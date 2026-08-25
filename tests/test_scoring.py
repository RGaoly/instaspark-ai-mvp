from pathlib import Path

import pandas as pd

from src.data_loader import load_creators, load_mission
from src.scoring import (
    DEFAULT_WEIGHTS,
    LIVE_PROOF_BONUS,
    additive_driver_display,
    mix_driver_display,
    passes_hard_gates,
    rank_creators,
    score_creator,
)

ROOT = Path(__file__).resolve().parents[1]


def _mission():
    return load_mission(ROOT / "data" / "launch_mission.json")


def _catalog():
    return load_creators(ROOT / "data" / "creators.csv")


def _row(**overrides) -> pd.Series:
    payload = {
        "creator_id": "T1",
        "creator_name": "Test Rider",
        "primary_market": "United States",
        "markets": ["United States"],
        "languages": ["English"],
        "followers": 100000,
        "engagement_rate": 4.0,
        "topics": ["cycling", "outdoor"],
        "styles": ["POV"],
        "estimated_cost_usd": 5000,
        "brand_safety_score": 80,
        "posting_consistency": 0.7,
        "recent_decline": 0.0,
        "collaboration_openness": 0.7,
        "historical_reliability": 0.8,
        "bio": "",
        "evidence": [],
        "risks": [],
    }
    payload.update(overrides)
    return pd.Series(payload)


def test_ranking_is_descending():
    ranked = rank_creators(_catalog(), _mission())
    scores = ranked["total_score"].tolist()
    assert scores == sorted(scores, reverse=True)


def test_all_ranked_creators_pass_hard_gates():
    ranked = rank_creators(_catalog(), _mission())
    for _, row in ranked.iterrows():
        passed, reasons = passes_hard_gates(row, _mission())
        assert passed is True
        assert reasons == []


def test_score_range():
    ranked = rank_creators(_catalog(), _mission())
    assert ranked["total_score"].between(0, 100).all()


def test_mix_weights_sum_to_one():
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9
    assert set(DEFAULT_WEIGHTS) == {
        "mission_fit",
        "topic_overlap",
        "momentum",
        "commercial_fit",
        "brand_safety",
    }


def test_empty_query_does_not_change_order_vs_baseline():
    mission = _mission()
    creators = _catalog()
    baseline = rank_creators(creators, mission)
    empty = rank_creators(creators, mission, query="")
    whitespace = rank_creators(creators, mission, query="   ")
    assert list(baseline["creator_id"]) == list(empty["creator_id"]) == list(whitespace["creator_id"])
    assert list(baseline["total_score"]) == list(empty["total_score"]) == list(whitespace["total_score"])
    assert (empty["query_boost"] == 0).all()


def test_topic_overlap_ranks_closer_creators_higher():
    mission = _mission()
    close = _row(
        creator_id="CLOSE",
        creator_name="Close Match",
        topics=list(mission["target_topics"]),
        styles=["vlog"],
    )
    far = _row(
        creator_id="FAR",
        creator_name="Far Match",
        topics=["fashion", "beauty", "cooking"],
        styles=["vlog"],
    )
    close_score = score_creator(close, mission)
    far_score = score_creator(far, mission)
    assert close_score["topic_overlap"] > far_score["topic_overlap"]
    assert close_score["total_score"] > far_score["total_score"]

    ranked = rank_creators(pd.DataFrame([far.to_dict(), close.to_dict()]), mission, dna_text="")
    assert list(ranked["creator_id"]) == ["CLOSE", "FAR"]


def test_attaching_live_evidence_increases_score():
    mission = _mission()
    row = _row()
    baseline = score_creator(row, mission, has_live_evidence=False)
    attached = score_creator(row, mission, has_live_evidence=True)
    assert baseline["live_proof_bonus"] == 0
    assert attached["live_proof_bonus"] == LIVE_PROOF_BONUS
    assert attached["total_score"] > baseline["total_score"]
    assert "Live YouTube evidence attached" in attached["positives"]

    ranked = rank_creators(
        pd.DataFrame([row.to_dict()]),
        mission,
        live_evidence_ids=["T1"],
        dna_text="",
    )
    boost = float(ranked.iloc[0]["tfidf_boost"])
    attached_with = score_creator(row, mission, has_live_evidence=True, tfidf_boost=boost)
    assert float(ranked.iloc[0]["live_proof_bonus"]) == LIVE_PROOF_BONUS
    assert float(ranked.iloc[0]["total_score"]) == attached_with["total_score"]


def test_query_boost_is_lexical_and_capped():
    mission = _mission()
    row = _row()
    baseline = score_creator(row, mission, query="")
    boosted = score_creator(row, mission, query="Rider cycling")
    assert boosted["query_boost"] > 0
    assert boosted["query_boost"] <= 4.0
    assert boosted["total_score"] > baseline["total_score"]


def test_named_drivers_are_aligned_for_search_and_compare():
    scored = score_creator(_row(), _mission())
    mix_labels = [label for label, _score, _weight in mix_driver_display(scored)]
    additive_labels = [label for label, _score, _note in additive_driver_display(scored)]
    assert mix_labels == [
        "Mission fit",
        "Topic overlap",
        "Momentum",
        "Commercial fit",
        "Brand safety",
    ]
    assert additive_labels == ["Query boost", "Live proof bonus", "TF-IDF cosine"]
    assert all(tag.startswith("w ") for _label, _score, tag in mix_driver_display(scored))


def test_legacy_weight_keys_still_score():
    scored = score_creator(
        _row(),
        _mission(),
        {
            "content_fit": 0.30,
            "audience_fit": 0.20,
            "momentum": 0.15,
            "commercial_fit": 0.15,
            "brand_safety": 0.20,
        },
    )
    assert 0 <= scored["total_score"] <= 100
    assert scored["mission_fit"] == scored["audience_fit"]
    assert scored["topic_overlap"] == scored["content_fit"]
