from __future__ import annotations

import pytest

from services.opportunity_service import create_opportunity, load_opportunities


def test_seed_opportunities_expose_product_contract_fields():
    records = load_opportunities()
    required = {
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
    }
    assert len(records) == 3
    assert all(required <= set(record) for record in records)
    assert all(record["evidence"] for record in records)


@pytest.mark.parametrize(
    "field",
    ["creator_id", "title", "source", "market", "language", "hypothesis", "owner"],
)
def test_create_opportunity_rejects_none_required_values(field):
    values = {
        "creator_id": "C003",
        "title": "Creator signal",
        "source": "Regional nomination",
        "market": "United States",
        "language": "English",
        "hypothesis": "This creator may fit the market.",
        "evidence": ["profile://C003"],
        "owner": "Global Creator Team",
    }
    values[field] = None

    with pytest.raises(ValueError, match=field):
        create_opportunity([], **values)


def test_created_opportunity_keeps_type_observation_and_next_action():
    record = create_opportunity(
        [],
        creator_id="C003",
        title="Creator signal",
        source="Regional nomination",
        market="United States",
        language="English",
        hypothesis="This creator may fit the market.",
        evidence=["profile://C003"],
        owner="Global Creator Team",
        opportunity_type="regional_nomination",
        observed_at="2026-08-06T10:00:00+08:00",
        suggested_action="Qualify after evidence review",
    )

    assert record["opportunity_type"] == "regional_nomination"
    assert record["observed_at"] == "2026-08-06T10:00:00+08:00"
    assert record["suggested_action"] == "Qualify after evidence review"
