"""Offline claim-evidence benchmark: keyword baseline vs Evidence Reader.

The gold set is operator-read public timedtext, not model output. The baseline
is a keyword matcher over the same caption lines. The model arm reads the
cached Evidence Reader pack. Metrics are precision / recall / F1 plus
quote-grounding accuracy (predicted-positive quotes that are a verbatim
substring of one caption line or two adjacent caption lines).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.evidence_reader import (
    CAPTION_SOURCE,
    EXTRACTOR,
    PROMPT_VERSION,
    caption_lines_of,
    extractions_by_post_id,
    load_pack,
    model_available,
)
from src.product_dna import claim_ids, load_product_dna
from src.retrieval import tokenize
from src.youtube_clips import load_youtube_intensive_clips

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD_PATH = ROOT / "data" / "gold_evidence_labels.json"
DEFAULT_REPORT_PATH = ROOT / "data" / "benchmark_report.json"

PACK_ID = "benchmark_x5_v1"
PACK_VERSION = 1

# Honest "no AI" arm. Tokens are drawn from the DNA claim text and scenes.
# ``360`` is a whole token so ``Insta360`` does not match, but ``Insta 360`` does.
CLAIM_KEYWORDS: dict[str, tuple[str, ...]] = {
    "all_day": ("all-day", "sunrise", "daylight", "battery"),
    "pov": ("pov", "handlebar", "mouthmount"),
    "rugged": ("wet", "dusty", "splash", "rain", "surfing", "surf"),
    "360": ("360", "surround"),
}

ARM_BASELINE = "keyword_baseline"
ARM_MODEL = "evidence_reader"
STATUS_OK = "ok"
STATUS_NOT_RUN = "not_run_no_model"
STATUS_NO_CACHE = "not_run_no_extracted_cache"


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def load_gold(path: str | Path = DEFAULT_GOLD_PATH) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Gold set must be a JSON object.")
    if _as_text(raw.get("method")) != "manual_read":
        raise ValueError("Gold set method must be manual_read.")
    labels = raw.get("labels")
    if not isinstance(labels, list) or not labels:
        raise ValueError("Gold set requires labels.")
    n_claims = 0
    for row in labels:
        claims = row.get("claims") or []
        if not isinstance(claims, list) or not claims:
            raise ValueError("Every gold row needs claims.")
        n_claims += len(claims)
        for item in claims:
            if not _as_text(item.get("claim_id")):
                raise ValueError("Every gold claim needs claim_id.")
            if bool(item.get("supported")) and not (_as_text(item.get("quote")) and _as_text(item.get("timestamp"))):
                raise ValueError("A supported gold claim needs a quote and timestamp from the caption.")
    expected = int(raw.get("n_claim_labels") or 0)
    if expected and expected != n_claims:
        raise ValueError(f"Gold n_claim_labels {expected} does not match {n_claims} claim rows.")
    return raw


def _clip_index() -> dict[str, dict[str, Any]]:
    pack = load_youtube_intensive_clips()
    return {_as_text(clip.get("post_id")): dict(clip) for clip in pack.get("clips") or []}


def keyword_predictions(clip: Mapping[str, Any], allowed: Sequence[str]) -> list[dict[str, Any]]:
    """Keyword/token overlap over real caption lines. Not an LLM."""

    lines = caption_lines_of(clip)
    found: list[dict[str, Any]] = []
    for claim_id in allowed:
        keywords = CLAIM_KEYWORDS.get(claim_id, ())
        hit = None
        for line in lines:
            tokens = set(tokenize(line.get("text") or ""))
            if any(token in tokens for token in keywords):
                hit = line
                break
        if hit is None:
            continue
        found.append(
            {
                "claim_id": claim_id,
                "supported": True,
                "quote": hit["text"],
                "timestamp": hit["t"],
                "source": ARM_BASELINE,
            }
        )
    return found


def model_predictions(post_id: str, pack: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    row = extractions_by_post_id(pack).get(_as_text(post_id)) or {}
    if _as_text(row.get("status")) != "extracted":
        return []
    return [
        {
            "claim_id": _as_text(item.get("claim_id")),
            "supported": True,
            "quote": _as_text(item.get("quote")),
            "timestamp": _as_text(item.get("timestamp")),
            "source": ARM_MODEL,
        }
        for item in row.get("claims") or []
        if item.get("supported") and _as_text(item.get("claim_id"))
    ]


def prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def _grounding_hits(preds: Sequence[Mapping[str, Any]], lines: Sequence[Mapping[str, Any]]) -> tuple[int, int]:
    texts = [_as_text(item.get("text")) for item in lines]
    adjacent = [f"{left} {right}" for left, right in zip(texts, texts[1:])]
    ok = 0
    n = 0
    for item in preds:
        quote = _as_text(item.get("quote"))
        if not quote:
            continue
        n += 1
        if any(quote in text for text in texts) or any(quote in text for text in adjacent):
            ok += 1
    return ok, n


def score_arm(
    gold: Mapping[str, Any],
    *,
    arm: str,
    predictions: Mapping[str, list[dict[str, Any]]],
    clips: Mapping[str, Mapping[str, Any]],
    status: str,
    model: str = "",
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    tp = fp = fn = 0
    grounded_ok = grounded_n = 0
    for row in gold.get("labels") or []:
        post_id = _as_text(row.get("post_id"))
        preds = {item["claim_id"]: item for item in predictions.get(post_id, [])}
        lines = caption_lines_of(clips.get(post_id) or {})
        ok, n = _grounding_hits(list(preds.values()), lines)
        grounded_ok += ok
        grounded_n += n
        for item in row.get("claims") or []:
            claim_id = _as_text(item.get("claim_id"))
            gold_pos = bool(item.get("supported"))
            pred_pos = claim_id in preds
            if gold_pos and pred_pos:
                tp += 1
            elif pred_pos and not gold_pos:
                fp += 1
            elif gold_pos and not pred_pos:
                fn += 1
    metrics = prf(tp, fp, fn)
    metrics["quote_grounding_accuracy"] = round(grounded_ok / grounded_n, 4) if grounded_n else 1.0
    metrics["grounded_quotes"] = grounded_ok
    metrics["predicted_quotes"] = grounded_n
    return {
        "arm": arm,
        "status": status,
        "n_clips": int(gold.get("n_clips") or len(gold.get("labels") or [])),
        "n_claims": int(gold.get("n_claim_labels") or 0),
        "model": model,
        "prompt_version": PROMPT_VERSION if arm == ARM_MODEL else "",
        "caption_source": CAPTION_SOURCE,
        "metrics": metrics,
        **dict(extra or {}),
    }


def run_benchmark(
    *,
    gold_path: str | Path = DEFAULT_GOLD_PATH,
    extractions_path: str | Path | None = None,
) -> dict[str, Any]:
    gold = load_gold(gold_path)
    dna = load_product_dna()
    allowed = claim_ids(dna)
    clips = _clip_index()
    baseline_preds: dict[str, list[dict[str, Any]]] = {}
    for row in gold.get("labels") or []:
        post_id = _as_text(row.get("post_id"))
        baseline_preds[post_id] = keyword_predictions(clips.get(post_id) or {}, allowed)

    pack = load_pack(extractions_path) if extractions_path else load_pack()
    extracted = int((pack.get("coverage") or {}).get("extracted") or 0)
    if extracted:
        model_status = STATUS_OK
        model_preds = {
            _as_text(row.get("post_id")): model_predictions(_as_text(row.get("post_id")), pack)
            for row in gold.get("labels") or []
        }
        model_name = _as_text(pack.get("model"))
    elif not model_available():
        model_status = STATUS_NOT_RUN
        model_preds = {}
        model_name = ""
    else:
        model_status = STATUS_NO_CACHE
        model_preds = {}
        model_name = _as_text(pack.get("model"))

    arms = [
        score_arm(gold, arm=ARM_BASELINE, predictions=baseline_preds, clips=clips, status=STATUS_OK),
        score_arm(
            gold,
            arm=ARM_MODEL,
            predictions=model_preds,
            clips=clips,
            status=model_status,
            model=model_name,
            extra={"extractor": EXTRACTOR, "extraction_pack_id": _as_text(pack.get("pack_id"))},
        ),
    ]
    return {
        "pack_id": PACK_ID,
        "version": PACK_VERSION,
        "gold_pack_id": _as_text(gold.get("pack_id")),
        "gold_n_clips": int(gold.get("n_clips") or 0),
        "gold_method": _as_text(gold.get("method")),
        "dna_id": _as_text(gold.get("dna_id")),
        "run_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Gold labels are manual_read of public timedtext. Baseline is keyword overlap. "
            "Model arm is the Evidence Reader cache. Ranking is untouched. Not a customer ROI."
        ),
        "arms": arms,
    }


def save_report(report: Mapping[str, Any], path: str | Path = DEFAULT_REPORT_PATH) -> Path:
    target = Path(path)
    target.write_text(json.dumps(dict(report), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def load_report(path: str | Path = DEFAULT_REPORT_PATH) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {
            "pack_id": "",
            "version": 0,
            "arms": [],
            "note": "No benchmark report. Run scripts/run_benchmark.py.",
        }
    raw = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("arms"), list):
        raise ValueError("Benchmark report must be an object with arms.")
    return raw
