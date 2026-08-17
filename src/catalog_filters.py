"""Deterministic catalog filters for Creator Search.

These narrow the already-ranked demo catalog. They do not rescore, invent
creators, or send the query to an LLM ranker.
"""

from __future__ import annotations

from typing import Any, Iterable

import pandas as pd


def _cell_text(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return " ".join(str(item) for item in value if str(item).strip())
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def _as_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def _tokens(query: str) -> list[str]:
    return [token.lower() for token in str(query or "").split() if token.strip()]


def filter_ranked_creators(
    ranked: pd.DataFrame,
    *,
    query: str = "",
    markets: Iterable[str] | None = None,
    languages: Iterable[str] | None = None,
    topics: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Filter ranked catalog rows by keyword, market, language, and topics.

    Keyword tokens must all appear in name, topics, styles, or country
    (``primary_market`` / ``markets``). Empty filter values leave that axis open.
    An empty result is returned as-is — callers must not invent replacements.
    """

    if ranked is None or ranked.empty:
        return ranked.copy() if ranked is not None else pd.DataFrame()

    visible = ranked.copy()
    selected_markets = [item for item in (markets or []) if str(item).strip()]
    selected_languages = [item for item in (languages or []) if str(item).strip()]
    selected_topics = [item for item in (topics or []) if str(item).strip()]

    if selected_markets:
        market_set = set(selected_markets)
        visible = visible[
            visible.apply(
                lambda row: row.get("primary_market") in market_set
                or bool(market_set.intersection(_as_list(row.get("markets")))),
                axis=1,
            )
        ]

    if selected_languages:
        language_set = set(selected_languages)
        visible = visible[
            visible["languages"].apply(lambda values: bool(language_set.intersection(_as_list(values))))
        ]

    if selected_topics:
        topic_set = {item.lower() for item in selected_topics}
        visible = visible[
            visible["topics"].apply(
                lambda values: bool(topic_set.intersection(item.lower() for item in _as_list(values)))
            )
        ]

    tokens = _tokens(query)
    if tokens:
        def matches_query(row: pd.Series) -> bool:
            haystack = " ".join(
                [
                    _cell_text(row.get("creator_name")),
                    _cell_text(row.get("topics")),
                    _cell_text(row.get("styles")),
                    _cell_text(row.get("primary_market")),
                    _cell_text(row.get("markets")),
                ]
            ).lower()
            return all(token in haystack for token in tokens)

        visible = visible[visible.apply(matches_query, axis=1)]

    return visible.reset_index(drop=True)


def unique_catalog_values(ranked: pd.DataFrame, column: str) -> list[str]:
    """Stable unique values from a scalar or list-like catalog column."""

    if ranked is None or ranked.empty or column not in ranked.columns:
        return []
    values: list[str] = []
    seen: set[str] = set()
    for cell in ranked[column]:
        for item in _as_list(cell):
            if item not in seen:
                seen.add(item)
                values.append(item)
    return values
