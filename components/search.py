"""Workspace search over missions, creators, and opportunities.

The top bar used to be a non-interactive HTML pill. This module is the
actual lookup so typing a name, product, market, or topic returns a
navigable hit instead of a dead control.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def _haystack(*parts: Any) -> str:
    chunks: list[str] = []
    for part in parts:
        if part is None:
            continue
        if isinstance(part, (list, tuple, set)):
            chunks.extend(str(item) for item in part if item is not None)
        else:
            chunks.append(str(part))
    return " ".join(chunks).lower()


def _matches(query: str, haystack: str) -> bool:
    tokens = [token for token in query.casefold().split() if token]
    if not tokens:
        return False
    blob = haystack.casefold()
    return all(token in blob for token in tokens)


def search_workspace(
    query: str,
    *,
    creators: pd.DataFrame,
    missions: list[dict[str, Any]],
    opportunities: list[dict[str, Any]],
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Return ranked hits for the global search box.

    All query tokens must appear in the record (AND). Missions and
    opportunities are listed first so a product or inbound signal is not
    buried under 30 creator names.
    """

    needle = str(query or "").strip()
    if not needle:
        return []

    hits: list[dict[str, Any]] = []

    for mission in missions:
        text = _haystack(
            mission.get("name"),
            mission.get("mission_id"),
            mission.get("product"),
            mission.get("market"),
            mission.get("markets"),
            mission.get("objective"),
            mission.get("target_topics"),
            mission.get("target_styles"),
        )
        if _matches(needle, text):
            title = str(mission.get("name") or mission.get("product") or mission["mission_id"])
            market = mission.get("market") or (mission.get("markets") or [""])[0]
            hits.append(
                {
                    "kind": "mission",
                    "id": mission["mission_id"],
                    "title": title,
                    "subtitle": f'{mission.get("product", "")} · {market}'.strip(" ·"),
                    "page": "launch-mission",
                }
            )

    creator_names = {
        row["creator_id"]: row.get("creator_name", row["creator_id"])
        for _, row in creators.iterrows()
    }
    for opportunity in opportunities:
        creator_name = creator_names.get(opportunity.get("creator_id"), "")
        text = _haystack(
            opportunity.get("opportunity_id"),
            opportunity.get("title"),
            opportunity.get("hypothesis"),
            opportunity.get("market"),
            opportunity.get("source"),
            opportunity.get("suggested_action"),
            creator_name,
            opportunity.get("creator_id"),
        )
        if _matches(needle, text):
            hits.append(
                {
                    "kind": "opportunity",
                    "id": opportunity["opportunity_id"],
                    "title": str(opportunity.get("title") or opportunity["opportunity_id"]),
                    "subtitle": f'{creator_name} · {opportunity.get("market", "")}'.strip(" ·"),
                    "page": "creator-opportunity",
                }
            )

    for _, row in creators.iterrows():
        text = _haystack(
            row.get("creator_id"),
            row.get("creator_name"),
            row.get("primary_market"),
            row.get("markets"),
            row.get("languages"),
            row.get("topics"),
            row.get("styles"),
            row.get("bio"),
        )
        if _matches(needle, text):
            topics = " · ".join(list(row.get("topics") or [])[:2])
            hits.append(
                {
                    "kind": "creator",
                    "id": row["creator_id"],
                    "title": str(row.get("creator_name") or row["creator_id"]),
                    "subtitle": f'{row.get("primary_market", "")} · {topics}'.strip(" ·"),
                    "page": "creator-search",
                }
            )

    return hits[:limit]
