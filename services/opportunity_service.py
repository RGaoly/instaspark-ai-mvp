from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OPPORTUNITIES_PATH = ROOT / "data" / "creator_opportunities.json"

OPPORTUNITY_FIELDS = (
    "opportunity_id",
    "opportunity_type",
    "creator_id",
    "title",
    "source",
    "market",
    "language",
    "hypothesis",
    "evidence",
    "status",
    "owner",
    "observed_at",
    "created_at",
    "suggested_action",
    "linked_mission_id",
)

OPPORTUNITY_STATUSES = (
    "discovered",
    "qualified",
    "shortlisted",
    "approved",
    "contacted",
    "negotiating",
    "contracted",
    "content_in_review",
    "published",
    "measured",
    "closed_lost",
)


def _clean_evidence(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [line.strip(" -\t") for line in value.splitlines() if line.strip(" -\t")]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, Mapping)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def normalize_opportunity(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return one opportunity in the canonical, JSON-serializable shape."""

    opportunity = {field: value.get(field) for field in OPPORTUNITY_FIELDS}
    for field in (
        "opportunity_id",
        "opportunity_type",
        "creator_id",
        "title",
        "source",
        "market",
        "language",
        "hypothesis",
        "owner",
        "suggested_action",
    ):
        opportunity[field] = str(opportunity.get(field) or "").strip()

    opportunity["evidence"] = _clean_evidence(opportunity.get("evidence"))
    status = str(opportunity.get("status") or "discovered").strip().lower()
    opportunity["status"] = status if status in OPPORTUNITY_STATUSES else "discovered"
    opportunity["created_at"] = str(opportunity.get("created_at") or "").strip()
    opportunity["observed_at"] = str(
        opportunity.get("observed_at") or opportunity["created_at"]
    ).strip()
    opportunity["linked_mission_id"] = (
        str(opportunity["linked_mission_id"]).strip()
        if opportunity.get("linked_mission_id")
        else None
    )
    return opportunity


def load_opportunities(path: str | Path = DEFAULT_OPPORTUNITIES_PATH) -> list[dict[str, Any]]:
    """Load and validate the seed opportunity collection."""

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Creator opportunities data must be a JSON array.")

    opportunities = [normalize_opportunity(item) for item in raw]
    identifiers = [item["opportunity_id"] for item in opportunities]
    if any(not identifier for identifier in identifiers):
        raise ValueError("Every creator opportunity must have an opportunity_id.")
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Creator opportunity IDs must be unique.")
    return opportunities


def next_opportunity_id(opportunities: Iterable[Mapping[str, Any]]) -> str:
    """Choose the next readable OPP-NNN identifier for a session-created item."""

    numbers = []
    for opportunity in opportunities:
        match = re.fullmatch(r"OPP-(\d+)", str(opportunity.get("opportunity_id", "")))
        if match:
            numbers.append(int(match.group(1)))
    return f"OPP-{max(numbers, default=0) + 1:03d}"


def create_opportunity(
    opportunities: Iterable[Mapping[str, Any]],
    *,
    creator_id: str,
    title: str,
    source: str,
    market: str,
    language: str,
    hypothesis: str,
    evidence: object,
    owner: str,
    status: str = "discovered",
    linked_mission_id: str | None = None,
    created_at: str | None = None,
    opportunity_type: str = "creator_signal",
    observed_at: str | None = None,
    suggested_action: str = "Review evidence and qualify the opportunity",
) -> dict[str, Any]:
    """Build a new opportunity without mutating the supplied collection."""

    existing = list(opportunities)
    required = {
        "creator_id": creator_id,
        "title": title,
        "source": source,
        "market": market,
        "language": language,
        "hypothesis": hypothesis,
        "owner": owner,
    }
    missing = [
        label
        for label, value in required.items()
        if value is None or not str(value).strip()
    ]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    if status not in OPPORTUNITY_STATUSES:
        raise ValueError(f"Unsupported opportunity status: {status}")

    return normalize_opportunity(
        {
            "opportunity_id": next_opportunity_id(existing),
            **required,
            "evidence": evidence,
            "status": status,
            "opportunity_type": opportunity_type,
            "created_at": created_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "observed_at": observed_at or created_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "suggested_action": suggested_action,
            "linked_mission_id": linked_mission_id,
        }
    )


def find_opportunity(
    opportunities: Iterable[Mapping[str, Any]], opportunity_id: str | None
) -> dict[str, Any] | None:
    for opportunity in opportunities:
        if opportunity.get("opportunity_id") == opportunity_id:
            return normalize_opportunity(opportunity)
    return None
