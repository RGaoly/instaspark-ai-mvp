from __future__ import annotations

import json
from pathlib import Path

from src.data_loader import load_creators, load_mission
from components.search import search_workspace


ROOT = Path(__file__).resolve().parents[1]


def _fixtures():
    creators = load_creators(ROOT / "data" / "creators.csv")
    mission = load_mission(ROOT / "data" / "launch_mission.json")
    mission = {
        **mission,
        "name": f'{mission["product"]} Global Launch',
        "markets": [mission["market"], "Mexico"],
    }
    opportunities = json.loads((ROOT / "data" / "creator_opportunities.json").read_text(encoding="utf-8"))
    return creators, [mission], opportunities


def test_empty_query_returns_no_hits():
    creators, missions, opportunities = _fixtures()
    assert search_workspace("  ", creators=creators, missions=missions, opportunities=opportunities) == []


def test_search_finds_creator_by_name():
    creators, missions, opportunities = _fixtures()
    hits = search_workspace("Ryan Gear", creators=creators, missions=missions, opportunities=opportunities)
    assert any(hit["kind"] == "creator" and hit["id"] == "C017" for hit in hits)


def test_search_finds_mission_by_product():
    creators, missions, opportunities = _fixtures()
    hits = search_workspace("X5", creators=creators, missions=missions, opportunities=opportunities)
    assert any(hit["kind"] == "mission" and hit["page"] == "launch-mission" for hit in hits)


def test_search_finds_opportunity_by_title():
    creators, missions, opportunities = _fixtures()
    hits = search_workspace("bilingual outdoor", creators=creators, missions=missions, opportunities=opportunities)
    assert any(hit["kind"] == "opportunity" and hit["id"] == "OPP-001" for hit in hits)


def test_search_requires_every_token():
    creators, missions, opportunities = _fixtures()
    hits = search_workspace("Ryan Antarctica", creators=creators, missions=missions, opportunities=opportunities)
    assert hits == []


def test_topbar_uses_a_real_search_input():
    shell = (ROOT / "components" / "shell.py").read_text(encoding="utf-8")
    assert 'key="global_search"' in shell
    assert "st.text_input" in shell
    assert "is-search-placeholder" not in shell
