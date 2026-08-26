from pathlib import Path

from components.positioning import rubric_scorecard_html
from src.claim_underwrite import UNDERWRITE_VERSION
from src.data_loader import load_creators, load_mission
from src.evidence_reader import empty_pack
from src.rubric_scorecard import SIGNIFICANT_BLOCKED_USD, prove
from views.growth_review import _business_value_html
from src.business_value import compute


ROOT = Path(__file__).resolve().parents[1]


def _live() -> dict:
    return prove(
        load_creators(ROOT / "data" / "creators.csv"),
        load_mission(ROOT / "data" / "launch_mission.json"),
    )


def test_live_artifacts_meet_every_five_point_bar():
    card = _live()
    assert card["all_met"] is True
    assert card["points"] == {
        "innovation": 5,
        "value": 5,
        "depth": 5,
        "completeness": 5,
    }
    assert card["value"]["ranking_model_version"] == UNDERWRITE_VERSION
    assert card["value"]["unevidenced_spend_blocked_usd"] >= SIGNIFICANT_BLOCKED_USD
    html = rubric_scorecard_html(card)
    assert 'id="rubric-scorecard"' in html
    assert 'id="rubric-innovation"' in html
    assert 'id="rubric-value"' in html
    assert 'id="rubric-depth"' in html
    assert 'id="rubric-completeness"' in html
    assert "行业级新范式" in html
    assert "直击痛点，收益显著" in html
    assert "离开 AI 方案不成立" in html
    assert "闭环清晰有落地路径" in html
    assert "Calibrator" in html


def test_empty_book_cannot_claim_five_on_innovation_or_depth():
    card = prove(
        load_creators(ROOT / "data" / "creators.csv"),
        load_mission(ROOT / "data" / "launch_mission.json"),
        pack=empty_pack(),
    )
    assert card["all_met"] is False
    assert card["points"]["innovation"] < 5
    assert card["points"]["depth"] < 5
    assert card["points"]["value"] < 5


def test_value_board_leads_with_blocked_spend():
    board = compute(
        load_creators(ROOT / "data" / "creators.csv"),
        load_mission(ROOT / "data" / "launch_mission.json"),
    )
    html = _business_value_html(board)
    assert html.index("Unevidenced spend blocked") < html.index("Hours of caption reading replaced")
    assert board["formulas"][0].startswith("unevidenced_spend")
    assert board["rule_top10_unevidenced_n"] >= 1
    assert board["unevidenced_spend_blocked_usd"] >= SIGNIFICANT_BLOCKED_USD
