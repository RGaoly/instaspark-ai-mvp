from __future__ import annotations

from pathlib import Path

from src.catalog_filters import filter_ranked_creators
from src.data_loader import load_creators, load_mission
from src.scoring import rank_creators


ROOT = Path(__file__).resolve().parents[1]


def _ranked():
    creators = load_creators(ROOT / "data" / "creators.csv")
    mission = load_mission(ROOT / "data" / "launch_mission.json")
    return rank_creators(creators, mission)


def test_keyword_filter_includes_matching_name_and_excludes_others():
    ranked = _ranked()
    assert not ranked.empty
    included = filter_ranked_creators(ranked, query="Ryan Gear")
    assert list(included["creator_id"]) == ["C017"]

    excluded = filter_ranked_creators(ranked, query="Antarctica")
    assert excluded.empty


def test_keyword_filter_matches_topics_and_country():
    ranked = _ranked()
    by_topic = filter_ranked_creators(ranked, query="surfing")
    assert not by_topic.empty
    assert by_topic["topics"].apply(lambda topics: "surfing" in [str(item).lower() for item in topics]).all()

    by_country = filter_ranked_creators(ranked, query="mexico")
    if not by_country.empty:
        assert by_country.apply(
            lambda row: "mexico" in str(row.get("primary_market", "")).lower()
            or "mexico" in " ".join(str(item).lower() for item in (row.get("markets") or [])),
            axis=1,
        ).all()


def test_market_filter_includes_and_excludes_catalog_rows():
    ranked = _ranked()
    mexico = filter_ranked_creators(ranked, markets=["Mexico"])
    japan = filter_ranked_creators(ranked, markets=["Japan"])
    assert japan.empty
    assert not mexico.empty
    assert mexico.apply(
        lambda row: row["primary_market"] == "Mexico" or "Mexico" in list(row.get("markets") or []),
        axis=1,
    ).all()
    without_mexico = ranked[ranked["markets"].apply(lambda markets: "Mexico" not in list(markets or []))]
    assert set(mexico["creator_id"]).isdisjoint(set(without_mexico["creator_id"]))


def test_empty_filters_keep_ranked_catalog():
    ranked = _ranked()
    visible = filter_ranked_creators(ranked, query="", markets=[], languages=[], topics=[])
    assert len(visible) == len(ranked)
