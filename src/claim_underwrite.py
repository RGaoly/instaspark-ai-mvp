"""Claim-underwriting: spend is authorized against Product DNA claims, not similarity.

Industry analogue: a credit desk does not lend because a borrower "looks similar"
to last year's book. It underwrites named covenants against documentary evidence.
InstaSpark is that desk for creator spend. The atomic unit is one Product DNA
``claim_id``. A creator is spend-ready only when Evidence Reader has grounded at
least one claim in a verbatim public caption quote.

This is not retrieval and not an LLM ranker. The rule mix (hard gates, commercial
fit, brand safety, sparse TF-IDF) is the Scout constraint layer. The Evidence
Reader cache is the underwriting book. Keyword overlap never mints a claim.
Without a model-produced cache the spend-ready cut is blocked; the catalog can
still be browsed under ``rule_mix_tfidf_v1`` and is labeled as not spend-ready.

YouTube overlay still never enters the ranked catalog as a new creator.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

COVERAGE_WEIGHT = 0.70
RULE_MIX_WEIGHT = 0.30
UNDERWRITE_VERSION = "claim_underwrite_v1"
RULE_MIX_VERSION = "rule_mix_tfidf_v1"
STATUS_GROUNDED = "grounded"
STATUS_UNEVIDENCED = "unevidenced"
STATUS_BLOCKED_NO_AI = "blocked_no_ai"
SAFETY_CATEGORIES = frozenset({"unsafe_act", "competitor_claim", "medical_claim", "political"})


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _unique(items: Iterable[str]) -> tuple[str, ...]:
    seen: list[str] = []
    for item in items:
        text = _as_text(item)
        if text and text not in seen:
            seen.append(text)
    return tuple(seen)


def pack_is_available(pack: Mapping[str, Any] | None) -> bool:
    """True when the cache contains at least one extracted clip. Empty is blocked."""

    data = pack or {}
    if data.get("available") is False:
        return False
    return any(_as_text(row.get("status")) == "extracted" for row in data.get("clips") or [])


def empty_ledger(target_claim_ids: Sequence[str] = ()) -> dict[str, Any]:
    targets = _unique(target_claim_ids)
    return {
        "creator_id": "",
        "target_claim_ids": list(targets),
        "grounded_claim_ids": [],
        "quotes": [],
        "contradictions": [],
        "brand_safety_flags": [],
        "grounded_claim_count": 0,
        "target_claim_count": len(targets),
        "claim_coverage": 0.0,
        "underwrite_status": STATUS_BLOCKED_NO_AI,
    }


def ledger_for_creator(
    creator_id: str,
    pack: Mapping[str, Any] | None,
    target_claim_ids: Sequence[str],
) -> dict[str, Any]:
    """Per-creator underwriting ledger from the Evidence Reader cache."""

    from src.evidence_reader import STATUS_EXTRACTED, grounded_claims_for_creator

    targets = _unique(target_claim_ids)
    available = pack_is_available(pack)
    quotes = grounded_claims_for_creator(creator_id, pack) if pack else []
    grounded = _unique(row.get("claim_id") for row in quotes if _as_text(row.get("claim_id")) in targets)
    contradictions: list[dict[str, Any]] = []
    flags: list[dict[str, Any]] = []
    for clip in (pack or {}).get("clips") or []:
        if _as_text(clip.get("creator_id")) != _as_text(creator_id):
            continue
        if _as_text(clip.get("status")) != STATUS_EXTRACTED:
            continue
        for item in clip.get("contradictions") or []:
            contradictions.append(dict(item))
        for item in clip.get("brand_safety_flags") or []:
            flags.append(dict(item))
    coverage = (100.0 * len(grounded) / len(targets)) if targets else 0.0
    if not available:
        status = STATUS_BLOCKED_NO_AI
    elif grounded:
        status = STATUS_GROUNDED
    else:
        status = STATUS_UNEVIDENCED
    return {
        "creator_id": _as_text(creator_id),
        "target_claim_ids": list(targets),
        "grounded_claim_ids": list(grounded),
        "quotes": quotes,
        "contradictions": contradictions,
        "brand_safety_flags": flags,
        "grounded_claim_count": len(grounded),
        "target_claim_count": len(targets),
        "claim_coverage": round(coverage, 1),
        "underwrite_status": status,
    }


def ledgers_by_creator(
    pack: Mapping[str, Any] | None,
    target_claim_ids: Sequence[str],
    creator_ids: Iterable[str] | None = None,
) -> dict[str, dict[str, Any]]:
    ids = _unique(creator_ids) if creator_ids is not None else _unique(
        row.get("creator_id") for row in (pack or {}).get("clips") or []
    )
    return {creator_id: ledger_for_creator(creator_id, pack, target_claim_ids) for creator_id in ids}


def underwrite_score(claim_coverage: float, rule_mix_score: float) -> float:
    """Spend-ready score: claim coverage is the book, rule mix is the constraint layer."""

    coverage = max(0.0, min(100.0, float(claim_coverage or 0.0)))
    rule = max(0.0, min(100.0, float(rule_mix_score or 0.0)))
    return round(COVERAGE_WEIGHT * coverage + RULE_MIX_WEIGHT * rule, 1)


def attach_underwrite(
    record: Mapping[str, Any],
    ledger: Mapping[str, Any],
    *,
    pack_available: bool,
) -> dict[str, Any]:
    """Merge a ledger onto a scored catalog row. Never mutates the rule-mix total_score."""

    row = dict(record)
    coverage = float(ledger.get("claim_coverage") or 0.0)
    rule_mix = float(row.get("total_score") or 0.0)
    score = underwrite_score(coverage, rule_mix) if pack_available else rule_mix
    status = str(ledger.get("underwrite_status") or STATUS_BLOCKED_NO_AI)
    grounded = list(ledger.get("grounded_claim_ids") or [])
    row["claim_coverage"] = coverage
    row["grounded_claim_ids"] = grounded
    row["grounded_claim_count"] = int(ledger.get("grounded_claim_count") or 0)
    row["target_claim_count"] = int(ledger.get("target_claim_count") or 0)
    row["underwrite_score"] = score
    row["underwrite_status"] = status
    row["spend_ready"] = status == STATUS_GROUNDED
    row["rule_mix_version"] = RULE_MIX_VERSION
    row["ranking_model_version"] = UNDERWRITE_VERSION if pack_available else RULE_MIX_VERSION
    row["match_confidence"] = "claim_underwritten" if pack_available else "deterministic_rule"
    positives = list(row.get("positives") or [])
    if grounded:
        positives.append(
            f"Evidence Reader grounded DNA claim(s) {', '.join(grounded)}"
        )
    elif pack_available:
        positives.append("No grounded Product DNA claim on public captions; not spend-ready")
    safety = [
        item
        for item in ledger.get("brand_safety_flags") or []
        if _as_text(item.get("category")) in SAFETY_CATEGORIES
    ]
    warnings = list(row.get("warnings") or [])
    if safety:
        warnings.append(
            f"Evidence Reader flagged {len(safety)} brand-safety quote(s) on public captions"
        )
    if ledger.get("contradictions"):
        warnings.append(
            f"Evidence Reader recorded {len(ledger['contradictions'])} caption contradiction(s)"
        )
    row["positives"] = positives
    row["warnings"] = warnings
    return row


def display_score(row: Mapping[str, Any]) -> float:
    """Primary number on Search / Compare: underwrite when the book exists."""

    version = _as_text(row.get("ranking_model_version"))
    if version == UNDERWRITE_VERSION:
        return float(row.get("underwrite_score") if row.get("underwrite_score") is not None else row.get("total_score") or 0)
    return float(row.get("total_score") or 0)


def underwrite_driver_display(row: Mapping[str, Any]) -> list[tuple[str, float, str]]:
    grounded = int(row.get("grounded_claim_count") or 0)
    target = int(row.get("target_claim_count") or 0)
    status = _as_text(row.get("underwrite_status")) or STATUS_BLOCKED_NO_AI
    return [
        (
            "Claim coverage",
            float(row.get("claim_coverage") or 0),
            f"{grounded}/{target} DNA claims · {status}",
        ),
        (
            "Underwrite score",
            float(row.get("underwrite_score") or 0),
            f"{COVERAGE_WEIGHT:.0%} coverage + {RULE_MIX_WEIGHT:.0%} rule mix",
        ),
    ]


def claim_matrix(
    rows: Iterable[Mapping[str, Any]],
    target_claim_ids: Sequence[str],
    *,
    pack: Mapping[str, Any] | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Top-N creator × DNA claim grid. Cells are grounded / empty, never invented."""

    targets = list(_unique(target_claim_ids))
    matrix_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if index >= limit:
            break
        creator_id = _as_text(row.get("creator_id"))
        ledger = ledger_for_creator(creator_id, pack, targets) if pack is not None else {
            "grounded_claim_ids": list(row.get("grounded_claim_ids") or []),
            "quotes": [],
        }
        grounded = set(ledger.get("grounded_claim_ids") or [])
        quotes_by_claim: dict[str, dict[str, Any]] = {}
        for quote in ledger.get("quotes") or []:
            claim_id = _as_text(quote.get("claim_id"))
            if claim_id and claim_id not in quotes_by_claim:
                quotes_by_claim[claim_id] = quote
        cells = []
        for claim_id in targets:
            hit = quotes_by_claim.get(claim_id) if claim_id in grounded else None
            cells.append(
                {
                    "claim_id": claim_id,
                    "grounded": claim_id in grounded,
                    "timestamp": _as_text((hit or {}).get("timestamp")) or None,
                    "quote": _as_text((hit or {}).get("quote"))[:120] or None,
                }
            )
        matrix_rows.append(
            {
                "creator_id": creator_id,
                "creator_name": _as_text(row.get("creator_name")) or creator_id,
                "underwrite_score": float(row.get("underwrite_score") or 0),
                "claim_coverage": float(row.get("claim_coverage") or 0),
                "spend_ready": bool(row.get("spend_ready")),
                "cells": cells,
            }
        )
    return {
        "claim_ids": targets,
        "rows": matrix_rows,
        "version": UNDERWRITE_VERSION,
        "note": (
            "Each cell is a Product DNA claim the Evidence Reader grounded in a "
            "verbatim public caption quote, or empty. Keyword overlap is never a cell."
        ),
    }


def unevidenced_spend_usd(rows: Iterable[Mapping[str, Any]], *, n: int = 10) -> float:
    """Estimated catalog cost of the first N rows that have no grounded claim."""

    total = 0.0
    for index, row in enumerate(rows):
        if index >= n:
            break
        if int(row.get("grounded_claim_count") or 0) > 0:
            continue
        total += float(row.get("estimated_cost_usd") or 0)
    return round(total, 2)
