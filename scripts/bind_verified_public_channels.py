"""Resolve well-known public YouTube channels and bind them to demo catalog rows.

Never claims the synthetic CSV name uploaded the videos. Prefers cached
timedtext by video_id. Fetches only missing binds, with a hard API cap.
Does not print secrets. Does not enter ranking.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.youtube_service import is_youtube_available, search_channels, videos_for_channel, videos_list
from src.content_evidence import clips_for, load_creator_content
from src.data_loader import load_creators, load_mission
from src.scoring import rank_creators
from src.verified_channels import DEFAULT_VERIFIED_CHANNELS_PATH, OWNERSHIP
from src.youtube_clips import DEFAULT_YOUTUBE_CLIPS_PATH, overlay_clip_from_upload
from src.youtube_identity import channel_title_matches

MAX_CHANNEL_SEARCHES = 28
MAX_UPLOAD_FETCHES = 28
MAX_VIDEO_LIST_BATCHES = 4

# Exact public titles we can justify. Not catalog persona names.
SEEDS: list[dict] = [
    {"query": "Insta360", "accept": {"Insta360"}, "topics": ["tech", "travel", "outdoor", "cycling", "motorcycle"]},
    {"query": "Insta360 Tutorials", "accept": {"Insta360 Tutorials"}, "topics": ["tech", "tutorial"]},
    {"query": "GoPro", "accept": {"GoPro"}, "topics": ["outdoor", "travel", "surfing", "skiing", "cycling"]},
    {"query": "DJI", "accept": {"DJI"}, "topics": ["tech", "travel", "outdoor"]},
    {"query": "DC Rainmaker", "accept": {"DC Rainmaker"}, "topics": ["tech", "cycling", "outdoor", "review"]},
    {"query": "NorCal Cycling", "accept": {"NorCal Cycling"}, "topics": ["cycling", "outdoor"]},
    {"query": "Chaseontwowheels", "accept": {"Chaseontwowheels"}, "topics": ["cycling", "POV"]},
    {"query": "Global Cycling Network", "accept": {"Global Cycling Network", "GCN"}, "topics": ["cycling", "outdoor"]},
    {"query": "GMBN", "accept": {"GMBN", "Global Mountain Bike Network"}, "topics": ["cycling", "outdoor", "POV"]},
    {"query": "Seth's Bike Hacks", "accept": {"Seth's Bike Hacks"}, "topics": ["cycling", "tutorial"]},
    {"query": "Berm Peak", "accept": {"Berm Peak"}, "topics": ["cycling", "outdoor", "vlog"]},
    {"query": "Red Bull", "accept": {"Red Bull"}, "topics": ["outdoor", "skiing", "surfing", "travel"]},
    {"query": "World Surf League", "accept": {"World Surf League"}, "topics": ["surfing", "outdoor"]},
    {"query": "Patagonia", "accept": {"Patagonia"}, "topics": ["outdoor", "travel"]},
    {"query": "REI", "accept": {"REI"}, "topics": ["outdoor", "travel"]},
    {"query": "The North Face", "accept": {"The North Face"}, "topics": ["outdoor", "travel"]},
    {"query": "Peak Design", "accept": {"Peak Design"}, "topics": ["tech", "travel"]},
    {"query": "Peter McKinnon", "accept": {"Peter McKinnon"}, "topics": ["tech", "travel", "cinematic"]},
    {"query": "Chris Burkard", "accept": {"Chris Burkard"}, "topics": ["travel", "outdoor", "cinematic"]},
    {"query": "Sam Kolder", "accept": {"Sam Kolder"}, "topics": ["travel", "cinematic"]},
    {"query": "Matti Haapoja", "accept": {"Matti Haapoja"}, "topics": ["cinematic", "travel", "tech"]},
    {"query": "Kara and Nate", "accept": {"Kara and Nate"}, "topics": ["travel", "vlog"]},
    {"query": "Yes Theory", "accept": {"Yes Theory"}, "topics": ["travel", "outdoor"]},
    {"query": "Oscar Hikes", "accept": {"Oscar Hikes"}, "topics": ["outdoor", "travel", "POV"]},
    {"query": "Surfing With Noz", "accept": {"Surfing With Noz"}, "topics": ["surfing", "outdoor", "POV"]},
    {"query": "MyLifeOutdoors", "accept": {"MyLifeOutdoors"}, "topics": ["outdoor", "travel"]},
    {"query": "The Tech Chap", "accept": {"The Tech Chap"}, "topics": ["tech", "review"]},
    {"query": "Becca Farsace", "accept": {"Becca Farsace"}, "topics": ["tech", "review"]},
]


def _norm(value: str) -> str:
    return " ".join(str(value or "").lower().split())


def _pick_seed_channel(items: list[dict], accept: set[str]) -> dict | None:
    wanted = {_norm(item) for item in accept}
    for item in items:
        if _norm(item.get("title") or "") in wanted:
            return item
    return None


def _topic_score(creator_topics: list[str], channel_topics: list[str]) -> int:
    left = {str(item).lower() for item in creator_topics or []}
    right = {str(item).lower() for item in channel_topics or []}
    return len(left & right)


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


def main() -> None:
    cache_path = DEFAULT_YOUTUBE_CLIPS_PATH
    raw = json.loads(cache_path.read_text(encoding="utf-8"))
    clips = list(raw.get("clips") or [])
    by_video = {str(item.get("video_id")): item for item in clips if item.get("video_id")}
    missing_ids = [vid for vid, item in by_video.items() if not str(item.get("channel_id") or "").strip()]
    video_list_calls = 0
    if is_youtube_available() and missing_ids:
        for start in range(0, len(missing_ids), 50):
            if video_list_calls >= MAX_VIDEO_LIST_BATCHES:
                break
            listed = videos_list(missing_ids[start : start + 50])
            video_list_calls += 1
            for item in listed.get("items") or []:
                video_id = str(item.get("video_id") or "")
                if video_id in by_video and item.get("channel_id"):
                    by_video[video_id]["channel_id"] = item.get("channel_id")
                    by_video[video_id]["channel_title"] = item.get("channel_title") or by_video[video_id].get(
                        "channel_title"
                    )
            time.sleep(0.05)

    catalog = load_creators(ROOT / "data" / "creators.csv")
    persona_names = {_norm(name) for name in catalog["creator_name"].tolist()}
    resolved: list[dict] = []
    searches = 0
    fetches = 0
    if is_youtube_available():
        for seed in SEEDS:
            if searches >= MAX_CHANNEL_SEARCHES or fetches >= MAX_UPLOAD_FETCHES:
                break
            if any(_norm(item["channel_title"]) in {_norm(title) for title in seed["accept"]} for item in resolved):
                continue
            result = search_channels(seed["query"], max_results=5)
            searches += 1
            picked = _pick_seed_channel(list(result.get("items") or []), seed["accept"])
            if not picked:
                print(f"skip_search {seed['query']!r} error={result.get('error')}", flush=True)
                time.sleep(0.1)
                continue
            title = str(picked.get("title") or "")
            if _norm(title) in persona_names or any(
                channel_title_matches(name, title) for name in catalog["creator_name"].tolist()
            ):
                print(f"reject_persona_collision {title!r}", flush=True)
                time.sleep(0.1)
                continue
            uploads = videos_for_channel(str(picked.get("channel_id") or ""), max_results=3)
            fetches += 1
            items = list(uploads.get("items") or [])
            if not items:
                print(
                    f"empty_uploads {title!r} channel={picked.get('channel_id')} error={uploads.get('error')}",
                    flush=True,
                )
                time.sleep(0.15)
                continue
            resolved.append(
                {
                    "channel_id": str(picked.get("channel_id")),
                    "channel_title": title,
                    "topics": list(seed["topics"]),
                    "uploads": items,
                    "bind_reason": (
                        f"Public channel {title!r} ({picked.get('channel_id')}). "
                        "Bound to this demo catalog row for intensive-read of that channel's public uploads. "
                        "The CSV display name is a synthetic persona and is not the uploader."
                    ),
                }
            )
            print(f"resolved {title!r} channel={picked.get('channel_id')} uploads={len(items)}", flush=True)
            time.sleep(0.15)
    else:
        print("YOUTUBE_API_KEY missing. Bind table not refreshed from live API.", flush=True)

    mission = load_mission(ROOT / "data" / "launch_mission.json")
    ranked = rank_creators(catalog, mission)
    order = list(ranked["creator_id"].astype(str)) + [
        cid for cid in catalog["creator_id"].astype(str) if cid not in set(ranked["creator_id"].astype(str))
    ]
    topics_by_id = {
        str(row.creator_id): list(row.topics) if not isinstance(row.topics, str) else row.topics.split("|")
        for row in catalog.itertuples()
    }
    names = {str(row.creator_id): str(row.creator_name) for row in catalog.itertuples()}
    used_channels: set[str] = set()
    binds: list[dict] = []
    for creator_id in order:
        unused = [item for item in resolved if item["channel_id"] not in used_channels]
        if not unused:
            break
        unused.sort(key=lambda item: (-_topic_score(topics_by_id.get(creator_id) or [], item["topics"]), item["channel_title"]))
        chosen = unused[0]
        used_channels.add(chosen["channel_id"])
        binds.append(
            {
                "creator_id": creator_id,
                "catalog_name": names.get(creator_id),
                "channel_id": chosen["channel_id"],
                "channel_title": chosen["channel_title"],
                "bind_reason": chosen["bind_reason"],
                "ownership": OWNERSHIP,
                "topics": chosen["topics"],
                "uploads": [
                    {
                        "video_id": item.get("video_id"),
                        "url": item.get("url"),
                        "title": item.get("title"),
                        "thumbnail_url": item.get("thumbnail_url"),
                        "channel_id": chosen["channel_id"],
                        "channel_title": chosen["channel_title"],
                        "duration": item.get("duration"),
                    }
                    for item in chosen["uploads"][:3]
                    if item.get("video_id")
                ],
            }
        )

    bind_doc = {
        "pack_id": "verified_public_channels_v1",
        "version": 1,
        "source": "youtube_data_api",
        "ownership": OWNERSHIP,
        "note": (
            "Demo catalog rows bound to real public YouTube channels for intensive-read. "
            "Catalog display names stay synthetic personas and are not the uploaders. "
            "attached_channel still wins if an operator attaches a channel. Never enters ranking."
        ),
        "bound_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "api_calls": {
            "channel_searches": searches,
            "upload_fetches": fetches,
            "video_list_batches": video_list_calls,
        },
        "bind_count": len(binds),
        "binds": binds,
    }
    DEFAULT_VERIFIED_CHANNELS_PATH.write_text(json.dumps(bind_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    posts = load_creator_content()
    by_post = {str(item.get("post_id")): item for item in clips if item.get("post_id")}
    bound_creators = {item["creator_id"] for item in binds}
    for bind in binds:
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
            if str(clip.get("creator_id") or "") in bound_creators and clip.get("ownership") != OWNERSHIP:
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
    raw["clips"] = ordered
    raw["ownership"] = "mixed"
    raw["ownership_mix"] = mix
    raw["verified_bind_count"] = len(binds)
    raw["verified_bound_at"] = bind_doc["bound_at"]
    raw["note"] = (
        "Intensive-read YouTube overlay. verified_public_channel = demo row bound to a real public "
        "channel; catalog name is not the uploader. channel_search_match = catalog name matched a "
        "public channel title. public_search_hit = topic search. attached_channel is runtime operator "
        "attach. Never enters ranking. Public timedtext stored when already cached. Not Whisper."
    )
    cache_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote binds={len(binds)} clips={len(ordered)} mix={mix} "
        f"searches={searches} fetches={fetches} video_list={video_list_calls}",
        flush=True,
    )


if __name__ == "__main__":
    main()
