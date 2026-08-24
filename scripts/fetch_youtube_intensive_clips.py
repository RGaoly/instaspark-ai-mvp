"""Fetch public YouTube videos into the intensive-read cache.

Does not enter ranking. Does not download caption bodies. Does not print secrets.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.content_evidence import load_creator_content
from src.data_loader import load_creators
from src.youtube_clips import DEFAULT_YOUTUBE_CLIPS_PATH
from services.youtube_service import (
    caption_tracks_for_video,
    comment_threads_for_video,
    is_youtube_available,
    search_videos,
    videos_list,
)

ROOT = Path(__file__).resolve().parents[1]

QUERIES = (
    "insta360 cycling POV",
    "insta360 travel 360 camera",
    "action camera motorcycle POV",
    "insta360 surfing",
    "ski helmet camera POV",
    "hiking 360 camera outdoor",
    "insta360 tech review",
    "motorcycle action camera",
    "travel vlog 360 camera",
)

TOPIC_QUERY = {
    "cycling": "insta360 cycling POV",
    "travel": "insta360 travel 360 camera",
    "motorcycle": "action camera motorcycle POV",
    "surfing": "insta360 surfing",
    "skiing": "ski helmet camera POV",
    "outdoor": "hiking 360 camera outdoor",
    "tech": "insta360 tech review",
    "beauty": "travel vlog 360 camera",
    "fashion": "travel vlog 360 camera",
}


def _pool() -> dict[str, list[dict]]:
    by_query: dict[str, list[dict]] = {}
    seen: set[str] = set()
    for query in QUERIES:
        result = search_videos(query, max_results=25)
        rows = []
        for item in result.get("items") or []:
            video_id = str(item.get("video_id") or "")
            if not video_id or video_id in seen:
                continue
            seen.add(video_id)
            rows.append(item)
        by_query[query] = rows
        print(f"search {query!r}: {len(rows)} unique public hits", flush=True)
    return by_query


def _pick(post: dict, creator_topics: list[str], by_query: dict[str, list[dict]], used: set[str]) -> dict | None:
    preferred = [TOPIC_QUERY[topic] for topic in creator_topics if topic in TOPIC_QUERY]
    order = preferred + [query for query in QUERIES if query not in preferred]
    for query in order:
        for item in by_query.get(query) or []:
            video_id = item["video_id"]
            if video_id in used:
                continue
            used.add(video_id)
            return {**item, "matched_query": query}
    return None


def main() -> None:
    if not is_youtube_available():
        print("YOUTUBE_API_KEY missing. Cache not written. Labeled demo stays in place.")
        return
    catalog = load_creators(ROOT / "data" / "creators.csv")
    topics_by_id = {row.creator_id: list(row.topics) for row in catalog.itertuples()}
    posts = load_creator_content()
    by_query = _pool()
    used: set[str] = set()
    assigned: list[tuple[dict, dict]] = []
    for post in posts:
        hit = _pick(post, topics_by_id.get(post["creator_id"], []), by_query, used)
        if hit:
            assigned.append((post, hit))
    print(f"assigned {len(assigned)} / {len(posts)} catalog clips", flush=True)
    meta = videos_list([hit["video_id"] for _post, hit in assigned])
    by_id = {item["video_id"]: item for item in meta.get("items") or []}
    print(f"videos.list public rows: {len(by_id)}", flush=True)

    clips = []
    first_clip_ids: set[str] = set()
    for post, hit in assigned:
        creator_id = post["creator_id"]
        video = by_id.get(hit["video_id"])
        if not video:
            continue
        comments = comment_threads_for_video(video["video_id"])
        tracks: list[dict] = []
        if creator_id not in first_clip_ids:
            first_clip_ids.add(creator_id)
            listed = caption_tracks_for_video(video["video_id"])
            tracks = list(listed.get("items") or [])
        clips.append(
            {
                "post_id": post["post_id"],
                "creator_id": creator_id,
                "video_id": video["video_id"],
                "url": video["url"],
                "title": video["title"],
                "duration": video.get("duration"),
                "thumbnail_url": video.get("thumbnail_url"),
                "channel_title": video.get("channel_title"),
                "privacy": "public",
                "keyframe_source": "youtube_thumbnail",
                "comment_source": "youtube_data_api",
                "comment_snippets": comments.get("snippets") or [],
                "comment_themes": comments.get("themes") or [],
                "caption_tracks": tracks,
                "caption_body_status": "not_downloaded",
                "asr_status": "not_collected",
                "asr": None,
                "transcript": None,
                "ownership": "public_search_hit",
                "query": hit.get("matched_query") or hit.get("query"),
                "source": "youtube_data_api",
            }
        )
        if len(clips) % 20 == 0:
            print(f"hydrated {len(clips)} clips", flush=True)

    pack = {
        "pack_id": "youtube_intensive_x5_v1",
        "version": 1,
        "source": "youtube_data_api",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ownership": "public_search_hit",
        "note": (
            "Public YouTube search hits for intensive read. Not claimed as catalog-creator uploads. "
            "Never enters ranking. ASR not collected. Caption track listed, body not downloaded."
        ),
        "clip_count": len(clips),
        "creator_count": len({item["creator_id"] for item in clips}),
        "clips": clips,
    }
    DEFAULT_YOUTUBE_CLIPS_PATH.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {len(clips)} clips / {pack['creator_count']} creators to "
        f"{DEFAULT_YOUTUBE_CLIPS_PATH.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
