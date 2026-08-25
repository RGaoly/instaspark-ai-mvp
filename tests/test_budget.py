from src.budget import BUDGET_MODEL_VERSION, propose_budget_decision
from views.growth_review import _budget_html


def test_empty_events_observe_without_forecast():
    decision = propose_budget_decision([], sku="Insta360 X5", budget_usd=1000)
    assert decision["action"] == "observe"
    assert decision["expected_value_usd"] is None
    assert decision["expected_value_status"] == "not_collected"
    assert decision["uncertainty"] == "unmeasured"
    assert decision["human_approval_required"] is True
    assert decision["model_version"] == BUDGET_MODEL_VERSION
    assert "0x" in decision["note"]
    html = _budget_html(decision)
    assert "observe" in html
    assert "viral" in html.lower() or "Not a viral forecast" in html


def test_recorded_events_use_revenue_not_a_lift_model():
    decision = propose_budget_decision(
        [{"orders": 2, "revenue_usd": 80, "spend_usd": 40}],
        sku="Insta360 X5",
    )
    assert decision["action"] == "review_recorded_outcomes"
    assert decision["expected_value_usd"] == 80
    assert decision["expected_value_status"] == "recorded_revenue"
    assert decision["cost_usd"] == 40
    assert "+64000" not in str(decision)
    assert "forecast" not in decision["note"].lower()
