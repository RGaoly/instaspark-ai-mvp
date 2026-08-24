"""Public YouTube intensive-read overlay. Never enters ranking.

Cached JSON is the offline source of truth after one fetch. Missing cache
keeps the labeled-demo catalog clips. This overlay does not claim catalog
creators uploaded the videos.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_YOUTUBE_CLIPS_PATH = ROOT / "data" / "youtube_intensive_clips.json"
ALLOWED_THUMB_HOSTS = (".ytimg.com", "i.ytimg.com", "img.youtube.com")


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _public_thumb(url: str) -> str:
    text = _as_text(url)
    host = urlparse(text).netloc.lower()
    if any(host == item or host.endswith(item) for item in ALLOWED_THUMB_HOSTS):
        return text
    return ""


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
        if str(item.get("caption_body_status") or "not_downloaded") != "not_downloaded":
            raise ValueError(f"{post_id} caption bodies must stay not_downloaded.")
        token = str(item.get("keyframe_source") or "")
        if token != "youtube_thumbnail":
            raise ValueError(f"{post_id} keyframe_source must be youtube_thumbnail.")
        if str(item.get("comment_source") or "") != "youtube_data_api":
            raise ValueError(f"{post_id} comment_source must be youtube_data_api.")
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
                "caption_body_status": "not_downloaded",
                "asr_status": "not_collected",
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
    merged["video_id"] = overlay.get("video_id")
    merged["url"] = overlay.get("url") or merged["url"]
    merged["youtube_title"] = overlay.get("title")
    merged["thumbnail_url"] = overlay.get("thumbnail_url")
    merged["keyframe_source"] = "youtube_thumbnail"
    merged["comment_source"] = "youtube_data_api"
    merged["comment_snippets"] = list(overlay.get("comment_snippets") or [])
    merged["youtube_comment_themes"] = list(overlay.get("comment_themes") or [])
    merged["caption_tracks"] = list(overlay.get("caption_tracks") or [])
    merged["caption_body_status"] = "not_downloaded"
    merged["youtube_source"] = "youtube_data_api"
    merged["ownership"] = overlay.get("ownership") or "public_search_hit"
    merged["asr_status"] = "not_collected"
    merged["asr"] = None
    return merged
