"""Quantified business value from the live catalog, underwriting book, and gold set.

Every number is computed from committed artifacts (catalog costs, Evidence Reader
cache, gold-set benchmark). Process-time hours use a documented assumption, not
an operator interview. This module never invents a customer ROI or a viral lift.
"""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from src.benchmark import load_report
from src.claim_underwrite import (
    RULE_MIX_VERSION,
    UNDERWRITE_VERSION,
    pack_is_available,
    unevidenced_spend_usd,
)
from src.evidence_reader import load_pack
from src.product_dna import claim_ids, load_product_dna
from src.scoring import rank_creators

# Documented time-motion: one public caption body read against the DNA claim set.
# Conservative on purpose — a thorough desk is slower. Labeled as a process model.
SECONDS_PER_CAPTION_BODY = 120
PROCESS_MODEL = (
    f"{SECONDS_PER_CAPTION_BODY} seconds per public caption body against the DNA claim set. "
    "Process-time model, not an operator interview."
)


def _arm_metrics(report: Mapping[str, Any], arm: str) -> dict[str, Any]:
    for item in report.get("arms") or []:
        if item.get("arm") == arm:
            return dict(item.get("metrics") or {})
    return {}


def hours_saved(eligible_clips: int, *, seconds_per_clip: int = SECONDS_PER_CAPTION_BODY) -> float:
    return round(max(0, int(eligible_clips)) * int(seconds_per_clip) / 3600.0, 2)


def compute(
    catalog: pd.DataFrame,
    mission: Mapping[str, Any],
    *,
    pack: Mapping[str, Any] | None = None,
    report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Pilot value board. Formulas are in ``formulas`` so the UI can show the math."""

    book = pack if pack is not None else load_pack()
    gold = report if report is not None else load_report()
    dna = load_product_dna()
    targets = claim_ids(dna)
    coverage = dict(book.get("coverage") or {})
    eligible = int(coverage.get("eligible_clips") or 0)
    extracted = int(coverage.get("extracted") or 0)
    supported = int(coverage.get("supported_claims") or 0)
    grounded_creators = int(coverage.get("grounded_creators") or len(book.get("grounded_creator_ids") or []))
    rejected = int(coverage.get("rejected_quotes_total") or 0)
    available = pack_is_available(book)

    underwritten = rank_creators(catalog, mission, evidence_pack=book)
    rule_only = rank_creators(catalog, mission, evidence_pack=book, sort="rule_mix")
    rule_risk = unevidenced_spend_usd(rule_only.to_dict("records") if not rule_only.empty else [])
    underwrite_risk = unevidenced_spend_usd(
        underwritten.to_dict("records") if not underwritten.empty else []
    )
    spend_blocked = round(max(0.0, rule_risk - underwrite_risk), 2)
    spend_ready_n = int(underwritten.head(10)["spend_ready"].sum()) if not underwritten.empty and "spend_ready" in underwritten else 0
    rule_unevidenced_n = (
        int((rule_only.head(10)["grounded_claim_count"].fillna(0).astype(int) == 0).sum())
        if not rule_only.empty and "grounded_claim_count" in rule_only
        else 0
    )
    underwrite_unevidenced_n = (
        int((underwritten.head(10)["grounded_claim_count"].fillna(0).astype(int) == 0).sum())
        if not underwritten.empty and "grounded_claim_count" in underwritten
        else 0
    )

    keyword = _arm_metrics(gold, "keyword_baseline")
    reader = _arm_metrics(gold, "evidence_reader")
    keyword_fp = int(keyword.get("fp") or 0)
    reader_fp = int(reader.get("fp") or 0)
    fp_reduction = round((keyword_fp - reader_fp) / keyword_fp, 4) if keyword_fp else None
    f1_lift = None
    if keyword.get("f1") is not None and reader.get("f1") is not None:
        f1_lift = round(float(reader["f1"]) - float(keyword["f1"]), 4)

    hours = hours_saved(eligible)
    return {
        "available": available,
        "ranking_model_version": UNDERWRITE_VERSION if available else RULE_MIX_VERSION,
        "dna_id": dna.get("dna_id"),
        "target_claim_ids": list(targets),
        "eligible_clips": eligible,
        "extracted_clips": extracted,
        "supported_claims": supported,
        "grounded_creators": grounded_creators,
        "rejected_ungrounded_quotes": rejected,
        "hours_saved": hours,
        "seconds_per_caption_body": SECONDS_PER_CAPTION_BODY,
        "process_model": PROCESS_MODEL,
        "top10_spend_ready": spend_ready_n,
        "rule_top10_unevidenced_n": rule_unevidenced_n,
        "underwrite_top10_unevidenced_n": underwrite_unevidenced_n,
        "rule_top10_unevidenced_spend_usd": rule_risk,
        "underwrite_top10_unevidenced_spend_usd": underwrite_risk,
        "unevidenced_spend_blocked_usd": spend_blocked,
        "gold_keyword_precision": keyword.get("precision"),
        "gold_reader_precision": reader.get("precision"),
        "gold_keyword_f1": keyword.get("f1"),
        "gold_reader_f1": reader.get("f1"),
        "gold_f1_lift": f1_lift,
        "gold_fp_reduction": fp_reduction,
        "gold_quote_grounding_accuracy": reader.get("quote_grounding_accuracy"),
        "pain": (
            "A hardware launch books creators to demonstrate named SKU claims on camera. "
            "Authorizing spend from a similarity score (followers, topic overlap, embeddings) "
            "puts budget on creators whose public content cannot ground a Product DNA claim."
        ),
        "formulas": [
            "unevidenced_spend = sum(estimated_cost_usd of Top 10 with 0 grounded claims)",
            "spend_blocked = rule_mix Top 10 unevidenced spend − claim-underwrite Top 10 unevidenced spend",
            f"hours_saved = eligible_clips × {SECONDS_PER_CAPTION_BODY}s / 3600",
            "F1 lift = evidence_reader F1 − keyword_baseline F1 on the gold set (manual_read timedtext)",
        ],
        "note": (
            "Hours are a process-time model. Spend uses catalog estimated_cost_usd, not invoices. "
            "Gold-set metrics come from data/benchmark_report.json. Not a customer ROI and not a forecast."
        ),
    }
