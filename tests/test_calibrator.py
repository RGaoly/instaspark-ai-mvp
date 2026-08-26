from src.calibrator import propose
from src.scoring import DEFAULT_WEIGHTS


def test_calibrator_skips_when_the_decision_log_is_empty():
    proposal = propose([])
    assert proposal["status"] == "skipped"
    assert proposal["auto_applied"] is False
    assert proposal["proposed_weights"] == proposal["current_weights"]
    assert "invent" in proposal["note"].lower()


def test_risk_or_cost_reason_codes_shift_weight_toward_commercial_and_safety():
    decisions = [{"reason_code": "risk_or_cost"} for _ in range(3)]
    proposal = propose(decisions, DEFAULT_WEIGHTS)
    assert proposal["status"] == "ok"
    assert proposal["auto_applied"] is False
    assert abs(sum(proposal["proposed_weights"].values()) - 1.0) < 1e-6
    assert proposal["proposed_weights"]["commercial_fit"] > DEFAULT_WEIGHTS["commercial_fit"]
    assert proposal["proposed_weights"]["brand_safety"] > DEFAULT_WEIGHTS["brand_safety"]
