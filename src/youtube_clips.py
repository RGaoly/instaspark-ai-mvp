"""Public YouTube intensive-read overlay. Never enters ranking.

Cached JSON is the offline source of truth after one fetch. Missing cache
keeps the labeled-demo catalog clips. This overlay does not claim catalog
creators uploaded the videos. Public timedtext bodies are optional and
never invented from labeled_demo.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_YOUTUBE_CLIPS_PATH = ROOT / "data" / "youtube_intensive_clips.json"
ALLOWED_THUMB_HOSTS = (".ytimg.com", "i.ytimg.com", "img.youtube.com")
ALLOWED_BODY_STATUS = frozenset({"not_downloaded", "downloaded_public_timedtext"})
ALLOWED_OWNERSHIP = frozenset(
    {"public_search_hit", "channel_search_match", "attached_channel", "verified_public_channel"}
)
TIMEDTEXT_SOURCE = "youtube_public_timedtext"


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _public_thumb(url: str) -> str:
    text = _as_text(url)
    host = urlparse(text).netloc.lower()
    if any(host == item or host.endswith(item) for item in ALLOWED_THUMB_HOSTS):
        return text
    return ""


def _clean_caption_lines(post_id: str, raw: Any, status: str) -> list[dict[str, str]]:
    if status != "downloaded_public_timedtext":
        if raw in (None, "", []):
            return []
        raise ValueError(f"{post_id} must not store caption_lines unless public timedtext downloaded.")
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{post_id} downloaded_public_timedtext requires caption_lines.")
    lines: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        stamp = _as_text(item.get("t"))
        text = _as_text(item.get("text"))
        if stamp and text:
            lines.append({"t": stamp, "text": text[:280]})
    if not lines:
        raise ValueError(f"{post_id} downloaded_public_timedtext caption_lines are empty.")
    return lines[:500]


def load_youtube_intensive_clips(
    path: str | Path = DEFAULT_YOUTUBE_CLIPS_PATH,
) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {
            "pack_id": "",
            "version": 0,
            "source": "youtube_data_api",
            "clips": [],
            "available": False,
            "note": "No YouTube intensive-read cache. Labeled demo layer stays in place.",
        }
    raw = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("YouTube intensive-read cache must be a JSON object.")
    if str(raw.get("source") or "") != "youtube_data_api":
        raise ValueError("YouTube intensive-read cache source must be youtube_data_api.")
    clips = raw.get("clips") or []
    if not isinstance(clips, list):
        raise ValueError("YouTube intensive-read cache clips must be an array.")
    cleaned = []
    ids: list[str] = []
    for item in clips:
        post_id = _as_text(item.get("post_id"))
        video_id = _as_text(item.get("video_id"))
        url = _as_text(item.get("url"))
        if not post_id or not video_id or not url.startswith("https://www.youtube.com/watch"):
            raise ValueError("Every YouTube clip needs post_id, video_id and a public watch URL.")
        if item.get("asr") not in (None, ""):
            raise ValueError(f"{post_id} must not store an ASR body.")
        if item.get("asr_status") != "not_collected":
            raise ValueError(f"{post_id} asr_status must stay not_collected.")
        if item.get("transcript") not in (None, ""):
            raise ValueError(f"{post_id} must not store a downloaded transcript.")
        if str(item.get("privacy") or "public") != "public":
            raise ValueError(f"{post_id} only public videos are allowed.")
        status = str(item.get("caption_body_status") or "not_downloaded")
        if status not in ALLOWED_BODY_STATUS:
            raise ValueError(f"{post_id} caption_body_status {status!r} is not allowed.")
        body_source = _as_text(item.get("caption_body_source"))
        if status == "downloaded_public_timedtext" and body_source != TIMEDTEXT_SOURCE:
            raise ValueError(f"{post_id} caption_body_source must be {TIMEDTEXT_SOURCE}.")
        if status == "not_downloaded" and body_source:
            raise ValueError(f"{post_id} must not claim a caption body source without a download.")
        lines = _clean_caption_lines(post_id, item.get("caption_lines"), status)
        token = str(item.get("keyframe_source") or "")
        if token != "youtube_thumbnail":
            raise ValueError(f"{post_id} keyframe_source must be youtube_thumbnail.")
        if str(item.get("comment_source") or "") != "youtube_data_api":
            raise ValueError(f"{post_id} comment_source must be youtube_data_api.")
        ownership = str(item.get("ownership") or "public_search_hit")
        if ownership not in ALLOWED_OWNERSHIP:
            raise ValueError(f"{post_id} ownership {ownership!r} is not allowed.")
        channel_id = _as_text(item.get("channel_id"))
        if ownership in {"attached_channel", "channel_search_match", "verified_public_channel"} and not channel_id:
            raise ValueError(f"{post_id} creator-linked ownership requires channel_id.")
        ids.append(post_id)
        cleaned.append(
            {
                **item,
                "post_id": post_id,
                "video_id": video_id,
                "url": url,
                "thumbnail_url": _public_thumb(str(item.get("thumbnail_url") or "")),
                "comment_snippets": [str(s).strip()[:280] for s in (item.get("comment_snippets") or []) if str(s).strip()][:3],
                "comment_themes": [str(s).strip() for s in (item.get("comment_themes") or []) if str(s).strip()][:3],
                "caption_tracks": list(item.get("caption_tracks") or []),
                "caption_body_status": status,
                "caption_body_source": body_source or None,
                "caption_lines": lines,
                "asr_status": "not_collected",
                "ownership": ownership,
                "channel_id": channel_id or None,
                "source": "youtube_data_api",
            }
        )
    if len(ids) != len(set(ids)):
        raise ValueError("YouTube intensive-read post_id values must be unique.")
    return {
        **raw,
        "clips": cleaned,
        "available": bool(cleaned),
    }


def youtube_clips_by_post_id(
    pack: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    data = pack if pack is not None else load_youtube_intensive_clips()
    return {str(item["post_id"]): dict(item) for item in data.get("clips") or []}


def attach_youtube_overlay(clip: Mapping[str, Any], overlay: Mapping[str, Any] | None) -> dict[str, Any]:
    """Display overlay. Ranking catalog URL stays on catalog_url."""

    merged = dict(clip)
    merged["catalog_url"] = str(clip.get("url") or "")
    if not overlay:
        return merged
    status = str(overlay.get("caption_body_status") or "not_downloaded")
    lines = list(overlay.get("caption_lines") or []) if status == "downloaded_public_timedtext" else []
    if status != "downloaded_public_timedtext" or not lines:
        status = "not_downloaded"
        lines = []
        body_source = None
    else:
        body_source = str(overlay.get("caption_body_source") or TIMEDTEXT_SOURCE)
    merged["video_id"] = overlay.get("video_id")
    merged["url"] = overlay.get("url") or merged["url"]
    merged["youtube_title"] = overlay.get("title")
    merged["thumbnail_url"] = overlay.get("thumbnail_url")
    merged["keyframe_source"] = "youtube_thumbnail"
    merged["comment_source"] = "youtube_data_api"
    merged["comment_snippets"] = list(overlay.get("comment_snippets") or [])
    merged["youtube_comment_themes"] = list(overlay.get("comment_themes") or [])
    merged["caption_tracks"] = list(overlay.get("caption_tracks") or [])
    merged["caption_body_status"] = status
    merged["caption_body_source"] = body_source
    merged["caption_lines"] = [{"t": str(item.get("t") or ""), "text": str(item.get("text") or "")} for item in lines if str(item.get("t") or "").strip() and str(item.get("text") or "").strip()]
    merged["youtube_source"] = "youtube_data_api"
    merged["ownership"] = str(overlay.get("ownership") or "public_search_hit")
    if merged["ownership"] not in ALLOWED_OWNERSHIP:
        merged["ownership"] = "public_search_hit"
    merged["channel_id"] = overlay.get("channel_id")
    merged["channel_title"] = overlay.get("channel_title")
    merged["asr_status"] = "not_collected"
    merged["asr"] = None
    return merged


def overlay_clip_from_upload(
    post: Mapping[str, Any],
    video: Mapping[str, Any],
    *,
    ownership: str,
    comments: Mapping[str, Any] | None = None,
    tracks: list | None = None,
    timedtext: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a cache/overlay row from a public channel upload. Does not invent bodies."""

    if ownership not in ALLOWED_OWNERSHIP:
        raise ValueError(f"ownership {ownership!r} is not allowed.")
    status = "not_downloaded"
    lines: list[dict[str, str]] = []
    body_source = None
    if timedtext and timedtext.get("caption_body_status") == "downloaded_public_timedtext":
        raw_lines = list(timedtext.get("caption_lines") or [])
        lines = [
            {"t": str(item.get("t") or ""), "text": str(item.get("text") or "")}
            for item in raw_lines
            if str(item.get("t") or "").strip() and str(item.get("text") or "").strip()
        ]
        if lines:
            status = "downloaded_public_timedtext"
            body_source = str(timedtext.get("source") or TIMEDTEXT_SOURCE)
    comments = comments or {}
    return {
        "post_id": str(post.get("post_id") or ""),
        "creator_id": str(post.get("creator_id") or ""),
        "video_id": str(video.get("video_id") or ""),
        "url": str(video.get("url") or ""),
        "title": video.get("title"),
        "duration": video.get("duration"),
        "thumbnail_url": video.get("thumbnail_url"),
        "channel_title": video.get("channel_title"),
        "channel_id": video.get("channel_id"),
        "privacy": "public",
        "keyframe_source": "youtube_thumbnail",
        "comment_source": "youtube_data_api",
        "comment_snippets": list(comments.get("snippets") or []),
        "comment_themes": list(comments.get("themes") or []),
        "caption_tracks": list(tracks or []),
        "caption_body_status": status,
        "caption_body_source": body_source,
        "caption_lines": lines,
        "caption_language": (timedtext or {}).get("language"),
        "caption_track_kind": (timedtext or {}).get("track_kind"),
        "caption_body_error": None if lines else (timedtext or {}).get("error"),
        "asr_status": "not_collected",
        "asr": None,
        "transcript": None,
        "ownership": ownership,
        "source": "youtube_data_api",
    }


def bind_uploads_to_posts(
    posts: list[Mapping[str, Any]],
    videos: list[Mapping[str, Any]],
    *,
    ownership: str,
    comments_by_video: Mapping[str, Mapping[str, Any]] | None = None,
    tracks_by_video: Mapping[str, list] | None = None,
    timedtext_by_video: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Zip catalog posts to channel uploads. Extra posts are omitted, not filled from topic search."""

    comments_by_video = comments_by_video or {}
    tracks_by_video = tracks_by_video or {}
    timedtext_by_video = timedtext_by_video or {}
    bound: dict[str, dict[str, Any]] = {}
    for post, video in zip(posts, videos):
        video_id = str(video.get("video_id") or "")
        post_id = str(post.get("post_id") or "")
        if not post_id or not video_id:
            continue
        bound[post_id] = overlay_clip_from_upload(
            post,
            video,
            ownership=ownership,
            comments=comments_by_video.get(video_id),
            tracks=tracks_by_video.get(video_id),
            timedtext=timedtext_by_video.get(video_id),
        )
    return bound
