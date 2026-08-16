"""Synthetic audience cohorts for shortlist overlap — not platform analytics.

Each creator is mapped to a deterministic set of audience segments derived from
declared markets, languages, topics, styles and follower tier. Pairwise Jaccard
and incremental (marginal) reach are then computed on a shortlist.

This is a modeled proxy so operators can see cannibalization risk. It is not
measured unique-reach from TikTok / Instagram / YouTube.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

_SLUG = re.compile(r"[^a-z0-9]+")


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _slug(value: str) -> str:
    return _SLUG.sub("_", value.strip().lower()).strip("_")


def _follower_tier(followers: int) -> str:
    if followers >= 1_000_000:
        return "mega"
    if followers >= 500_000:
        return "macro"
    if followers >= 100_000:
        return "mid"
    return "micro"


def audience_segments(row: Mapping[str, Any]) -> frozenset[str]:
    """Build a reproducible synthetic cohort for one creator."""

    markets = _as_list(row.get("markets")) or _as_list(row.get("primary_market"))
    languages = _as_list(row.get("languages"))
    topics = _as_list(row.get("topics"))
    styles = _as_list(row.get("styles"))
    followers = int(row.get("followers") or 0)

    segs: set[str] = {f"tier:{_follower_tier(followers)}"}
    for market in markets:
        slug_m = _slug(market)
        segs.add(f"market:{slug_m}")
        for topic in topics:
            segs.add(f"market_topic:{slug_m}:{_slug(topic)}")
    for language in languages:
        slug_l = _slug(language)
        segs.add(f"lang:{slug_l}")
        for topic in topics:
            segs.add(f"lang_topic:{slug_l}:{_slug(topic)}")
    for topic in topics:
        segs.add(f"topic:{_slug(topic)}")
    for style in styles:
        segs.add(f"style:{_slug(style)}")
    return frozenset(segs)


def jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    a = set(left)
    b = set(right)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def overlap_vs_cohort(creator: Mapping[str, Any], cohort: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Mean / max Jaccard of one creator against the rest of a shortlist."""

    self_id = str(creator.get("creator_id", ""))
    segs = audience_segments(creator)
    peers = [
        item
        for item in cohort
        if str(item.get("creator_id", "")) and str(item.get("creator_id")) != self_id
    ]
    if not peers:
        return {
            "mean_jaccard": 0.0,
            "max_jaccard": 0.0,
            "peers": 0,
            "segment_count": len(segs),
            "method": "synthetic_segment_jaccard",
        }
    scores = [jaccard(segs, audience_segments(peer)) for peer in peers]
    return {
        "mean_jaccard": round(sum(scores) / len(scores), 4),
        "max_jaccard": round(max(scores), 4),
        "peers": len(peers),
        "segment_count": len(segs),
        "method": "synthetic_segment_jaccard",
    }


def incremental_reach(creators: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Marginal unique segments in the given order (usually score-ranked)."""

    covered: set[str] = set()
    rows: list[dict[str, Any]] = []
    for item in creators:
        segs = audience_segments(item)
        incremental = segs - covered
        covered |= segs
        followers = int(item.get("followers") or 0)
        share = (len(incremental) / len(segs)) if segs else 0.0
        rows.append(
            {
                "creator_id": str(item.get("creator_id", "")),
                "creator_name": str(item.get("creator_name", item.get("creator_id", ""))),
                "segment_count": len(segs),
                "incremental_segments": len(incremental),
                "incremental_share": round(share, 4),
                "covered_segments": len(covered),
                "followers": followers,
                "marginal_followers": int(round(followers * share)),
            }
        )
    return rows


def shortlist_overlap_report(creators: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Pairwise Jaccard plus incremental reach for a compare / shortlist set."""

    rows = [dict(item) for item in creators]
    pairs: list[dict[str, Any]] = []
    for i, left in enumerate(rows):
        for right in rows[i + 1 :]:
            score = jaccard(audience_segments(left), audience_segments(right))
            pairs.append(
                {
                    "left_id": str(left.get("creator_id", "")),
                    "right_id": str(right.get("creator_id", "")),
                    "left_name": str(left.get("creator_name", left.get("creator_id", ""))),
                    "right_name": str(right.get("creator_name", right.get("creator_id", ""))),
                    "jaccard": round(score, 4),
                }
            )
    incremental = incremental_reach(rows)
    return {
        "method": "synthetic_segment_jaccard",
        "modeled": True,
        "count": len(rows),
        "pairwise": pairs,
        "incremental": incremental,
        "max_pairwise_jaccard": max((item["jaccard"] for item in pairs), default=0.0),
        "union_segments": incremental[-1]["covered_segments"] if incremental else 0,
        "sum_marginal_followers": sum(item["marginal_followers"] for item in incremental),
    }
