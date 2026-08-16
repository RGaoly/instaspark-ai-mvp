from pathlib import Path

from src.audience import (
    audience_segments,
    incremental_reach,
    jaccard,
    overlap_vs_cohort,
    shortlist_overlap_report,
)
from src.data_loader import load_creators

ROOT = Path(__file__).resolve().parents[1]


def test_identical_segment_sets_have_jaccard_one():
    segs = {"market:us", "topic:outdoor"}
    assert jaccard(segs, segs) == 1.0


def test_disjoint_segment_sets_have_jaccard_zero():
    assert jaccard({"a"}, {"b"}) == 0.0


def test_creator_segments_are_deterministic():
    creators = load_creators(ROOT / "data" / "creators.csv")
    row = creators.iloc[0].to_dict()
    assert audience_segments(row) == audience_segments(row)
    assert audience_segments(row)


def test_shortlist_overlap_and_marginal_reach_are_modeled():
    creators = load_creators(ROOT / "data" / "creators.csv")
    rows = creators.head(3).to_dict("records")
    report = shortlist_overlap_report(rows)
    assert report["modeled"] is True
    assert report["method"] == "synthetic_segment_jaccard"
    assert report["count"] == 3
    assert len(report["pairwise"]) == 3
    assert 0.0 <= report["max_pairwise_jaccard"] <= 1.0
    incremental = report["incremental"]
    assert incremental[0]["incremental_segments"] == incremental[0]["segment_count"]
    assert incremental[0]["covered_segments"] <= incremental[-1]["covered_segments"]
    vs = overlap_vs_cohort(rows[0], rows)
    assert vs["peers"] == 2
    assert 0.0 <= vs["mean_jaccard"] <= 1.0


def test_later_similar_creators_add_less_incremental_reach():
    creators = load_creators(ROOT / "data" / "creators.csv")
    rows = creators.head(4).to_dict("records")
    lifts = incremental_reach(rows)
    assert lifts[0]["incremental_share"] == 1.0
    assert lifts[-1]["incremental_share"] <= lifts[0]["incremental_share"]
