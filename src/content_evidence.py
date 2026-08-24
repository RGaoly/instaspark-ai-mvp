"""Labeled demo content clips. Timestamps are authored, not ASR.

Live ingest, speech-to-text and comment mining are out of this demo. Each clip
keeps a synthetic URL plus operator-authored timestamps mapped to Product DNA
claim ids.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTENT_PATH = ROOT / "data" / "creator_content.json"


def load_creator_content(path: str | Path = DEFAULT_CONTENT_PATH) -> list[dict[str, Any]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Creator content must be a JSON array.")
    posts = []
    ids: list[str] = []
    for item in raw:
        post_id = str(item.get("post_id") or "").strip()
        creator_id = str(item.get("creator_id") or "").strip()
        url = str(item.get("url") or "").strip()
        timestamps = item.get("timestamps") or []
        if not post_id or not creator_id or not url:
            raise ValueError("Each content row needs post_id, creator_id and url.")
        if not isinstance(timestamps, list) or not timestamps:
            raise ValueError(f"{post_id} needs at least one labeled timestamp.")
        for stamp in timestamps:
            if not str(stamp.get("t") or "").strip() or not str(stamp.get("label") or "").strip():
                raise ValueError(f"{post_id} timestamps need t and label.")
        if item.get("asr") not in (None, ""):
            raise ValueError(f"{post_id} must not claim ASR; set asr to null.")
        ids.append(post_id)
        posts.append(dict(item))
    if len(ids) != len(set(ids)):
        raise ValueError("Content post_id values must be unique.")
    return posts


def content_by_creator(
    posts: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for post in posts if posts is not None else load_creator_content():
        grouped[str(post.get("creator_id"))].append(dict(post))
    return dict(grouped)


def clips_for(creator_id: str, posts: Iterable[Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    return content_by_creator(posts).get(str(creator_id), [])
