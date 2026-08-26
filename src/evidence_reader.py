"""Evidence Reader Agent. Model-grounded DNA claim extraction from public captions.

The agent reads real public YouTube timedtext lines (``caption_body_status ==
downloaded_public_timedtext``) together with the Product DNA claim set and asks
the configured LLM which claims the clip actually demonstrates. Every returned
quote is validated against the supplied caption lines before it is kept:

* a quote that is not a verbatim substring of one supplied caption line, or of
  two adjacent caption lines joined with a space, is dropped
* a timestamp that is not one of the supplied caption timestamps is dropped

There is no keyword fallback. Without a model key the agent returns
``unavailable_no_model`` so the operator sees an honest blocked state instead of
rule output dressed up as extraction. ``labeled_demo`` captions are never read by
this agent; they stay a separate layer.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXTRACTIONS_PATH = ROOT / "data" / "evidence_extractions.json"

PACK_ID = "evidence_reader_x5_v1"
PACK_VERSION = 1
PROMPT_VERSION = "evidence_reader_v2"
EXTRACTOR = "evidence_reader"
CAPTION_SOURCE = "youtube_public_timedtext"
ELIGIBLE_BODY_STATUS = "downloaded_public_timedtext"

STATUS_EXTRACTED = "extracted"
STATUS_NO_MODEL = "unavailable_no_model"
STATUS_ERROR = "error"

MAX_LINES_PER_CALL = 400
MAX_QUOTE_CHARS = 240
MAX_NOTE_CHARS = 200
BRAND_SAFETY_CATEGORIES = frozenset(
    {"profanity", "unsafe_act", "competitor_claim", "medical_claim", "political", "other"}
)
FORBIDDEN_PACK_KEYS = frozenset({"api_key", "llm_api_key", "authorization", "base_url", "llm_base_url", "secret", "token"})

SOURCE_LABEL = f"{CAPTION_SOURCE} + {EXTRACTOR}"

GATE_GROUNDED = "grounded"
GATE_BLOCKED_NO_EVIDENCE = "blocked_no_grounded_evidence"
GATE_BLOCKED_NO_MODEL = "blocked_no_model"
GATE_OVERRIDDEN = "overridden"


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize(value: Any) -> str:
    return " ".join(_as_text(value).split())


def source_label(model: str | None) -> str:
    """Honest per-clip source label: public captions read by a named model."""

    name = _as_text(model)
    return f"{CAPTION_SOURCE} + {EXTRACTOR}({name})" if name else SOURCE_LABEL


# ── Eligibility ──────────────────────────────────────────────────


def caption_lines_of(clip: Mapping[str, Any]) -> list[dict[str, str]]:
    """Real public timedtext lines only. labeled_demo captions are never returned."""

    if _as_text(clip.get("caption_body_status")) != ELIGIBLE_BODY_STATUS:
        return []
    if _as_text(clip.get("caption_body_source")) not in {"", CAPTION_SOURCE}:
        return []
    lines = []
    for item in clip.get("caption_lines") or []:
        stamp = _as_text(item.get("t"))
        text = _normalize(item.get("text"))
        if stamp and text:
            lines.append({"t": stamp, "text": text})
    return lines


def eligible_clips(clips: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(clip) for clip in clips or [] if caption_lines_of(clip)]


# ── Prompt ───────────────────────────────────────────────────────


def build_system_prompt() -> str:
    return (
        "You are an evidence extraction agent for a creator marketing operator. "
        "You read public video caption lines and decide which product claims the clip "
        "actually demonstrates. You never invent quotes. Every quote you output must be "
        "copied verbatim from exactly ONE supplied caption line, and its timestamp must be "
        "that same line's timestamp. If nothing in the captions supports a claim, omit that "
        "claim. Return JSON only, no prose and no code fences, shaped as: "
        '{"claims":[{"claim_id":"","supported":true,"confidence":0.0,"quote":"","timestamp":"MM:SS","note":""}],'
        '"contradictions":[{"quote":"","timestamp":"MM:SS","why":""}],'
        '"brand_safety_flags":[{"quote":"","timestamp":"MM:SS","category":""}]}. '
        "claim_id must be one of the supplied claim ids. confidence is 0-1. note is under 20 words. "
        "category is one of profanity, unsafe_act, competitor_claim, medical_claim, political, other. "
        "Captions may be auto-generated and noisy; that is not a reason to invent text."
    )


def build_user_prompt(dna: Mapping[str, Any], lines: Sequence[Mapping[str, Any]]) -> str:
    claim_rows = []
    for claim in dna.get("claims") or []:
        claim_id = _as_text(claim.get("claim_id"))
        if not claim_id:
            continue
        scenes = ", ".join(_as_text(item) for item in (claim.get("scenes") or [])[:3] if _as_text(item))
        claim_rows.append(
            f"- {claim_id}: {_as_text(claim.get('claim'))}" + (f" (scenes: {scenes})" if scenes else "")
        )
    caption_rows = "\n".join(f"{item['t']}\t{item['text']}" for item in lines[:MAX_LINES_PER_CALL])
    return (
        f"SKU: {_as_text(dna.get('sku'))}\n"
        f"Product DNA claims (use these claim_id values only):\n" + "\n".join(claim_rows) + "\n\n"
        "Caption lines (TIMESTAMP<TAB>TEXT). Quote from one line, verbatim:\n"
        f"{caption_rows}\n"
    )


def _strip_json(text: str) -> str:
    body = _as_text(text)
    if body.startswith("```"):
        body = re.sub(r"^```[a-zA-Z]*\s*", "", body)
        body = re.sub(r"\s*```$", "", body)
    start = body.find("{")
    end = body.rfind("}")
    if start >= 0 and end > start:
        return body[start : end + 1]
    return body


# ── Grounding validator ──────────────────────────────────────────


class GroundingStats(dict):
    """Counters for the grounding validator. Rejections are reported, not hidden.

    The rejection reasons are deliberately separate. A model that honestly reports
    "this clip does not support the claim" is not hallucinating. Two neighbouring
    YouTube caption chunks joined with a space are still transcript. A stitch across
    three or more lines, or an invented sentence, is dropped.
    """

    KEYS = (
        "kept",
        "declared_unsupported",
        "rejected_missing_quote",
        "rejected_hallucinated_quotes",
        "rejected_cross_line_quotes",
        "rejected_unknown_timestamps",
        "rejected_unknown_claim_ids",
        "retimed_quotes",
        "case_normalized_quotes",
        "joined_adjacent_lines",
    )

    def __init__(self) -> None:
        super().__init__({key: 0 for key in self.KEYS})

    def bump(self, key: str, amount: int = 1) -> None:
        self[key] = int(self.get(key, 0)) + amount


def _line_index(lines: Sequence[Mapping[str, Any]]) -> list[tuple[str, str]]:
    return [(_as_text(item.get("t")), _normalize(item.get("text"))) for item in lines or []]


def _spans_multiple_lines(needle: str, index: Sequence[tuple[str, str]]) -> bool:
    """True when the quote only exists once neighbouring caption lines are joined."""

    joined = _normalize(" ".join(text for _, text in index))
    return needle.casefold() in joined.casefold()


def _slice_in(haystack: str, needle: str) -> str | None:
    if needle in haystack:
        start = haystack.find(needle)
        return haystack[start : start + len(needle)]
    folded_hay, folded_needle = haystack.casefold(), needle.casefold()
    start = folded_hay.find(folded_needle)
    if start < 0:
        return None
    return haystack[start : start + len(needle)]


def _adjacent_matches(needle: str, index: Sequence[tuple[str, str]]) -> list[tuple[str, str, str]]:
    """Quotes YouTube split across two neighbouring caption chunks. Still real transcript."""

    found: list[tuple[str, str, str]] = []
    for i in range(len(index) - 1):
        stamp_a, text_a = index[i]
        _, text_b = index[i + 1]
        joined = _normalize(f"{text_a} {text_b}")
        slice_ = _slice_in(joined, needle)
        if slice_ is None:
            continue
        found.append((stamp_a, joined, slice_))
    return found


def ground_quote(
    quote: Any,
    timestamp: Any,
    lines: Sequence[Mapping[str, Any]],
    stats: GroundingStats | None = None,
) -> dict[str, str] | None:
    """Return the grounded quote/timestamp, or None when the quote is not in the captions.

    Preferred match is a single caption line. YouTube timedtext often splits one spoken
    sentence across two neighbouring chunks; that pair, joined with a space, is still
    verbatim transcript and is kept. Three-or-more-line stitches and invented sentences
    are dropped.
    """

    stats = stats if stats is not None else GroundingStats()
    index = _line_index(lines)
    stamps = {stamp for stamp, _ in index if stamp}
    needle = _normalize(quote)[:MAX_QUOTE_CHARS]
    stamp = _as_text(timestamp)
    if not needle:
        stats.bump("rejected_missing_quote")
        return None
    matches = [(line_stamp, text, needle) for line_stamp, text in index if needle in text]
    adjacent = False
    if not matches:
        folded = needle.casefold()
        matches = [
            (line_stamp, text, text[text.casefold().find(folded) : text.casefold().find(folded) + len(needle)])
            for line_stamp, text in index
            if folded in text.casefold()
        ]
        if matches:
            stats.bump("case_normalized_quotes")
    if not matches:
        matches = _adjacent_matches(needle, index)
        if matches:
            adjacent = True
            stats.bump("joined_adjacent_lines")
    if not matches:
        stats.bump(
            "rejected_cross_line_quotes" if _spans_multiple_lines(needle, index) else "rejected_hallucinated_quotes"
        )
        return None
    if stamp and stamp not in stamps:
        stats.bump("rejected_unknown_timestamps")
        return None
    exact = next((item for item in matches if item[0] == stamp), None)
    if exact is None:
        if not adjacent:
            stats.bump("retimed_quotes")
        exact = matches[0]
    return {"quote": exact[2], "timestamp": exact[0], "line_text": exact[1]}


def validate_extraction(
    raw: Mapping[str, Any] | None,
    lines: Sequence[Mapping[str, Any]],
    allowed_claim_ids: Sequence[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], GroundingStats]:
    """Drop every ungrounded claim, contradiction and brand-safety flag."""

    stats = GroundingStats()
    allowed = {str(item) for item in allowed_claim_ids}
    claims: list[dict[str, Any]] = []
    contradictions: list[dict[str, Any]] = []
    flags: list[dict[str, Any]] = []
    if not isinstance(raw, Mapping):
        return claims, contradictions, flags, stats

    seen: set[tuple[str, str, str]] = set()
    for item in raw.get("claims") or []:
        if not isinstance(item, Mapping):
            continue
        claim_id = _as_text(item.get("claim_id"))
        if claim_id not in allowed:
            stats.bump("rejected_unknown_claim_ids")
            continue
        supported = bool(item.get("supported", True))
        if not supported and not _normalize(item.get("quote")):
            # The model was asked to omit unsupported claims but is allowed to say so
            # explicitly. An honest "no evidence here" is not a rejected quote.
            stats.bump("declared_unsupported")
            continue
        grounded = ground_quote(item.get("quote"), item.get("timestamp"), lines, stats)
        if grounded is None:
            continue
        key = (claim_id, grounded["quote"], grounded["timestamp"])
        if key in seen:
            continue
        seen.add(key)
        try:
            confidence = float(item.get("confidence"))
        except (TypeError, ValueError):
            confidence = 0.0
        claims.append(
            {
                "claim_id": claim_id,
                "supported": supported,
                "confidence": round(min(max(confidence, 0.0), 1.0), 2),
                "quote": grounded["quote"],
                "timestamp": grounded["timestamp"],
                "note": _normalize(item.get("note"))[:MAX_NOTE_CHARS],
            }
        )
        stats.bump("kept")

    for item in raw.get("contradictions") or []:
        if not isinstance(item, Mapping):
            continue
        grounded = ground_quote(item.get("quote"), item.get("timestamp"), lines, stats)
        if grounded is None:
            continue
        contradictions.append(
            {
                "quote": grounded["quote"],
                "timestamp": grounded["timestamp"],
                "why": _normalize(item.get("why"))[:MAX_NOTE_CHARS],
            }
        )

    for item in raw.get("brand_safety_flags") or []:
        if not isinstance(item, Mapping):
            continue
        grounded = ground_quote(item.get("quote"), item.get("timestamp"), lines, stats)
        if grounded is None:
            continue
        category = _normalize(item.get("category")).lower().replace(" ", "_").replace("-", "_")
        flags.append(
            {
                "quote": grounded["quote"],
                "timestamp": grounded["timestamp"],
                "category": category if category in BRAND_SAFETY_CATEGORIES else "other",
            }
        )
    return claims, contradictions, flags, stats


# ── Extraction ───────────────────────────────────────────────────


def _default_call(system_prompt: str, user_prompt: str) -> str | None:
    from services.llm_service import _call_llm

    return _call_llm(system_prompt, user_prompt)


def _model_name() -> str:
    from services.llm_service import _llm_model

    return _as_text(_llm_model())


def model_available() -> bool:
    from services.llm_service import is_llm_available

    return bool(is_llm_available())


def _blank_result(clip: Mapping[str, Any], status: str, *, model: str, error: str | None = None) -> dict[str, Any]:
    lines = caption_lines_of(clip)
    return {
        "clip_id": _as_text(clip.get("post_id")),
        "post_id": _as_text(clip.get("post_id")),
        "creator_id": _as_text(clip.get("creator_id")),
        "channel_id": _as_text(clip.get("channel_id")) or None,
        "channel_title": _as_text(clip.get("channel_title")) or None,
        "video_id": _as_text(clip.get("video_id")) or None,
        "url": _as_text(clip.get("url")) or None,
        "caption_language": _as_text(clip.get("caption_language")) or None,
        "caption_source": CAPTION_SOURCE,
        "caption_lines_read": len(lines[:MAX_LINES_PER_CALL]),
        "extractor": EXTRACTOR,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "claims": [],
        "contradictions": [],
        "brand_safety_flags": [],
        "grounding": dict(GroundingStats()),
        "status": status,
        "error": error,
    }


def extract_clip(
    clip: Mapping[str, Any],
    dna: Mapping[str, Any],
    *,
    call: Callable[[str, str], str | None] | None = None,
    model: str | None = None,
    available: bool | None = None,
) -> dict[str, Any]:
    """Extract grounded claim evidence for one clip. Never invents a quote."""

    lines = caption_lines_of(clip)
    resolved_model = _as_text(model) if model is not None else _model_name()
    if not lines:
        raise ValueError(
            f"{_as_text(clip.get('post_id')) or 'clip'} has no public timedtext body; "
            "the Evidence Reader only reads downloaded_public_timedtext captions."
        )
    has_model = model_available() if available is None else bool(available)
    if not has_model:
        return _blank_result(clip, STATUS_NO_MODEL, model="")
    caller = call or _default_call
    try:
        raw_text = caller(build_system_prompt(), build_user_prompt(dna, lines))
    except Exception as exc:  # network, provider, timeout
        return _blank_result(clip, STATUS_ERROR, model=resolved_model, error=type(exc).__name__)
    if raw_text is None or not _as_text(raw_text):
        return _blank_result(clip, STATUS_ERROR, model=resolved_model, error="empty_model_response")
    try:
        parsed = json.loads(_strip_json(str(raw_text)))
    except json.JSONDecodeError:
        return _blank_result(clip, STATUS_ERROR, model=resolved_model, error="invalid_json")
    from src.product_dna import claim_ids

    claims, contradictions, flags, stats = validate_extraction(parsed, lines, claim_ids(dna))
    result = _blank_result(clip, STATUS_EXTRACTED, model=resolved_model)
    result["claims"] = claims
    result["contradictions"] = contradictions
    result["brand_safety_flags"] = flags
    result["grounding"] = dict(stats)
    return result


def extract_pack(
    clips: Iterable[Mapping[str, Any]],
    dna: Mapping[str, Any],
    *,
    call: Callable[[str, str], str | None] | None = None,
    limit: int | None = None,
    workers: int = 1,
    available: bool | None = None,
    model: str | None = None,
    on_result: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run the agent over eligible clips and return a versioned, cacheable pack."""

    pool = eligible_clips(clips)
    eligible_n = len(pool)
    attempted = pool if limit is None else pool[: max(int(limit), 0)]
    has_model = model_available() if available is None else bool(available)
    resolved_model = _as_text(model) if model is not None else _model_name()
    model = resolved_model if has_model else ""

    def run(clip: Mapping[str, Any]) -> dict[str, Any]:
        result = extract_clip(clip, dna, call=call, model=model, available=has_model)
        if on_result is not None:
            on_result(result)
        return result

    if workers > 1 and attempted:
        with ThreadPoolExecutor(max_workers=int(workers)) as pool_exec:
            results = list(pool_exec.map(run, attempted))
    else:
        results = [run(clip) for clip in attempted]

    supported = sum(1 for row in results for claim in row["claims"] if claim["supported"])
    grounded_creators = sorted(
        {row["creator_id"] for row in results for claim in row["claims"] if claim["supported"] and row["creator_id"]}
    )
    coverage = {
        "eligible_clips": eligible_n,
        "attempted_clips": len(attempted),
        "limit": limit,
        "extracted": sum(1 for row in results if row["status"] == STATUS_EXTRACTED),
        "unavailable_no_model": sum(1 for row in results if row["status"] == STATUS_NO_MODEL),
        "error": sum(1 for row in results if row["status"] == STATUS_ERROR),
        "supported_claims": supported,
        "grounded_clips": sum(1 for row in results if any(claim["supported"] for claim in row["claims"])),
        "grounded_creators": len(grounded_creators),
        "contradictions": sum(len(row["contradictions"]) for row in results),
        "brand_safety_flags": sum(len(row["brand_safety_flags"]) for row in results),
        **{
            key: sum(int(row["grounding"].get(key, 0)) for row in results)
            for key in GroundingStats.KEYS
            if key != "kept"
        },
        "rejected_quotes_total": sum(
            int(row["grounding"].get(key, 0))
            for row in results
            for key in (
                "rejected_missing_quote",
                "rejected_hallucinated_quotes",
                "rejected_cross_line_quotes",
                "rejected_unknown_timestamps",
            )
        ),
    }
    return {
        "pack_id": PACK_ID,
        "version": PACK_VERSION,
        "prompt_version": PROMPT_VERSION,
        "extractor": EXTRACTOR,
        "model": model,
        "caption_source": CAPTION_SOURCE,
        "dna_id": _as_text(dna.get("dna_id")),
        "dna_version": dna.get("version"),
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Model-grounded DNA claim evidence read from public YouTube timedtext. "
            "Every quote is validated as a verbatim substring of one caption line or two "
            "adjacent caption lines; ungrounded quotes are dropped, not repaired. Not ASR, "
            "not labeled_demo, not ranking input."
        ),
        "coverage": coverage,
        "grounded_creator_ids": grounded_creators,
        "clips": results,
    }


