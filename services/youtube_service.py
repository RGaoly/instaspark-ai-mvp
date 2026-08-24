"""Optional YouTube Data API v3 client for public channel lookup.

This is a labeled live lookup, not a replacement for the governed catalog.
When YOUTUBE_API_KEY is absent, callers receive an empty result with a
clear reason so the UI never pretends the catalog is a platform feed.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from infra.config import YOUTUBE_API_TIMEOUT_SECONDS, _resolve_secret

logger = logging.getLogger(__name__)

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

# Tests monkeypatch this name. None means resolve live (st.secrets → env → dotenv).
YOUTUBE_API_KEY: str | None = None


def _youtube_api_key() -> str:
    if YOUTUBE_API_KEY is not None:
        return str(YOUTUBE_API_KEY).strip()
    return _resolve_secret("YOUTUBE_API_KEY", "")


def is_youtube_available() -> bool:
    return bool(_youtube_api_key())


def youtube_status_label() -> str:
    return "YouTube Data API live" if is_youtube_available() else "YouTube lookup off"


def _request(path: str, params: dict[str, str]) -> dict[str, Any]:
    query = urllib.parse.urlencode({**params, "key": _youtube_api_key()})
    url = f"{YOUTUBE_API_BASE}/{path}?{query}"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "InstaSparkAI/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=YOUTUBE_API_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        logger.warning("YouTube API HTTP %s: %s", exc.code, detail[:300])
        raise RuntimeError(f"YouTube API HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        logger.warning("YouTube API unreachable: %s", exc)
        raise RuntimeError("YouTube API unreachable") from exc


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def search_channels(query: str, *, max_results: int = 6) -> dict[str, Any]:
    """Search public YouTube channels. Never invents rows when the key is missing."""

    cleaned = " ".join(str(query).split())
    if not cleaned:
        return {
            "source": "youtube_data_api",
            "available": is_youtube_available(),
            "query": "",
            "items": [],
            "error": "Enter a search query.",
        }
    if not is_youtube_available():
        return {
            "source": "youtube_data_api",
            "available": False,
            "query": cleaned,
            "items": [],
            "error": "YOUTUBE_API_KEY is not configured. Ranking below stays the demo catalog.",
        }

    try:
        search_payload = _request(
            "search",
            {
                "part": "snippet",
                "type": "channel",
                "q": cleaned,
                "maxResults": str(max(1, min(max_results, 10))),
            },
        )
        channel_ids = [
            str(item.get("snippet", {}).get("channelId") or item.get("id", {}).get("channelId") or "")
            for item in search_payload.get("items", [])
        ]
        channel_ids = [item for item in channel_ids if item]
        stats_by_id: dict[str, dict[str, Any]] = {}
        if channel_ids:
            stats_payload = _request(
                "channels",
                {
                    "part": "snippet,statistics",
                    "id": ",".join(channel_ids),
                },
            )
            for item in stats_payload.get("items", []):
                stats_by_id[str(item.get("id", ""))] = item

        items: list[dict[str, Any]] = []
        for channel_id in channel_ids:
            record = stats_by_id.get(channel_id, {})
            snippet = record.get("snippet") or {}
            stats = record.get("statistics") or {}
            hidden = bool(stats.get("hiddenSubscriberCount"))
            items.append(
                {
                    "channel_id": channel_id,
                    "title": snippet.get("title") or channel_id,
                    "description": (snippet.get("description") or "")[:280],
                    "country": snippet.get("country") or "Not declared",
                    "subscriber_count": None if hidden else _as_int(stats.get("subscriberCount")),
                    "video_count": _as_int(stats.get("videoCount")),
                    "url": f"https://www.youtube.com/channel/{channel_id}",
                    "source": "youtube_data_api",
                }
            )
        return {
            "source": "youtube_data_api",
            "available": True,
            "query": cleaned,
            "items": items,
            "error": None,
        }
    except RuntimeError as exc:
        return {
            "source": "youtube_data_api",
            "available": True,
            "query": cleaned,
            "items": [],
            "error": str(exc),
        }


def captions_for_channel(channel_id: str) -> dict[str, Any]:
    """List caption tracks for a channel's latest public video. Never ranks.

    Transcript bodies are not downloaded. Missing keys stay empty with an error.
    """

    cleaned = str(channel_id or "").strip()
    result: dict[str, Any] = {
        "source": "youtube_data_api",
        "available": is_youtube_available(),
        "channel_id": cleaned,
        "video_id": None,
        "items": [],
        "transcript": None,
        "error": None,
        "note": "Caption tracks are listed only. Transcript text is not downloaded. This block never enters ranking.",
    }
    if not cleaned:
        result["error"] = "A live channel_id is required."
        return result
    if not is_youtube_available():
        result["error"] = "YOUTUBE_API_KEY is not configured. Labeled demo layer stays in place."
        return result
    try:
        search_payload = _request(
            "search",
            {
                "part": "snippet",
                "type": "video",
                "channelId": cleaned,
                "maxResults": "1",
                "order": "date",
            },
        )
        video_id = ""
        items = search_payload.get("items") or []
        if items:
            video_id = str((items[0].get("id") or {}).get("videoId") or "")
        result["video_id"] = video_id or None
        if not video_id:
            result["error"] = "No public video found on this channel to list caption tracks."
            return result
        caption_payload = _request("captions", {"part": "snippet", "videoId": video_id})
        tracks = []
        for item in caption_payload.get("items") or []:
            snippet = item.get("snippet") or {}
            tracks.append(
                {
                    "id": item.get("id"),
                    "language": snippet.get("language"),
                    "name": snippet.get("name"),
                    "track_kind": snippet.get("trackKind"),
                    "source": "youtube_data_api",
                }
            )
        result["items"] = tracks
        if not tracks:
            result["error"] = "API returned no caption tracks for the latest public video."
        return result
    except RuntimeError as exc:
        result["error"] = str(exc)
        return result
