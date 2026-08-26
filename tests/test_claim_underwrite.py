from pathlib import Path

from src.claim_underwrite import (
    UNDERWRITE_VERSION,
    attach_underwrite,
    claim_matrix,
    display_score,
    ledger_for_creator,
    pack_is_available,
    underwrite_score,
    unevidenced_spend_usd,
)
from src.data_loader import load_creators, load_mission
from src.evidence_reader import empty_pack, load_pack
from src.product_dna import claim_ids, load_product_dna
from src.scoring import rank_creators

ROOT = Path(__file__).resolve().parents[1]


def test_underwrite_score_weights_coverage_above_rule_mix():
    high_coverage = underwrite_score(100, 40)
    low_coverage = underwrite_score(0, 90)
    assert high_coverage > low_coverage
    assert high_coverage == 82.0  # 0.7*100 + 0.3*40


def test_committed_pack_makes_ranking_claim_underwritten():
    catalog = load_creators(ROOT / "data" / "creators.csv")
    mission = load_mission(ROOT / "data" / "launch_mission.json")
    pack = load_pack()
    assert pack_is_available(pack)
    underwritten = rank_creators(catalog, mission, evidence_pack=pack)
    scout_only = rank_creators(catalog, mission, evidence_pack=empty_pack())
    assert (underwritten["ranking_model_version"] == UNDERWRITE_VERSION).all()
    assert (scout_only["ranking_model_version"] == "rule_mix_tfidf_v1").all()
    assert int(underwritten.head(10)["spend_ready"].sum()) >= 1
    assert int(scout_only["spend_ready"].sum()) == 0
    assert list(underwritten.head(10)["creator_id"]) != list(scout_only.head(10)["creator_id"])


def test_ledger_only_counts_grounded_dna_claims():
    pack = load_pack()
    targets = claim_ids(load_product_dna())
    grounded_id = str((pack.get("grounded_creator_ids") or ["C004"])[0])
    ledger = ledger_for_creator(grounded_id, pack, targets)
    assert ledger["underwrite_status"] == "grounded"
    assert ledger["grounded_claim_count"] >= 1
    assert set(ledger["grounded_claim_ids"]) <= set(targets)


def test_display_score_uses_underwrite_when_stamped():
    row = attach_underwrite(
        {"total_score": 80, "positives": [], "warnings": []},
        {
            "claim_coverage": 50,
            "grounded_claim_ids": ["pov", "360"],
            "grounded_claim_count": 2,
            "target_claim_count": 4,
            "underwrite_status": "grounded",
            "brand_safety_flags": [],
            "contradictions": [],
        },
        pack_available=True,
    )
    assert row["ranking_model_version"] == UNDERWRITE_VERSION
    assert display_score(row) == row["underwrite_score"]
    assert row["total_score"] == 80


def test_claim_matrix_cells_are_quotes_or_empty():
    catalog = load_creators(ROOT / "data" / "creators.csv")
    mission = load_mission(ROOT / "data" / "launch_mission.json")
    pack = load_pack()
    ranked = rank_creators(catalog, mission, evidence_pack=pack)
    matrix = claim_matrix(ranked.to_dict("records"), claim_ids(load_product_dna()), pack=pack, limit=10)
    assert matrix["claim_ids"] == list(claim_ids(load_product_dna()))
    assert matrix["rows"]
    for row in matrix["rows"]:
        for cell in row["cells"]:
            if cell["grounded"]:
                assert cell["quote"]
                assert cell["timestamp"]
            else:
                assert cell["quote"] is None


def test_unevidenced_spend_ignores_grounded_rows():
    rows = [
        {"grounded_claim_count": 1, "estimated_cost_usd": 8000},
        {"grounded_claim_count": 0, "estimated_cost_usd": 5000},
        {"grounded_claim_count": 0, "estimated_cost_usd": 4000},
    ]
    assert unevidenced_spend_usd(rows, n=10) == 9000
