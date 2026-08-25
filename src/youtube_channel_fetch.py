"""Hydrate intensive-read overlays from a public channel's uploads.

Used when an operator attaches live evidence, and when the catalog name
matches a public channel title. Never enters ranking. Never invents caption bodies.
"""

from __future__ import annotations

from typing import Any, Mapping

from services.youtube_service import (
    caption_tracks_for_video,
    comment_threads_for_video,
    videos_for_channel,
)
from services.youtube_timedtext import fetch_public_timedtext
from src.youtube_clips import bind_uploads_to_posts


def hydrate_channel_clips(
    channel: Mapping[str, Any],
    posts: list[Mapping[str, Any]],
    *,
    ownership: str,
) -> list[dict[str, Any]]:
    """Return overlay rows in catalog-post order. Empty if the channel has no public uploads."""

    channel_id = str(channel.get("channel_id") or "").strip()
    if not channel_id or not posts:
        return []
    listed = videos_for_channel(channel_id, max_results=max(1, min(len(posts), 10)))
    videos = []
    for item in listed.get("items") or []:
        row = dict(item)
        row["channel_id"] = row.get("channel_id") or channel_id
        row["channel_title"] = row.get("channel_title") or channel.get("title")
        videos.append(row)
    comments_by_video: dict[str, dict[str, Any]] = {}
    tracks_by_video: dict[str, list] = {}
    timedtext_by_video: dict[str, dict[str, Any]] = {}
    for video in videos:
        video_id = str(video.get("video_id") or "")
        if not video_id:
            continue
        comments_by_video[video_id] = comment_threads_for_video(video_id)
        tracks = caption_tracks_for_video(video_id)
        track_items = list(tracks.get("items") or [])
        tracks_by_video[video_id] = track_items
        timedtext_by_video[video_id] = fetch_public_timedtext(video_id, track_items)
    bound = bind_uploads_to_posts(
        list(posts),
        videos,
        ownership=ownership,
        comments_by_video=comments_by_video,
        tracks_by_video=tracks_by_video,
        timedtext_by_video=timedtext_by_video,
    )
    return [bound[str(post.get("post_id"))] for post in posts if str(post.get("post_id")) in bound]
