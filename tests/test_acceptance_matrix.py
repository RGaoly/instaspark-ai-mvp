from pathlib import Path

from src.content_evidence import load_creator_content
from src.data_loader import load_creators, load_mission
from src.evaluation import acceptance_matrix
from src.scoring import rank_creators

ROOT = Path(__file__).resolve().parents[1]


def test_acceptance_matrix_passes_on_demo_catalog():
    catalog = load_creators(ROOT / "data" / "creators.csv")
    mission = load_mission(ROOT / "data" / "launch_mission.json")
    posts = load_creator_content()
    ranked = rank_creators(catalog, mission)
    again = rank_creators(catalog, mission)
    assert list(ranked.head(10)["creator_id"]) == list(again.head(10)["creator_id"])

    rows = {item["id"]: item for item in acceptance_matrix(
        ranked=ranked,
        mission=mission,
        catalog_size=len(catalog),
        posts=posts,
        events=[],
    )}
    assert rows["hard_gates"]["passed"] is True
    assert rows["evidence"]["passed"] is True
    assert rows["stability"]["passed"] is True
    assert rows["attribution"]["passed"] is True
    assert rows["recall"]["passed"] is True
    assert rows["recall"]["value"] == 60
    assert "public-channel" in rows["recall"]["target"]
    assert rows["intensive_read"]["passed"] is True
    assert rows["intensive_read"]["value"] == 20
    assert "not_collected" in rows["intensive_read"]["detail"]
    assert "labeled-demo" in rows["intensive_read"]["detail"]
    assert rows["intensive_read"]["target"].startswith("20 creators")
    assert rows["catalog_videos"]["passed"] is True
    assert rows["catalog_videos"]["value"] == 180
    assert rows["creator_genome"]["passed"] is True
    assert rows["creator_genome"]["value"] == 60


def test_attribution_fails_when_event_missing_source():
    catalog = load_creators(ROOT / "data" / "creators.csv")
    mission = load_mission(ROOT / "data" / "launch_mission.json")
    ranked = rank_creators(catalog, mission)
    rows = {item["id"]: item for item in acceptance_matrix(
        ranked=ranked,
        mission=mission,
        catalog_size=len(catalog),
        posts=load_creator_content(),
        events=[{"creator_id": "C004", "mission_id": mission["mission_id"], "orders": 1}],
    )}
    assert rows["attribution"]["passed"] is False
