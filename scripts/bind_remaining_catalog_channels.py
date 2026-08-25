"""Bind remaining synthetic catalog rows to unique public YouTube channels.

Keeps the existing 20 binds. Prefers curated well-known channel IDs (verified
via channels.list, uploads via playlistItems — no search.list) then cache
leftovers in the action-cam / cycling / travel / outdoor / moto niche.
creator_id stays stable. creator_name becomes channel_title. Not KYC.
"""

from __future__ import annotations

import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.youtube_service import channels_list, is_youtube_available, uploads_via_playlist
from services.youtube_timedtext import fetch_public_timedtext
from src.content_evidence import clips_for, load_creator_content
from src.data_loader import load_creators
from src.verified_channels import DEFAULT_VERIFIED_CHANNELS_PATH, OWNERSHIP
from src.youtube_clips import DEFAULT_YOUTUBE_CLIPS_PATH, overlay_clip_from_upload

MAX_PLAYLIST_FETCHES = 40
MAX_TIMEDTEXT_FETCHES = 80
NEED = 40

WELL_KNOWN_EXTRA: list[dict] = [
    {
        "channel_id": "UCuTaETsuCOkJ0H_GAztWt0Q",
        "accept": {"Global Cycling Network", "GCN"},
        "topics": ["cycling", "outdoor"],
    },
    {
        "channel_id": "UCu8YylsPiu9XfaQC74Hr_Gw",
        "accept": {"Berm Peak"},
        "topics": ["cycling", "outdoor", "vlog"],
    },
    {
        "channel_id": "UCCXxVerycxB08muPJta5WBQ",
        "accept": {"Peak Design"},
        "topics": ["tech", "travel"],
    },
    {
        "channel_id": "UC3DkFux8Iv-aYnTRWzwaiBA",
        "accept": {"Peter McKinnon"},
        "topics": ["tech", "travel", "cinematic"],
    },
    {
        "channel_id": "UCblfuW_4rakIf2hCnfAtEpg",
        "accept": {"Red Bull"},
        "topics": ["outdoor", "skiing", "surfing", "travel"],
    },
    {
        "channel_id": "UC-yRDvpR1W6E1QSHlEmXk-w",
        "accept": {"Yes Theory"},
        "topics": ["travel", "outdoor"],
    },
    {
        "channel_id": "UC4FHiPgSThOJQZ-4WC0DobQ",
        "accept": {"Matti Haapoja"},
        "topics": ["cinematic", "travel", "tech"],
    },
    {
        "channel_id": "UCiWLcA2eKP7ePXa9NQzMjPg",
        "accept": {"GMBN Tech"},
        "topics": ["cycling", "tech", "outdoor"],
    },
]

PREFERRED_CACHE_TITLES = [
    "Lost LeBlanc",
    "MyLifeOutdoors",
    "JORDAN HETRICK",
    "Ben Claremont",
    "Action Cam Guy",
    "Insta360 Shorts",
    "Scrambler POV",
    "The Ride with Ben Delaney",
    "Dots on a Map",
    "Open Air Problems",
    "Backcountry Exposure",
    "GT Biking",
    "Her Two Wheels",
    "Nick Kendall",
    "Weekend On Wheels #Wow",
    "Surf Life Siargao",
    "Kitesurfing Official",
    "OTM Cars & Motorcycles",
    "AuthenTech - Ben Schmanke",
    "Capture Guide",
    "GoPronaut",
    "Life at Lean",
    "The Bergreens",
    "Tahoe Meg",
    "Emory, By Land",
    "Frost Ops",
    "JB Outside",
    "JCUTMoto",
    "Boards, Bikes, And Hikes",
    "Dork in the Road",
    "HondaFanboy35",
    "Geekyranjit",
    "Sulit Tech Reviews",
    "TheCuriousEngineer",
    "Chris Brockhurst",
    "Chris Rogers",
    "BuzzAlong",
    "Chaos Causes",
    "FlytPath",
    "Best Phone Mounts",
    "David Manning",
    "Ryan Osmond",
    "Max Wrist",
    "Simply Philip",
    "Surf Traveller",
    "TheBetterBuy",
    "Venom's Tech",
    "Loud Oli Tech",
    "Luuk | Travel is Happiness",
    "Ryan Purvis",
    "Artem Shcherbyna",
    "Jaden Coyer",
    "Jeremiah Staab",
    "Josh Kwan",
    "Tech Fowler",
    "Tech By Aadil",
    "Capture Guide",
]


