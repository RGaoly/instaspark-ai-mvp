"""TF-IDF cosine retrieval over the demo catalog.

This is a real sparse-vector retrieval pass, not a neural embedding and not an
LLM ranker. Scores are a small additive boost on top of the named rule mix.
"""

from __future__ import annotations

import math
import re
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

TFIDF_BOOST_CAP = 3.0
_TOKEN = re.compile(r"[a-z0-9]+", re.I)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return " ".join(_as_text(item) for item in value)
    return str(value)


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN.findall(text or "")]


def _tf(tokens: Sequence[str]) -> dict[str, float]:
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    n = float(len(tokens) or 1)
    return {token: count / n for token, count in counts.items()}


def catalog_document(row: Mapping[str, Any]) -> str:
    return " ".join(
        [
            _as_text(row.get("creator_name")),
            _as_text(row.get("bio")),
            _as_text(row.get("topics")),
            _as_text(row.get("styles")),
            _as_text(row.get("evidence")),
            _as_text(row.get("primary_market")),
        ]
    )


def query_document(mission: Mapping[str, Any], *, dna_text: str = "", query: str = "") -> str:
    return " ".join(
        [
            _as_text(mission.get("product")),
            _as_text(mission.get("objective")),
            _as_text(mission.get("target_topics")),
            _as_text(mission.get("target_styles")),
            dna_text,
            query,
        ]
    )


def _idf(docs: Sequence[list[str]]) -> dict[str, float]:
    n = float(len(docs) or 1)
    df: dict[str, int] = {}
    for tokens in docs:
        for token in set(tokens):
            df[token] = df.get(token, 0) + 1
    return {token: math.log((n + 1.0) / (count + 1.0)) + 1.0 for token, count in df.items()}


def _dot(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    return sum(left[token] * right[token] for token in left if token in right)


def _norm(vector: Mapping[str, float]) -> float:
    return math.sqrt(sum(value * value for value in vector.values())) or 1.0


def cosine(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    return _dot(left, right) / (_norm(left) * _norm(right))


def tfidf_boosts(
    catalog: pd.DataFrame,
    mission: Mapping[str, Any],
    *,
    dna_text: str = "",
    query: str = "",
    cap: float = TFIDF_BOOST_CAP,
) -> dict[str, float]:
    """Return 0–cap additive boosts keyed by creator_id. Empty catalog is {}."""

    if catalog is None or catalog.empty:
        return {}
    docs = [tokenize(catalog_document(row)) for _, row in catalog.iterrows()]
    query_tokens = tokenize(query_document(mission, dna_text=dna_text, query=query))
    if not query_tokens:
        return {str(row.get("creator_id")): 0.0 for _, row in catalog.iterrows()}
    idf = _idf([*docs, query_tokens])
    query_vec = {token: tf * idf.get(token, 0.0) for token, tf in _tf(query_tokens).items()}
    boosts: dict[str, float] = {}
    for (_, row), tokens in zip(catalog.iterrows(), docs):
        doc_vec = {token: tf * idf.get(token, 0.0) for token, tf in _tf(tokens).items()}
        boosts[str(row.get("creator_id"))] = round(min(cap, max(0.0, cosine(query_vec, doc_vec) * cap)), 3)
    return boosts
