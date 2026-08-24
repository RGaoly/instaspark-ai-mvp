"""Labeled demo content clips. Timestamps are authored, not ASR.

Live ingest, speech-to-text and comment mining are out of this demo. Each clip
keeps a synthetic URL plus operator-authored timestamps mapped to Product DNA
claim ids. A separate versioned pack adds a labeled-demo caption / keyframe /
comment-theme layer. That layer is not Whisper, not YouTube captions, not OCR.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTENT_PATH = ROOT / "data" / "creator_content.json"
DEFAULT_DEEP_READ_PATH = ROOT / "data" / "creator_content_deep_read.json"

CLAIM_IDS = {"all_day", "pov", "rugged", "360"}
LABELED_CAPTION_SOURCE = "labeled_demo"
LABELED_KEYFRAME_STATUS = "labeled_demo_note"
LABELED_COMMENT_STATUS = "labeled_demo_themes"
FORBIDDEN_COLLECTION_CLAIMS = frozenset(
    {
        "asr_collected",
        "whisper",
        "whisper_asr",
        "youtube_captions",
        "youtube_caption",
        "scraped_comments",
        "ocr_collected",
    }
)


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _reject_invented_collection(post_id: str, field: str, value: Any) -> None:
    token = _as_text(value).lower().replace("-", "_").replace(" ", "_")
    if token in FORBIDDEN_COLLECTION_CLAIMS:
        raise ValueError(
            f"{post_id} field {field}={value!r} claims a collected pipeline this demo does not run."
        )


def load_deep_read_pack(path: str | Path = DEFAULT_DEEP_READ_PATH) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Deep-read pack must be a JSON object.")
    pack_id = _as_text(raw.get("pack_id"))
    version = raw.get("version")
    layer = _as_text(raw.get("layer"))
    clips = raw.get("clips")
    if not pack_id:
        raise ValueError("Deep-read pack requires pack_id.")
    if not isinstance(version, int) or version < 1:
        raise ValueError("Deep-read pack version must be a positive integer.")
    if layer != LABELED_CAPTION_SOURCE:
        raise ValueError("Deep-read pack layer must be labeled_demo.")
    if not isinstance(clips, list) or not clips:
        raise ValueError("Deep-read pack requires clips.")
    ids: list[str] = []
    for item in clips:
        post_id = _as_text(item.get("post_id"))
        if not post_id:
            raise ValueError("Every deep-read clip needs post_id.")
        _reject_invented_collection(post_id, "caption_source", item.get("caption_source"))
        _reject_invented_collection(post_id, "keyframe_status", item.get("keyframe_status"))
        _reject_invented_collection(post_id, "comment_status", item.get("comment_status"))
        if item.get("caption_source") != LABELED_CAPTION_SOURCE:
            raise ValueError(f"{post_id} caption_source must be {LABELED_CAPTION_SOURCE}.")
        if item.get("keyframe_status") != LABELED_KEYFRAME_STATUS:
            raise ValueError(f"{post_id} keyframe_status must be {LABELED_KEYFRAME_STATUS}.")
        if item.get("comment_status") != LABELED_COMMENT_STATUS:
            raise ValueError(f"{post_id} comment_status must be {LABELED_COMMENT_STATUS}.")
        themes = [str(theme).strip() for theme in (item.get("comment_themes") or []) if str(theme).strip()]
        if not 1 <= len(themes) <= 3:
            raise ValueError(f"{post_id} needs 1–3 catalog comment themes.")
        if any("scraped comment" in theme.lower() and "not scraped" not in theme.lower() for theme in themes):
            raise ValueError(f"{post_id} comment themes must stay catalog labels, not scraped comments.")
        stamps = item.get("stamps") or []
        if not isinstance(stamps, list) or not stamps:
            raise ValueError(f"{post_id} deep-read stamps are required.")
        for stamp in stamps:
            _reject_invented_collection(post_id, "stamp.caption_source", stamp.get("caption_source"))
            if not _as_text(stamp.get("t")) or not _as_text(stamp.get("claim_id")):
                raise ValueError(f"{post_id} deep-read stamps need t and claim_id.")
            if _as_text(stamp.get("claim_id")) not in CLAIM_IDS:
                raise ValueError(f"{post_id} stamp claim_id is not a Product DNA claim.")
            if not _as_text(stamp.get("caption")) or not _as_text(stamp.get("keyframe_note")):
                raise ValueError(f"{post_id} stamps need labeled caption and keyframe_note.")
            lowered = f"{stamp.get('caption')} {stamp.get('keyframe_note')}".lower()
            if "whisper" in lowered or "asr output" in lowered:
                raise ValueError(f"{post_id} labeled caption must not pose as Whisper/ASR output.")
        ids.append(post_id)
    if len(ids) != len(set(ids)):
        raise ValueError("Deep-read post_id values must be unique.")
    return raw


def _merge_deep_read(post: dict[str, Any], layer: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(post)
    merged["deep_read_pack_id"] = layer.get("pack_id")
    merged["deep_read_version"] = layer.get("version")
    merged["caption_source"] = layer["caption_source"]
    merged["keyframe_status"] = layer["keyframe_status"]
    merged["comment_status"] = layer["comment_status"]
    merged["comment_themes"] = list(layer["comment_themes"])
    by_key = {
        (_as_text(stamp.get("t")), _as_text(stamp.get("claim_id"))): stamp
        for stamp in layer.get("stamps") or []
    }
    stamps = []
    for stamp in merged.get("timestamps") or []:
        row = dict(stamp)
        extra = by_key.get((_as_text(row.get("t")), _as_text(row.get("claim_id"))))
        if extra is None:
            raise ValueError(f"{merged.get('post_id')} timestamp {row.get('t')} missing labeled-demo layer.")
        row["caption"] = extra["caption"]
        row["keyframe_note"] = extra["keyframe_note"]
        row["caption_source"] = LABELED_CAPTION_SOURCE
        stamps.append(row)
    merged["timestamps"] = stamps
    return merged


def load_creator_content(
    path: str | Path = DEFAULT_CONTENT_PATH,
    *,
    deep_read_path: str | Path = DEFAULT_DEEP_READ_PATH,
) -> list[dict[str, Any]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Creator content must be a JSON array.")
    pack = load_deep_read_pack(deep_read_path)
    layers = {str(item["post_id"]): item for item in pack["clips"]}
    posts = []
    ids: list[str] = []
    for item in raw:
        post_id = _as_text(item.get("post_id"))
        creator_id = _as_text(item.get("creator_id"))
        url = _as_text(item.get("url"))
        timestamps = item.get("timestamps") or []
        if not post_id or not creator_id or not url:
            raise ValueError("Each content row needs post_id, creator_id and url.")
        if not isinstance(timestamps, list) or not timestamps:
            raise ValueError(f"{post_id} needs at least one labeled timestamp.")
        for stamp in timestamps:
            if not _as_text(stamp.get("t")) or not _as_text(stamp.get("label")):
                raise ValueError(f"{post_id} timestamps need t and label.")
            if _as_text(stamp.get("claim_id")) not in CLAIM_IDS:
                raise ValueError(f"{post_id} timestamps need a Product DNA claim_id.")
        if item.get("asr") not in (None, ""):
            raise ValueError(f"{post_id} must not claim ASR; set asr to null.")
        if item.get("asr_status") != "not_collected":
            raise ValueError(f"{post_id} asr_status must stay not_collected.")
        _reject_invented_collection(post_id, "asr_status", item.get("asr_status"))
        _reject_invented_collection(post_id, "caption_source", item.get("caption_source"))
        layer = layers.get(post_id)
        if layer is None:
            raise ValueError(f"{post_id} is missing from the labeled-demo deep-read pack.")
        merged = _merge_deep_read(dict(item), {**layer, "pack_id": pack["pack_id"], "version": pack["version"]})
        ids.append(post_id)
        posts.append(merged)
    if len(ids) != len(set(ids)):
        raise ValueError("Content post_id values must be unique.")
    if set(layers) != set(ids):
        extra = sorted(set(layers) - set(ids))
        raise ValueError(f"Deep-read pack has clips with no catalog row: {', '.join(extra[:5])}")
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
