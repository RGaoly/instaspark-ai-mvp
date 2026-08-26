from pathlib import Path

from src.business_value import SECONDS_PER_CAPTION_BODY, compute, hours_saved
from src.data_loader import load_creators, load_mission

ROOT = Path(__file__).resolve().parents[1]


def test_hours_saved_is_the_documented_process_model():
    assert hours_saved(103) == round(103 * SECONDS_PER_CAPTION_BODY / 3600, 2)
    assert hours_saved(0) == 0


def test_business_value_board_is_computed_from_committed_artifacts():
    board = compute(
        load_creators(ROOT / "data" / "creators.csv"),
        load_mission(ROOT / "data" / "launch_mission.json"),
    )
    assert board["available"] is True
    assert board["eligible_clips"] >= 1
    assert board["hours_saved"] == hours_saved(board["eligible_clips"])
    assert board["unevidenced_spend_blocked_usd"] >= 0
    assert board["top10_spend_ready"] >= 1
    assert board["gold_f1_lift"] is not None
    assert "unevidenced_spend =" in board["formulas"][0]
    assert "spend_blocked =" in board["formulas"][1]
    assert any(item.startswith("hours_saved") for item in board["formulas"])
    assert board["unevidenced_spend_blocked_usd"] >= 10_000
    assert board["rule_top10_unevidenced_n"] >= 1
    assert "Not a customer ROI" in board["note"]
    assert "interview" not in board["pain"].lower()
