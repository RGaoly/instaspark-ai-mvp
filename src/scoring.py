"""Hybrid recall: hard gates + named rule mix + sparse TF-IDF cosine.

``total_score`` is a weighted sum of 0–100 mix drivers, plus three small additive
bonuses, then clamped to 0–100:

    mission_fit      * 0.20   market (65%) + language (35%)
    topic_overlap    * 0.30   Jaccard(mission topics, creator topics ∪ styles)
    momentum         * 0.15   engagement, consistency, recent decline
    commercial_fit   * 0.15   cost vs budget, openness, reliability
    brand_safety     * 0.20   catalog safety score
    + query_boost             0–4 when an NL query token hits name/topics/styles/country
    + live_proof_bonus        +3 only after an operator attaches live YouTube evidence
    + tfidf_boost             0–3 sparse TF-IDF cosine vs mission + Product DNA + Creator Genome (+ query)

Query boost is a lexical filter+boost, not semantic search. TF-IDF cosine is a
real sparse-vector pass, not a neural embedding and not an LLM ranker. Live
YouTube hits never enter the ranked catalog as new creators; the bonus applies
only to a demo-catalog row the operator already selected.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

import pandas as pd

from src.retrieval import TFIDF_BOOST_CAP, tfidf_boosts

RANKING_MODEL_VERSION = "rule_mix_tfidf_v1"

# Mix weights must sum to 1.0. Additive bonuses are documented separately.
DEFAULT_WEIGHTS = {
    "mission_fit": 0.20,
    "topic_overlap": 0.30,
    "momentum": 0.15,
    "commercial_fit": 0.15,
    "brand_safety": 0.20,
}

# Additive caps — not part of the 1.0 mix.
QUERY_BOOST_PER_HIT = 1.0
QUERY_BOOST_CAP = 4.0
LIVE_PROOF_BONUS = 3.0

_WEIGHT_ALIASES = {
    "mission_fit": ("mission_fit", "audience_fit"),
    "topic_overlap": ("topic_overlap", "content_fit"),
}


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _token_set(items: Iterable[str]) -> set[str]:
    return {str(item).strip().lower() for item in items if str(item).strip()}


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = _token_set(left)
    right_set = _token_set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def _overlap_score(items: Iterable[str], targets: Iterable[str]) -> float:
    item_set = _token_set(items)
    target_set = _token_set(targets)
    return len(item_set & target_set) / len(target_set) if target_set else 0.0


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _weight(weights: Mapping[str, float], key: str) -> float:
    for candidate in _WEIGHT_ALIASES.get(key, (key,)):
        if candidate in weights:
            return float(weights[candidate])
    return float(DEFAULT_WEIGHTS[key])


def _query_tokens(query: str) -> list[str]:
    return [token.lower() for token in str(query or "").split() if token.strip()]


def query_boost_for(row: Mapping[str, Any], query: str) -> float:
    """Small additive boost when query tokens hit name / topics / styles / country.

    Empty query returns 0 and must not change ranking vs the unscored baseline.
    This is lexical overlap, not embeddings or an LLM ranker.
    """

    tokens = _query_tokens(query)
    if not tokens:
        return 0.0
    fields = [
        str(row.get("creator_name") or ""),
        " ".join(_as_list(row.get("topics"))),
        " ".join(_as_list(row.get("styles"))),
        str(row.get("primary_market") or ""),
        " ".join(_as_list(row.get("markets"))),
    ]
    hits = 0
    for token in tokens:
        for field in fields:
            if token in field.lower():
                hits += 1
    return min(QUERY_BOOST_CAP, hits * QUERY_BOOST_PER_HIT)


def weight_tag(key: str) -> str:
    return f"w {int(round(_weight(DEFAULT_WEIGHTS, key) * 100))}%"


def mix_driver_display(row: Mapping[str, Any]) -> list[tuple[str, float, str]]:
    """Named mix drivers for Search / Compare. Labels must stay aligned."""

    return [
        ("Mission fit", float(row.get("mission_fit") or row.get("audience_fit") or 0), weight_tag("mission_fit")),
        ("Topic overlap", float(row.get("topic_overlap") or row.get("content_fit") or 0), weight_tag("topic_overlap")),
        ("Momentum", float(row.get("momentum") or 0), weight_tag("momentum")),
        ("Commercial fit", float(row.get("commercial_fit") or 0), weight_tag("commercial_fit")),
        ("Brand safety", float(row.get("brand_safety") or 0), weight_tag("brand_safety")),
    ]


def additive_driver_display(row: Mapping[str, Any]) -> list[tuple[str, float, str]]:
    return [
        ("Query boost", float(row.get("query_boost") or 0), f"cap +{QUERY_BOOST_CAP:g} · lexical filter+boost"),
        ("Live proof bonus", float(row.get("live_proof_bonus") or 0), f"cap +{LIVE_PROOF_BONUS:g} · after attach"),
        ("TF-IDF cosine", float(row.get("tfidf_boost") or 0), f"cap +{TFIDF_BOOST_CAP:g} · sparse vector, not neural"),
    ]


def _default_dna_text() -> str:
    try:
        from src.product_dna import dna_document, load_product_dna

        return dna_document(load_product_dna())
    except (OSError, ValueError):
        return ""


def _genome_texts() -> dict[str, str]:
    try:
        from src.creator_genome import genome_document, genomes_by_id

        return {creator_id: genome_document(item) for creator_id, item in genomes_by_id().items()}
    except (OSError, ValueError):
        return {}


def passes_hard_gates(row: pd.Series, mission: dict) -> tuple[bool, list[str]]:
    reasons = []
    if mission["market"] not in row["markets"]:
        reasons.append("目标市场不匹配")
    if mission["language"] not in row["languages"]:
        reasons.append("语言不匹配")
    if float(row["estimated_cost_usd"]) > float(mission["max_cost_usd"]):
        reasons.append("预计成本超预算")
    if int(row["brand_safety_score"]) < int(mission["min_brand_safety"]):
        reasons.append("品牌安全低于门槛")
    return len(reasons) == 0, reasons


def score_creator(
    row: pd.Series,
    mission: dict,
    weights: dict | None = None,
    *,
    query: str = "",
    has_live_evidence: bool = False,
    tfidf_boost: float = 0.0,
) -> dict:
    weights = weights or DEFAULT_WEIGHTS
    topics = _as_list(row.get("topics"))
    styles = _as_list(row.get("styles"))
    mission_topics = _as_list(mission.get("target_topics"))
    mission_styles = _as_list(mission.get("target_styles"))

    topic_overlap = 100.0 * _jaccard(mission_topics, topics + styles)
    style_coverage = _overlap_score(styles, mission_styles)

    market_fit = 1.0 if mission["market"] in row["markets"] else 0.0
    language_fit = 1.0 if mission["language"] in row["languages"] else 0.0
    mission_fit = 100 * (0.65 * market_fit + 0.35 * language_fit)

    momentum = _clamp(
        55 + 6 * float(row["engagement_rate"]) + 15 * float(row["posting_consistency"]) - 20 * float(row["recent_decline"])
    )

    cost_ratio = float(row["estimated_cost_usd"]) / float(mission["max_cost_usd"])
    cost_score = _clamp(120 - 80 * cost_ratio)
    commercial_fit = _clamp(
        0.55 * cost_score + 25 * float(row["collaboration_openness"]) + 20 * float(row["historical_reliability"])
    )
    brand_safety = _clamp(float(row["brand_safety_score"]))
    query_boost = query_boost_for(row, query)
    live_proof_bonus = LIVE_PROOF_BONUS if has_live_evidence else 0.0
    tfidf_boost = min(TFIDF_BOOST_CAP, max(0.0, float(tfidf_boost or 0.0)))

    total = (
        mission_fit * _weight(weights, "mission_fit")
        + topic_overlap * _weight(weights, "topic_overlap")
        + momentum * _weight(weights, "momentum")
        + commercial_fit * _weight(weights, "commercial_fit")
        + brand_safety * _weight(weights, "brand_safety")
        + query_boost
        + live_proof_bonus
        + tfidf_boost
    )
    total = _clamp(total)

    positives = []
    if topic_overlap >= 50:
        positives.append("内容主题与产品场景高度重合")
    if style_coverage >= 0.5:
        positives.append("内容表达方式适合展示产品卖点")
    if float(row["engagement_rate"]) >= 3.5:
        positives.append("近期互动表现较强")
    if float(row["historical_reliability"]) >= 0.8:
        positives.append("历史履约可靠")
    if float(row["estimated_cost_usd"]) <= float(mission["max_cost_usd"]) * 0.7:
        positives.append("成本处于预算友好区间")
    if query_boost > 0:
        positives.append("Query tokens hit name, topics, styles, or country")
    if has_live_evidence:
        positives.append("Live YouTube evidence attached")
    if tfidf_boost > 0:
        positives.append("TF-IDF cosine with mission/DNA tokens (sparse vector, not neural)")

    warnings = list(row["risks"]) if row.get("risks") is not None else []
    if not isinstance(warnings, list):
        warnings = _as_list(warnings)
    if float(row["recent_decline"]) >= 0.5:
        warnings.append("近期表现存在下滑")
    if float(row["estimated_cost_usd"]) > float(mission["max_cost_usd"]) * 0.9:
        warnings.append("报价接近预算上限")
    if not warnings:
        warnings.append("需人工确认档期、竞品排他与素材授权")

    mission_fit_r = round(mission_fit, 1)
    topic_overlap_r = round(topic_overlap, 1)
    return {
        "mission_fit": mission_fit_r,
        "topic_overlap": topic_overlap_r,
        "audience_fit": mission_fit_r,
        "content_fit": topic_overlap_r,
        "momentum": round(momentum, 1),
        "commercial_fit": round(commercial_fit, 1),
        "brand_safety": round(brand_safety, 1),
        "query_boost": round(query_boost, 1),
        "live_proof_bonus": round(live_proof_bonus, 1),
        "tfidf_boost": round(tfidf_boost, 3),
        "ranking_model_version": RANKING_MODEL_VERSION,
        "match_confidence": "deterministic_rule",
        "total_score": round(total, 1),
        "positives": positives or ["具备基础匹配条件，需进一步人工核验"],
        "warnings": warnings,
    }


def rank_creators(
    df: pd.DataFrame,
    mission: dict,
    weights: dict | None = None,
    *,
    query: str = "",
    live_evidence_ids: Iterable[str] | None = None,
    dna_text: str | None = None,
) -> pd.DataFrame:
    live_ids = {str(item) for item in (live_evidence_ids or []) if str(item).strip()}
    dna = _default_dna_text() if dna_text is None else dna_text
    genome_texts = _genome_texts()
    boosts = (
        tfidf_boosts(df, mission, dna_text=dna, query=query, genome_texts=genome_texts)
        if df is not None and not df.empty
        else {}
    )
    genomes: dict[str, Any] = {}
    try:
        from src.creator_genome import genomes_by_id

        genomes = genomes_by_id()
    except (OSError, ValueError):
        genomes = {}
    records = []
    for _, row in df.iterrows():
        passed, gate_reasons = passes_hard_gates(row, mission)
        if passed:
            creator_id = str(row.get("creator_id", ""))
            scored = score_creator(
                row,
                mission,
                weights,
                query=query,
                has_live_evidence=creator_id in live_ids,
                tfidf_boost=boosts.get(creator_id, 0.0),
            )
            genome = genomes.get(creator_id) or {}
            records.append(
                {
                    **row.to_dict(),
                    **scored,
                    "gate_reasons": gate_reasons,
                    "genome_id": genome.get("genome_id"),
                    "genome_version": genome.get("version"),
                }
            )
    if not records:
        return pd.DataFrame()
    result = pd.DataFrame(records)
    return result.sort_values(
        by=["total_score", "brand_safety", "engagement_rate"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
