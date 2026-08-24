"""Catalog rows whose identity is a real public YouTube channel.

For bound rows, creator_name === channel_title and youtube_channel_id is
persisted. That is not KYC. attached_channel still wins at runtime.
Unbound rows stay synthetic personas.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.youtube_clips import overlay_clip_from_upload


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VERIFIED_CHANNELS_PATH = ROOT / "data" / "verified_public_channels.json"
OWNERSHIP = "catalog_channel"
VERIFIED_ROW_LABEL = "This catalog row is this public YouTube channel: {channel_title}"
LEFTOVER_SEARCH_NOTE = "Leftover public_search_hit: topic search, not a verified channel bind."


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def load_verified_public_channels(
    path: str | Path = DEFAULT_VERIFIED_CHANNELS_PATH,
) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {
            "pack_id": "",
            "version": 0,
            "binds": [],
            "available": False,
            "note": "No verified public channel bind table.",
        }
    raw = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("verified_public_channels.json must be a JSON object.")
    binds = raw.get("binds") or []
    if not isinstance(binds, list):
        raise ValueError("verified_public_channels.json binds must be an array.")
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in binds:
        if not isinstance(item, dict):
            raise ValueError("Each verified bind must be an object.")
        creator_id = _as_text(item.get("creator_id"))
        channel_id = _as_text(item.get("channel_id"))
        channel_title = _as_text(item.get("channel_title"))
        reason = _as_text(item.get("bind_reason"))
        ownership = _as_text(item.get("ownership") or OWNERSHIP)
        if not creator_id or not channel_id or not channel_title or not reason:
            raise ValueError("Each verified bind needs creator_id, channel_id, channel_title and bind_reason.")
        if not channel_id.startswith("UC"):
            raise ValueError(f"{creator_id} channel_id must be a public UC… id.")
        if ownership != OWNERSHIP:
            raise ValueError(f"{creator_id} ownership must be {OWNERSHIP}.")
        if creator_id in seen:
            raise ValueError(f"Duplicate verified bind for {creator_id}.")
        uploads = []
        for upload in item.get("uploads") or []:
            if not isinstance(upload, dict):
                continue
            video_id = _as_text(upload.get("video_id"))
            url = _as_text(upload.get("url"))
            if not video_id or not url.startswith("https://www.youtube.com/watch"):
                raise ValueError(f"{creator_id} uploads need video_id and a public watch URL.")
            uploads.append(
                {
                    "video_id": video_id,
                    "url": url,
                    "title": upload.get("title") or video_id,
                    "thumbnail_url": upload.get("thumbnail_url") or "",
                    "channel_id": _as_text(upload.get("channel_id") or channel_id),
                    "channel_title": _as_text(upload.get("channel_title") or channel_title),
                    "duration": upload.get("duration"),
                }
            )
        seen.add(creator_id)
        cleaned.append(
            {
                **item,
                "creator_id": creator_id,
                "channel_id": channel_id,
                "channel_title": channel_title,
                "bind_reason": reason,
                "ownership": OWNERSHIP,
                "uploads": uploads,
            }
        )
    return {**raw, "binds": cleaned, "available": bool(cleaned)}


def binds_by_creator_id(
    pack: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    data = pack if pack is not None else load_verified_public_channels()
    return {str(item["creator_id"]): dict(item) for item in data.get("binds") or []}


def cache_clips_by_video_id(clips: Iterable[Mapping[str, Any]] | None) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for item in clips or []:
        video_id = _as_text(item.get("video_id"))
        if video_id and video_id not in found:
            found[video_id] = dict(item)
    return found


def overlay_for_verified_bind(
    bind: Mapping[str, Any],
    posts: Sequence[Mapping[str, Any]],
    *,
    cache_by_video: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Zip this catalog row's posts to that public channel's uploads. Timedtext reused from cache."""

    cache_by_video = cache_by_video or {}
    bound: dict[str, dict[str, Any]] = {}
    for post, upload in zip(list(posts), list(bind.get("uploads") or [])):
        post_id = _as_text(post.get("post_id"))
        video_id = _as_text(upload.get("video_id"))
        if not post_id or not video_id:
            continue
        cached = dict(cache_by_video.get(video_id) or {})
        timedtext = None
        if cached.get("caption_body_status") == "downloaded_public_timedtext" and cached.get("caption_lines"):
            timedtext = {
                "caption_body_status": "downloaded_public_timedtext",
                "caption_lines": list(cached.get("caption_lines") or []),
                "source": cached.get("caption_body_source") or "youtube_public_timedtext",
                "language": cached.get("caption_language"),
                "track_kind": cached.get("caption_track_kind"),
            }
        bound[post_id] = overlay_clip_from_upload(
            post,
            {
                "video_id": video_id,
                "url": upload.get("url") or cached.get("url"),
                "title": upload.get("title") or cached.get("title"),
                "thumbnail_url": upload.get("thumbnail_url") or cached.get("thumbnail_url"),
                "channel_id": bind.get("channel_id"),
                "channel_title": bind.get("channel_title"),
                "duration": upload.get("duration") or cached.get("duration"),
            },
            ownership=OWNERSHIP,
            comments={
                "snippets": list(cached.get("comment_snippets") or []),
                "themes": list(cached.get("comment_themes") or cached.get("youtube_comment_themes") or []),
            },
            tracks=list(cached.get("caption_tracks") or []),
            timedtext=timedtext,
        )
    return bound


def verified_row_label(bind: Mapping[str, Any] | None) -> str:
    if not bind:
        return ""
    title = _as_text(bind.get("channel_title")) or "public channel"
    return VERIFIED_ROW_LABEL.format(channel_title=title)