def _norm(value: str) -> str:
    return " ".join(str(value or "").lower().split())


def _topic_score(creator_topics: list[str], channel_topics: list[str]) -> int:
    left = {str(item).lower() for item in creator_topics or []}
    right = {str(item).lower() for item in channel_topics or []}
    return len(left & right)


def _topics_from_title(title: str) -> list[str]:
    blob = _norm(title)
    mapping = [
        (["bike", "cycling", "gmbn", "gcn", "wheels", "biking", "gravel", "ride"], "cycling"),
        (["moto", "scrambler", "honda", "motorcycle"], "motorcycle"),
        (["surf", "kite"], "surfing"),
        (["ski", "snow"], "skiing"),
        (["hike", "outdoor", "trail", "backcountry", "gopro", "insta360", "open air"], "outdoor"),
        (["travel", "leblanc", "map", "journey", "yes theory"], "travel"),
        (["tech", "cam", "review", "engineer", "phone", "mount", "chap"], "tech"),
    ]
    found: list[str] = []
    for keys, topic in mapping:
        if any(key in blob for key in keys) and topic not in found:
            found.append(topic)
    return found or ["outdoor", "travel"]


def _as_topics(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [item for item in str(value or "").split("|") if item.strip()]


def _timedtext_from_cache(cached: dict) -> dict | None:
    if cached.get("caption_body_status") == "downloaded_public_timedtext" and cached.get("caption_lines"):
        return {
            "caption_body_status": "downloaded_public_timedtext",
            "caption_lines": list(cached.get("caption_lines") or []),
            "source": cached.get("caption_body_source") or "youtube_public_timedtext",
            "language": cached.get("caption_language"),
            "track_kind": cached.get("caption_track_kind"),
        }
    return None


def _upload_row(item: dict, channel_id: str, channel_title: str) -> dict:
    video_id = str(item.get("video_id") or "")
    return {
        "video_id": video_id,
        "url": item.get("url") or f"https://www.youtube.com/watch?v={video_id}",
        "title": item.get("title") or video_id,
        "thumbnail_url": item.get("thumbnail_url") or "",
        "channel_id": channel_id,
        "channel_title": channel_title,
        "duration": item.get("duration"),
    }


def _cache_channels(clips: list[dict]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for clip in clips:
        channel_id = str(clip.get("channel_id") or "").strip()
        if not channel_id.startswith("UC"):
            continue
        rec = found.setdefault(
            channel_id,
            {"channel_id": channel_id, "channel_title": "", "uploads": [], "seen": set()},
        )
        if not rec["channel_title"]:
            rec["channel_title"] = str(clip.get("channel_title") or "").strip()
        video_id = str(clip.get("video_id") or "")
        if video_id and video_id not in rec["seen"]:
            rec["seen"].add(video_id)
            rec["uploads"].append(_upload_row(clip, channel_id, rec["channel_title"]))
    for rec in found.values():
        rec.pop("seen", None)
    return found


def main() -> None:
    pack = json.loads(DEFAULT_VERIFIED_CHANNELS_PATH.read_text(encoding="utf-8"))
    existing = list(pack.get("binds") or [])
    used_channels = {str(item.get("channel_id") or "") for item in existing}
    used_titles = {_norm(str(item.get("channel_title") or "")) for item in existing}
    used_formers = {_norm(str(item.get("former_catalog_name") or "")) for item in existing}

    cache_raw = json.loads(DEFAULT_YOUTUBE_CLIPS_PATH.read_text(encoding="utf-8"))
    clips = list(cache_raw.get("clips") or [])
    by_video = {str(item.get("video_id")): item for item in clips if item.get("video_id")}
    cache_by_channel = _cache_channels(clips)

    catalog = load_creators(ROOT / "data" / "creators.csv")
    bound_ids = {str(item.get("creator_id") or "") for item in existing}
    unbound_ids = [str(cid) for cid in catalog["creator_id"].astype(str) if cid not in bound_ids]
    names = {str(row.creator_id): str(row.creator_name) for row in catalog.itertuples()}
    topics_by_id = {str(row.creator_id): _as_topics(row.topics) for row in catalog.itertuples()}

    skip_titles = used_titles | used_formers | {_norm(names.get(cid) or "") for cid in unbound_ids}
    skip_titles.add(_norm("Daniel Surf"))
    skip_titles.add(_norm("Rena Gao"))

    resolved: list[dict] = []
    playlist_fetches = 0
    channel_list_calls = 0
    timedtext_fetches = 0

    def _accept_title(title: str, accept: set[str] | None = None) -> bool:
        if accept and _norm(title) not in {_norm(item) for item in accept}:
            return False
        if _norm(title) in skip_titles or _norm(title) in used_titles:
            return False
        return True

    def _maybe_enrich(channel_id: str, title: str, uploads: list[dict], playlist_id: str = "") -> list[dict]:
        nonlocal playlist_fetches
        if len(uploads) >= 3 or not is_youtube_available() or playlist_fetches >= MAX_PLAYLIST_FETCHES:
            return uploads[:3]
        fetched = uploads_via_playlist(
            channel_id,
            max_results=3,
            uploads_playlist_id=playlist_id or None,
        )
        playlist_fetches += 1
        items = list(fetched.get("items") or [])
        print(
            f"playlist {title!r} channel={channel_id} uploads={len(items)} error={fetched.get('error')}",
            flush=True,
        )
        time.sleep(0.08)
        if not items:
            return uploads[:3]
        by_id = {str(item.get("video_id")): item for item in uploads if item.get("video_id")}
        for item in items:
            video_id = str(item.get("video_id") or "")
            if video_id and video_id not in by_id:
                by_id[video_id] = _upload_row(item, channel_id, title)
        ordered = [_upload_row(item, channel_id, title) for item in items if item.get("video_id")]
        for item in uploads:
            if item.get("video_id") and item["video_id"] not in {row["video_id"] for row in ordered}:
                ordered.append(item)
        return ordered[:3]

    if is_youtube_available() and WELL_KNOWN_EXTRA:
        wanted_ids = [item["channel_id"] for item in WELL_KNOWN_EXTRA if item["channel_id"] not in used_channels]
        listed = channels_list(wanted_ids)
        channel_list_calls += 1
        by_id = {str(item.get("channel_id")): item for item in (listed.get("items") or [])}
        print(f"channels.list extra={len(by_id)} error={listed.get('error')}", flush=True)
        for seed in WELL_KNOWN_EXTRA:
            if len(resolved) >= NEED:
                break
            channel_id = seed["channel_id"]
            if channel_id in used_channels:
                continue
            found = by_id.get(channel_id)
            title = str((found or {}).get("title") or "")
            if not found or not _accept_title(title, seed["accept"]):
                print(f"skip_known {channel_id} title={title!r}", flush=True)
                continue
            uploads = _maybe_enrich(
                channel_id,
                title,
                [],
                str(found.get("uploads_playlist_id") or ""),
            )
            if not uploads:
                print(f"empty_uploads {title!r} {channel_id}", flush=True)
                continue
            used_channels.add(channel_id)
            used_titles.add(_norm(title))
            resolved.append(
                {
                    "channel_id": channel_id,
                    "channel_title": title,
                    "topics": list(seed["topics"]),
                    "uploads": uploads,
                }
            )
            print(f"resolved_known {title!r} {channel_id} uploads={len(uploads)}", flush=True)

    preferred_rank = {_norm(title): index for index, title in enumerate(PREFERRED_CACHE_TITLES)}
    leftovers = []
    for channel_id, rec in cache_by_channel.items():
        title = rec["channel_title"]
        if channel_id in used_channels or not title:
            continue
        if not _accept_title(title):
            continue
        leftovers.append(rec)
    leftovers.sort(
        key=lambda rec: (
            preferred_rank.get(_norm(rec["channel_title"]), 10_000),
            -len(rec["uploads"]),
            rec["channel_title"].lower(),
        )
    )
    for rec in leftovers:
        if len(resolved) >= NEED:
            break
        channel_id = rec["channel_id"]
        title = rec["channel_title"]
        if channel_id in used_channels or _norm(title) in used_titles:
            continue
        uploads = _maybe_enrich(channel_id, title, list(rec["uploads"]))
        if not uploads:
            continue
        used_channels.add(channel_id)
        used_titles.add(_norm(title))
        resolved.append(
            {
                "channel_id": channel_id,
                "channel_title": title,
                "topics": _topics_from_title(title),
                "uploads": uploads,
            }
        )
        print(f"resolved_cache {title!r} {channel_id} uploads={len(uploads)}", flush=True)

    if len(resolved) < NEED:
        print(f"WARN only resolved {len(resolved)}/{NEED} extra channels", flush=True)

    extra_binds: list[dict] = []
    remaining_channels = list(resolved)
    for creator_id in unbound_ids:
        unused = [item for item in remaining_channels if item["channel_id"] not in {row["channel_id"] for row in extra_binds}]
        if not unused:
            break
        unused.sort(
            key=lambda item: (
                -_topic_score(topics_by_id.get(creator_id) or [], item["topics"]),
                item["channel_title"].lower(),
            )
        )
        chosen = unused[0]
        extra_binds.append(
            {
                "creator_id": creator_id,
                "catalog_name": chosen["channel_title"],
                "channel_id": chosen["channel_id"],
                "channel_title": chosen["channel_title"],
                "bind_reason": (
                    f"This catalog row is public YouTube channel {chosen['channel_title']!r} "
                    f"({chosen['channel_id']}). Intensive-read clips are that channel's public uploads. Not KYC."
                ),
                "ownership": OWNERSHIP,
                "topics": chosen["topics"],
                "uploads": chosen["uploads"][:3],
                "former_catalog_name": names.get(creator_id),
            }
        )

    all_binds = existing + extra_binds
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    pack.update(
        {
            "pack_id": "verified_public_channels_v1",
            "version": 1,
            "source": "youtube_data_api",
            "ownership": OWNERSHIP,
            "note": (
                "Catalog rows ARE these public YouTube channels (name + channel id). "
                "creator_id stays stable. Clips are that channel's public uploads. Not KYC. "
                "attached_channel still wins. Never ranked."
            ),
            "bound_at": now,
            "api_calls": {
                "channel_list_calls": channel_list_calls,
                "playlist_fetches": playlist_fetches,
                "timedtext_fetches": 0,
            },
            "bind_count": len(all_binds),
            "binds": all_binds,
        }
    )

    # Timedtext for new video ids only.
    for bind in extra_binds:
        for upload in bind["uploads"]:
            video_id = str(upload.get("video_id") or "")
            cached = by_video.get(video_id) or {}
            if cached.get("caption_body_status") == "downloaded_public_timedtext" and cached.get("caption_lines"):
                continue
            if timedtext_fetches >= MAX_TIMEDTEXT_FETCHES or not video_id:
                continue
            result = fetch_public_timedtext(video_id, list(cached.get("caption_tracks") or []))
            timedtext_fetches += 1
            if result.get("caption_body_status") == "downloaded_public_timedtext" and result.get("caption_lines"):
                merged = dict(cached)
                merged.update(
                    {
                        "video_id": video_id,
                        "caption_body_status": "downloaded_public_timedtext",
                        "caption_body_source": result.get("source") or "youtube_public_timedtext",
                        "caption_lines": list(result.get("caption_lines") or []),
                        "caption_language": result.get("language"),
                        "caption_track_kind": result.get("track_kind"),
                        "caption_body_error": None,
                    }
                )
                by_video[video_id] = merged
            time.sleep(0.05)
    pack["api_calls"]["timedtext_fetches"] = timedtext_fetches
    DEFAULT_VERIFIED_CHANNELS_PATH.write_text(
        json.dumps(pack, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # CSV identity
    csv_path = ROOT / "data" / "creators.csv"
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    extra_by_id = {item["creator_id"]: item for item in extra_binds}
    for row in rows:
        bind = extra_by_id.get(row["creator_id"])
        if not bind:
            continue
        row["creator_name"] = bind["channel_title"]
        row["youtube_channel_id"] = bind["channel_id"]
        row["bio"] = (
            f"Public YouTube channel {bind['channel_title']} ({bind['channel_id']}). "
            "This catalog row is that channel. Not KYC."
        )
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Genome identity
    genome_path = ROOT / "data" / "creator_genome.json"
    genome_pack = json.loads(genome_path.read_text(encoding="utf-8"))
    for genome in genome_pack.get("genomes") or []:
        bind = extra_by_id.get(str(genome.get("creator_id") or ""))
        if not bind:
            continue
        genome["creator_name"] = bind["channel_title"]
        genome["youtube_channel_id"] = bind["channel_id"]
        genome["identity_note"] = "Catalog row identity is this public YouTube channel. Not KYC."
    genome_path.write_text(json.dumps(genome_pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Catalog clip titles keep labeled-demo timestamps; display name follows the channel.
    content_path = ROOT / "data" / "creator_content.json"
    posts = json.loads(content_path.read_text(encoding="utf-8"))
    for post in posts:
        bind = extra_by_id.get(str(post.get("creator_id") or ""))
        if not bind:
            continue
        title = str(post.get("title") or "")
        former = bind.get("former_catalog_name")
        if former and title.startswith(f"{former} ·"):
            post["title"] = f"{bind['channel_title']} ·" + title.split("·", 1)[1]
        elif "· catalog clip" in title:
            suffix = title.split("· catalog clip", 1)[1]
            post["title"] = f"{bind['channel_title']} · catalog clip{suffix}"
    content_path.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Overlay youtube cache for extra binds.
    posts = load_creator_content()
    by_post = {str(item.get("post_id")): item for item in clips if item.get("post_id")}
    bound_creators = {item["creator_id"] for item in all_binds}
    for bind in extra_binds:
        creator_posts = clips_for(bind["creator_id"], posts)
        for post, upload in zip(creator_posts, bind["uploads"]):
            post_id = str(post.get("post_id") or "")
            video_id = str(upload.get("video_id") or "")
            cached = dict(by_video.get(video_id) or {})
            by_post[post_id] = overlay_clip_from_upload(
                post,
                upload,
                ownership=OWNERSHIP,
                comments={
                    "snippets": list(cached.get("comment_snippets") or []),
                    "themes": list(cached.get("comment_themes") or []),
                },
                tracks=list(cached.get("caption_tracks") or []),
                timedtext=_timedtext_from_cache(cached),
            )

    ordered = []
    seen = set()
    for post in posts:
        post_id = str(post.get("post_id") or "")
        clip = by_post.get(post_id)
        if clip and post_id not in seen:
            if str(clip.get("creator_id") or "") in extra_by_id and clip.get("ownership") != OWNERSHIP:
                continue
            ordered.append(clip)
            seen.add(post_id)
    for post_id, clip in by_post.items():
        if post_id not in seen:
            ordered.append(clip)

    mix: dict[str, int] = {}
    for item in ordered:
        token = str(item.get("ownership") or "public_search_hit")
        mix[token] = mix.get(token, 0) + 1
    cache_raw["clips"] = ordered
    cache_raw["ownership"] = "mixed"
    cache_raw["ownership_mix"] = mix
    cache_raw["verified_bind_count"] = len(all_binds)
    cache_raw["verified_bound_at"] = now
    cache_raw["note"] = (
        "Intensive-read YouTube overlay. catalog_channel = this catalog row is that public "
        "YouTube channel; clips are its uploads; not KYC. channel_search_match / public_search_hit "
        "only if a leftover unbound row remains. attached_channel is runtime operator attach. "
        "Never ranked. Not Whisper."
    )
    DEFAULT_YOUTUBE_CLIPS_PATH.write_text(json.dumps(cache_raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote extra={len(extra_binds)} total={len(all_binds)} mix={mix} "
        f"playlist={playlist_fetches} timedtext={timedtext_fetches}",
        flush=True,
    )


if __name__ == "__main__":
    main()
