"""Public YouTube timedtext bodies via the player captionTracks URL.

This is not Data API captions.download (OAuth), not Whisper, not a full-video
download. Empty or missing public timedtext stays not_downloaded.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Mapping
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

PLAYER_URL = "https://www.youtube.com/youtubei/v1/player"
TIMEDTEXT_SOURCE = "youtube_public_timedtext"
DOWNLOADED = "downloaded_public_timedtext"
NOT_DOWNLOADED = "not_downloaded"
TIMEOUT_SECONDS = 20
MAX_LINES = 500
ALLOWED_TIMEDTEXT_HOSTS = ("www.youtube.com", "youtube.com")

_ANDROID_CLIENT = {
    "clientName": "ANDROID",
    "clientVersion": "20.10.38",
    "hl": "en",
    "gl": "US",
}
_FALLBACK_CLIENT = {
    "clientName": "TVHTML5_SIMPLY_EMBEDDED_PLAYER",
    "clientVersion": "2.0",
    "hl": "en",
    "gl": "US",
}

_PLAYER_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "com.google.android.youtube/20.10.38 (Linux; U; Android 14) gzip",
}
_GET_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _http_post_json(url: str, payload: dict[str, Any], *, timeout: int = TIMEOUT_SECONDS) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=_PLAYER_HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    if not raw:
        return {}
    parsed = json.loads(raw.decode("utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def _http_get(url: str, *, timeout: int = TIMEOUT_SECONDS) -> bytes:
    request = urllib.request.Request(url, headers=_GET_HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read() or b""


def _seconds_to_stamp(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _clean_caption_text(value: str) -> str:
    text = (
        str(value or "")
        .replace("\xa0", " ")
        .replace("\n", " ")
        .replace("\r", " ")
    )
    return " ".join(text.split()).strip()


def _line(ms: float, text: str) -> dict[str, str] | None:
    cleaned = _clean_caption_text(text)
    if not cleaned:
        return None
    return {"t": _seconds_to_stamp(ms / 1000.0), "text": cleaned[:280]}


def parse_timedtext(raw: bytes | str) -> list[dict[str, str]]:
    """Parse YouTube srv3 XML or json3 caption bodies into timestamped lines."""

    if raw is None:
        return []
    blob = raw.decode("utf-8", errors="replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
    text = blob.strip()
    if not text:
        return []
    if text[0] in "{[":
        return _parse_json3(text)
    return _parse_xml(text)


def _parse_json3(text: str) -> list[dict[str, str]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        return []
    lines: list[dict[str, str]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        segs = event.get("segs") or []
        if not isinstance(segs, list):
            continue
        piece = "".join(str(seg.get("utf8") or "") for seg in segs if isinstance(seg, dict))
        start = event.get("tStartMs")
        try:
            ms = float(start)
        except (TypeError, ValueError):
            continue
        line = _line(ms, piece)
        if line:
            lines.append(line)
        if len(lines) >= MAX_LINES:
            break
    return lines


def _element_text(node: ET.Element) -> str:
    bits = [node.text or ""]
    for child in node:
        bits.append("".join(child.itertext()))
        bits.append(child.tail or "")
    return "".join(bits)


def _parse_xml(text: str) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    lines: list[dict[str, str]] = []
    tag = root.tag.rsplit("}", 1)[-1]
    nodes: list[ET.Element]
    if tag == "transcript":
        nodes = [child for child in root if child.tag.rsplit("}", 1)[-1] == "text"]
        for node in nodes:
            try:
                ms = float(node.attrib.get("start") or 0) * 1000.0
            except (TypeError, ValueError):
                continue
            line = _line(ms, _element_text(node))
            if line:
                lines.append(line)
            if len(lines) >= MAX_LINES:
                break
        return lines
    body = root.find("body")
    parents = list(body) if body is not None else list(root)
    for node in parents:
        if node.tag.rsplit("}", 1)[-1] != "p":
            continue
        try:
            ms = float(node.attrib.get("t") or 0)
        except (TypeError, ValueError):
            continue
        line = _line(ms, _element_text(node))
        if line:
            lines.append(line)
        if len(lines) >= MAX_LINES:
            break
    return lines


def pick_caption_track(
    tracks: list[Mapping[str, Any]] | None,
    listed: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any] | None:
    rows = [dict(item) for item in tracks or [] if isinstance(item, dict) and item.get("baseUrl")]
    if not rows:
        return None
    langs = {
        str(item.get("language") or item.get("languageCode") or "").lower()
        for item in (listed or [])
        if isinstance(item, dict)
    }
    langs.discard("")

    def score(track: dict[str, Any]) -> tuple[int, int, int]:
        lang = str(track.get("languageCode") or "").lower()
        kind = str(track.get("kind") or "").lower()
        standard = 0 if kind == "asr" else 1
        lang_match = 1 if (not langs or lang in langs) else 0
        english = 1 if lang.startswith("en") else 0
        return (standard, lang_match, english)

    return max(rows, key=score)


def _public_timedtext_url(url: str) -> str:
    text = str(url or "").strip()
    parsed = urlparse(text)
    host = parsed.netloc.lower()
    if parsed.scheme != "https" or host not in ALLOWED_TIMEDTEXT_HOSTS:
        return ""
    if "/api/timedtext" not in parsed.path:
        return ""
    return text


def _player_tracks(video_id: str) -> list[dict[str, Any]]:
    for client in (_ANDROID_CLIENT, _FALLBACK_CLIENT):
        payload = _http_post_json(
            PLAYER_URL,
            {"context": {"client": client}, "videoId": video_id},
        )
        tracks = (
            ((payload.get("captions") or {}).get("playerCaptionsTracklistRenderer") or {}).get("captionTracks")
            or []
        )
        if isinstance(tracks, list) and tracks:
            return [item for item in tracks if isinstance(item, dict)]
    return []


def _empty_result(video_id: str, error: str | None) -> dict[str, Any]:
    return {
        "source": TIMEDTEXT_SOURCE,
        "video_id": video_id,
        "caption_body_status": NOT_DOWNLOADED,
        "caption_lines": [],
        "language": None,
        "track_kind": None,
        "error": error,
    }


def fetch_public_timedtext(
    video_id: str,
    listed_tracks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return timestamped public caption lines, or an honest not_downloaded result."""

    cleaned = str(video_id or "").strip()
    if not cleaned:
        return _empty_result("", "video_id is required.")
    try:
        tracks = _player_tracks(cleaned)
    except urllib.error.HTTPError as exc:
        logger.warning("YouTube player timedtext HTTP %s for video", exc.code)
        return _empty_result(cleaned, f"player_http_{exc.code}")
    except urllib.error.URLError:
        logger.warning("YouTube player timedtext unreachable")
        return _empty_result(cleaned, "player_unreachable")
    except (json.JSONDecodeError, RuntimeError, TimeoutError, ValueError):
        return _empty_result(cleaned, "player_invalid")

    chosen = pick_caption_track(tracks, listed_tracks)
    timedtext_url = _public_timedtext_url(str((chosen or {}).get("baseUrl") or ""))
    if not chosen or not timedtext_url:
        return _empty_result(cleaned, "public_timedtext_unavailable")

    try:
        raw = _http_get(timedtext_url)
    except urllib.error.HTTPError as exc:
        try:
            exc.read()
        except Exception:
            pass
        return _empty_result(cleaned, f"http_{exc.code}")
    except urllib.error.URLError:
        return _empty_result(cleaned, "timedtext_unreachable")

    lines = parse_timedtext(raw)
    if not lines:
        return _empty_result(cleaned, "empty_timedtext")

    kind = str(chosen.get("kind") or "").strip() or "standard"
    return {
        "source": TIMEDTEXT_SOURCE,
        "video_id": cleaned,
        "caption_body_status": DOWNLOADED,
        "caption_lines": lines,
        "language": chosen.get("languageCode"),
        "track_kind": kind,
        "error": None,
    }
