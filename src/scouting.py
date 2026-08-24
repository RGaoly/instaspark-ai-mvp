"""Always-on scout cards from catalog momentum. Not a live crawl.

Windows are labeled proxies from existing catalog fields:
7-day ≈ inverted recent_decline, 30-day ≈ engagement, 90-day ≈ posting_consistency.
"""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

SCOUT_LIMIT = 8


def _as_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def scout_score(row: Mapping[str, Any]) -> float:
    decline = float(row.get("recent_decline") or 0)
    engagement = float(row.get("engagement_rate") or 0)
    consistency = float(row.get("posting_consistency") or 0)
    return round((1.0 - decline) * 40 + min(engagement, 8.0) * 5 + consistency * 20, 1)


def scout_cards(
    catalog: pd.DataFrame,
    *,
    exclude_ids: set[str] | None = None,
    limit: int = SCOUT_LIMIT,
    genomes: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Rising catalog creators. Empty catalog returns []."""

    if catalog is None or catalog.empty:
        return []
    blocked = {str(item) for item in (exclude_ids or []) if str(item).strip()}
    pack = genomes
    if pack is None:
        try:
            from src.creator_genome import genomes_by_id

            pack = genomes_by_id()
        except (OSError, ValueError):
            pack = {}
    cards: list[dict[str, Any]] = []
    for _, row in catalog.iterrows():
        creator_id = str(row.get("creator_id") or "")
        if not creator_id or creator_id in blocked:
            continue
        genome = pack.get(creator_id) or {}
        momentum = genome.get("momentum") or {}
        window_7d = float(momentum["window_7d"]) if "window_7d" in momentum else round((1.0 - float(row.get("recent_decline") or 0)) * 100, 1)
        window_30d = float(momentum["window_30d"]) if "window_30d" in momentum else round(float(row.get("engagement_rate") or 0) * 10, 1)
        window_90d = float(momentum["window_90d"]) if "window_90d" in momentum else round(float(row.get("posting_consistency") or 0) * 100, 1)
        score = float(momentum["scout_score"]) if "scout_score" in momentum else scout_score(row)
        cards.append(
            {
                "creator_id": creator_id,
                "creator_name": str(row.get("creator_name") or creator_id),
                "market": str(row.get("primary_market") or ""),
                "language": (_as_list(row.get("languages")) or [""])[0],
                "topics": list((genome.get("topic_scene") or {}).get("topics") or _as_list(row.get("topics"))),
                "scout_score": score,
                "window_7d": window_7d,
                "window_30d": window_30d,
                "window_90d": window_90d,
                "genome_id": genome.get("genome_id"),
                "source": "creator_genome" if genome else "catalog_momentum",
                "note": str(momentum.get("note") or "Catalog proxies, not a live 7/30/90 crawl."),
            }
        )
    cards.sort(key=lambda item: (-item["scout_score"], item["creator_id"]))
    return cards[:limit]