# ── Cache ────────────────────────────────────────────────────────


def save_pack(pack: Mapping[str, Any], path: str | Path = DEFAULT_EXTRACTIONS_PATH) -> Path:
    target = Path(path)
    blob = dict(pack)
    for key in list(blob):
        if str(key).lower() in FORBIDDEN_PACK_KEYS:
            raise ValueError(f"Extraction pack must not carry {key}.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(blob, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def empty_pack() -> dict[str, Any]:
    return {
        "pack_id": "",
        "version": 0,
        "prompt_version": PROMPT_VERSION,
        "extractor": EXTRACTOR,
        "model": "",
        "caption_source": CAPTION_SOURCE,
        "available": False,
        "coverage": {"eligible_clips": 0, "attempted_clips": 0, "extracted": 0, "supported_claims": 0},
        "clips": [],
        "note": "No Evidence Reader cache. Claim-grounded evidence is unavailable.",
    }


def load_pack(path: str | Path = DEFAULT_EXTRACTIONS_PATH) -> dict[str, Any]:
    """Load the cached pack. A missing file is an honest empty pack, not a fallback."""

    target = Path(path)
    if not target.exists():
        return empty_pack()
    raw = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Evidence extraction pack must be a JSON object.")
    for key in raw:
        if str(key).lower() in FORBIDDEN_PACK_KEYS:
            raise ValueError(f"Extraction pack must not carry {key}.")
    if _as_text(raw.get("extractor")) != EXTRACTOR:
        raise ValueError("Extraction pack extractor must be evidence_reader.")
    if _as_text(raw.get("caption_source")) != CAPTION_SOURCE:
        raise ValueError(f"Extraction pack caption_source must be {CAPTION_SOURCE}.")
    clips = raw.get("clips")
    if not isinstance(clips, list):
        raise ValueError("Extraction pack clips must be an array.")
    cleaned: list[dict[str, Any]] = []
    for item in clips:
        if not isinstance(item, Mapping):
            raise ValueError("Every extraction row must be an object.")
        status = _as_text(item.get("status"))
        if status not in {STATUS_EXTRACTED, STATUS_NO_MODEL, STATUS_ERROR}:
            raise ValueError(f"Extraction status {status!r} is not allowed.")
        row = dict(item)
        row["claims"] = [
            dict(claim)
            for claim in item.get("claims") or []
            if _as_text(claim.get("quote")) and _as_text(claim.get("timestamp")) and _as_text(claim.get("claim_id"))
        ]
        row["contradictions"] = [dict(entry) for entry in item.get("contradictions") or []]
        row["brand_safety_flags"] = [dict(entry) for entry in item.get("brand_safety_flags") or []]
        if status == STATUS_NO_MODEL and row["claims"]:
            raise ValueError("unavailable_no_model rows must not carry claims.")
        cleaned.append(row)
    return {**raw, "clips": cleaned, "available": any(row["status"] == STATUS_EXTRACTED for row in cleaned)}


def extractions_by_post_id(pack: Mapping[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    data = pack if pack is not None else load_pack()
    return {_as_text(row.get("post_id")): dict(row) for row in data.get("clips") or [] if _as_text(row.get("post_id"))}


def supported_claim_rows(pack: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """Flat list of validated supported claims across the pack."""

    data = pack if pack is not None else load_pack()
    rows = []
    for clip in data.get("clips") or []:
        if _as_text(clip.get("status")) != STATUS_EXTRACTED:
            continue
        for claim in clip.get("claims") or []:
            if not claim.get("supported"):
                continue
            rows.append(
                {
                    "creator_id": _as_text(clip.get("creator_id")),
                    "post_id": _as_text(clip.get("post_id")),
                    "channel_id": _as_text(clip.get("channel_id")) or None,
                    "video_id": _as_text(clip.get("video_id")) or None,
                    "url": _as_text(clip.get("url")) or None,
                    "claim_id": _as_text(claim.get("claim_id")),
                    "quote": _as_text(claim.get("quote")),
                    "timestamp": _as_text(claim.get("timestamp")),
                    "confidence": claim.get("confidence"),
                    "note": _as_text(claim.get("note")),
                    "model": _as_text(clip.get("model")),
                    "prompt_version": _as_text(clip.get("prompt_version")),
                    "caption_source": CAPTION_SOURCE,
                    "source_label": source_label(clip.get("model")),
                }
            )
    return rows


def grounded_claims_for_creator(creator_id: str, pack: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    target = _as_text(creator_id)
    return [row for row in supported_claim_rows(pack) if row["creator_id"] == target]


# ── Approval gate ────────────────────────────────────────────────


def gate_state(
    creator_id: str,
    pack: Mapping[str, Any] | None = None,
    *,
    available: bool | None = None,
    override: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Approval gate verdict for one creator. Rules alone can never satisfy it."""

    data = pack if pack is not None else load_pack()
    has_model = model_available() if available is None else bool(available)
    claims = grounded_claims_for_creator(creator_id, data)
    if claims:
        status = GATE_GROUNDED
    elif not has_model:
        status = GATE_BLOCKED_NO_MODEL
    else:
        status = GATE_BLOCKED_NO_EVIDENCE
    blocked = status != GATE_GROUNDED
    if blocked and override:
        status = GATE_OVERRIDDEN
    return {
        "creator_id": _as_text(creator_id),
        "status": status,
        "grounded": bool(claims),
        "blocked": blocked and not override,
        "model_available": has_model,
        "model": _as_text(data.get("model")) if claims else (_model_name() if has_model else ""),
        "prompt_version": _as_text(data.get("prompt_version")) or PROMPT_VERSION,
        "claims": claims,
        "override": dict(override) if override else None,
        "pack_id": _as_text(data.get("pack_id")),
        "source_label": source_label(data.get("model") if claims else None),
    }
