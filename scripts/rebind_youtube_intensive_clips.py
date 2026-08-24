"""Rebind Top-20 intensive-read clips to public channels when the catalog name matches.

Unmatched creators keep the existing topic-search overlay (public_search_hit).
Never enters ranking. Does not print secrets.
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

from services.youtube_service import is_youtube_available, search_channels
from src.content_evidence import clips_for, load_creator_content
from src.data_loader import load_creators, load_mission
from src.scoring import rank_creators
from src.youtube_channel_fetch import hydrate_channel_clips
from src.youtube_clips import DEFAULT_YOUTUBE_CLIPS_PATH
from src.youtube_identity import pick_matching_channel


def main() -> None:
    if not is_youtube_available():
        print("YOUTUBE_API_KEY missing. Cache not rebound.")
        return
    path = DEFAULT_YOUTUBE_CLIPS_PATH
    raw = json.loads(path.read_text(encoding="utf-8"))
    clips = list(raw.get("clips") or [])
    by_post = {str(item.get("post_id")): item for item in clips if item.get("post_id")}
    catalog = load_creators(ROOT / "data" / "creators.csv")
    mission = load_mission(ROOT / "data" / "launch_mission.json")
    ranked = rank_creators(catalog, mission)
    posts = load_creator_content()
    names = {row.creator_id: row.creator_name for row in catalog.itertuples()}
    matched = 0
    skipped = 0
    for creator_id in list(ranked.head(20)["creator_id"]):
        creator_id = str(creator_id)
        name = str(names.get(creator_id) or "")
        result = search_channels(name, max_results=5)
        picked = pick_matching_channel(name, result.get("items") or [])
        if not picked:
            skipped += 1
            print(f"no_match {creator_id} {name!r}", flush=True)
            time.sleep(0.1)
            continue
        creator_posts = clips_for(creator_id, posts)
        overlays = hydrate_channel_clips(picked, creator_posts, ownership="channel_search_match")
        if not overlays:
            skipped += 1
            print(f"empty_uploads {creator_id} {name!r} channel={picked.get('channel_id')}", flush=True)
            time.sleep(0.2)
            continue
        assigned_ids = {str(item.get("post_id")) for item in overlays}
        for post in creator_posts:
            post_id = str(post.get("post_id") or "")
            if post_id in assigned_ids:
                continue
            by_post.pop(post_id, None)
        for item in overlays:
            by_post[str(item["post_id"])] = item
        matched += 1
        print(
            f"bound {creator_id} {name!r} -> {picked.get('title')!r} "
            f"uploads={len(overlays)} channel={picked.get('channel_id')}",
            flush=True,
        )
        time.sleep(0.2)

    ordered = []
    seen = set()
    for post in posts:
        post_id = str(post.get("post_id") or "")
        clip = by_post.get(post_id)
        if clip and post_id not in seen:
            ordered.append(clip)
            seen.add(post_id)
    for post_id, clip in by_post.items():
        if post_id not in seen:
            ordered.append(clip)

    mix = {}
    for item in ordered:
        token = str(item.get("ownership") or "public_search_hit")
        mix[token] = mix.get(token, 0) + 1
    raw["clips"] = ordered
    raw["pack_id"] = "youtube_intensive_x5_v2"
    raw["version"] = 2
    raw["ownership"] = "mixed"
    raw["ownership_mix"] = mix
    raw["channel_match_fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    raw["clip_count"] = len(ordered)
    raw["creator_count"] = len({item.get("creator_id") for item in ordered})
    raw["note"] = (
        "Intensive-read YouTube overlay. channel_search_match = catalog name matched a public "
        "channel title; public_search_hit = topic search, not claimed as the catalog creator. "
        "attached_channel is resolved at runtime from operator attach. Never enters ranking. "
        "Public timedtext stored when YouTube exposes it. Not Whisper."
    )
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(ordered)} clips mix={mix} matched_creators={matched} unmatched_top20={skipped}")


if __name__ == "__main__":
    main()
