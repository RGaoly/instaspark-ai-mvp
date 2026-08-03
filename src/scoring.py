from __future__ import annotations

from typing import Iterable
import pandas as pd

DEFAULT_WEIGHTS = {
    "content_fit": 0.30,
    "audience_fit": 0.20,
    "momentum": 0.15,
    "commercial_fit": 0.15,
    "brand_safety": 0.20,
}


def _overlap_score(items: Iterable[str], targets: Iterable[str]) -> float:
    item_set = {str(x).strip().lower() for x in items if str(x).strip()}
    target_set = {str(x).strip().lower() for x in targets if str(x).strip()}
    return len(item_set & target_set) / len(target_set) if target_set else 0.0


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


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


def score_creator(row: pd.Series, mission: dict, weights: dict | None = None) -> dict:
    weights = weights or DEFAULT_WEIGHTS
    topic_fit = _overlap_score(row["topics"], mission["target_topics"])
    style_fit = _overlap_score(row["styles"], mission["target_styles"])
    content_fit = 100 * (0.65 * topic_fit + 0.35 * style_fit)

    market_fit = 1.0 if mission["market"] in row["markets"] else 0.0
    language_fit = 1.0 if mission["language"] in row["languages"] else 0.0
    audience_fit = 100 * (0.65 * market_fit + 0.35 * language_fit)

    momentum = _clamp(55 + 6 * float(row["engagement_rate"]) + 15 * float(row["posting_consistency"]) - 20 * float(row["recent_decline"]))

    cost_ratio = float(row["estimated_cost_usd"]) / float(mission["max_cost_usd"])
    cost_score = _clamp(120 - 80 * cost_ratio)
    commercial_fit = _clamp(0.55 * cost_score + 25 * float(row["collaboration_openness"]) + 20 * float(row["historical_reliability"]))
    brand_safety = _clamp(float(row["brand_safety_score"]))

    total = (
        content_fit * weights["content_fit"]
        + audience_fit * weights["audience_fit"]
        + momentum * weights["momentum"]
        + commercial_fit * weights["commercial_fit"]
        + brand_safety * weights["brand_safety"]
    )

    positives = []
    if topic_fit >= 0.5:
        positives.append("内容主题与产品场景高度重合")
    if style_fit >= 0.5:
        positives.append("内容表达方式适合展示产品卖点")
    if float(row["engagement_rate"]) >= 3.5:
        positives.append("近期互动表现较强")
    if float(row["historical_reliability"]) >= 0.8:
        positives.append("历史履约可靠")
    if float(row["estimated_cost_usd"]) <= float(mission["max_cost_usd"]) * 0.7:
        positives.append("成本处于预算友好区间")

    warnings = list(row["risks"])
    if float(row["recent_decline"]) >= 0.5:
        warnings.append("近期表现存在下滑")
    if float(row["estimated_cost_usd"]) > float(mission["max_cost_usd"]) * 0.9:
        warnings.append("报价接近预算上限")
    if not warnings:
        warnings.append("需人工确认档期、竞品排他与素材授权")

    return {
        "content_fit": round(content_fit, 1),
        "audience_fit": round(audience_fit, 1),
        "momentum": round(momentum, 1),
        "commercial_fit": round(commercial_fit, 1),
        "brand_safety": round(brand_safety, 1),
        "total_score": round(total, 1),
        "positives": positives or ["具备基础匹配条件，需进一步人工核验"],
        "warnings": warnings,
    }


def rank_creators(df: pd.DataFrame, mission: dict, weights: dict | None = None) -> pd.DataFrame:
    records = []
    for _, row in df.iterrows():
        passed, gate_reasons = passes_hard_gates(row, mission)
        if passed:
            records.append({**row.to_dict(), **score_creator(row, mission, weights), "gate_reasons": gate_reasons})
    if not records:
        return pd.DataFrame()
    result = pd.DataFrame(records)
    return result.sort_values(by=["total_score", "brand_safety", "engagement_rate"], ascending=[False, False, False]).reset_index(drop=True)
