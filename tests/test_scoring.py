from pathlib import Path
from src.data_loader import load_creators, load_mission
from src.scoring import passes_hard_gates, rank_creators

ROOT = Path(__file__).resolve().parents[1]


def test_ranking_is_descending():
    creators = load_creators(ROOT / "data" / "creators.csv")
    mission = load_mission(ROOT / "data" / "launch_mission.json")
    ranked = rank_creators(creators, mission)
    scores = ranked["total_score"].tolist()
    assert scores == sorted(scores, reverse=True)


def test_all_ranked_creators_pass_hard_gates():
    creators = load_creators(ROOT / "data" / "creators.csv")
    mission = load_mission(ROOT / "data" / "launch_mission.json")
    ranked = rank_creators(creators, mission)
    for _, row in ranked.iterrows():
        passed, reasons = passes_hard_gates(row, mission)
        assert passed is True
        assert reasons == []


def test_score_range():
    creators = load_creators(ROOT / "data" / "creators.csv")
    mission = load_mission(ROOT / "data" / "launch_mission.json")
    ranked = rank_creators(creators, mission)
    assert ranked["total_score"].between(0, 100).all()
