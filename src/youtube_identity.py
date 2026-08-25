"""Honest catalog-name ↔ public channel title matching.

Never silently claims identity. Extra tokens like Dental/Reviews are not a match.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

_STOP = frozenset(
    {
        "official",
        "channel",
        "tv",
        "the",
        "youtube",
        "topic",
        "videos",
        "video",
        "vevo",
    }
)
_ALLOWED_EXTRA = frozenset({"official", "channel", "tv", "youtube", "vlog", "vlogs"})


def _norm_token(part: str) -> str:
    if part in {"vlog", "vlogs"}:
        return "vlog"
    return part


def _tokens(value: str) -> list[str]:
    text = re.sub(r"[^a-z0-9\s]", " ", str(value or "").lower())
    return [_norm_token(part) for part in text.split() if part and part not in _STOP]


def channel_title_matches(catalog_name: str, channel_title: str) -> bool:
    """True only when the public channel title reasonably is the catalog name."""

    title = str(channel_title or "").strip()
    if re.search(r"-\s*topic\s*$", title, flags=re.I):
        return False
    catalog = _tokens(catalog_name)
    channel = _tokens(channel_title)
    if not catalog or not channel:
        return False
    if catalog == channel or "".join(catalog) == "".join(channel):
        return True
    extra = channel[len(catalog) :]
    if channel[: len(catalog)] == catalog and extra and all(token in _ALLOWED_EXTRA for token in extra):
        return True
    return False


def pick_matching_channel(
    catalog_name: str,
    items: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any] | None:
    """First search.list channel whose title matches. None if none reasonably match."""

    for item in items or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "")
        channel_id = str(item.get("channel_id") or "").strip()
        if channel_id and channel_title_matches(catalog_name, title):
            return dict(item)
    return None
