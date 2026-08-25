"""BudgetDecision from recorded performance events only.

PDF BudgetDecision fields: cost, expected value, uncertainty, action, approver,
next effective time. This demo never invents a lift forecast. Empty events keep
ROI at 0x and the action at observe.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from src.domain import attributed_roi


BUDGET_MODEL_VERSION = "events_only_v1"


def propose_budget_decision(
    events: Sequence[Mapping[str, Any]] = (),
    *,
    sku: str,
    budget_usd: float = 0.0,
    actor: str = "Olivia Chen",
) -> dict[str, Any]:
    rows = list(events or [])
    spend = sum(float(item.get("spend_usd") or 0) for item in rows)
    revenue = sum(float(item.get("revenue_usd") or 0) for item in rows)
    orders = sum(int(item.get("orders") or 0) for item in rows)
    roi = attributed_roi(rows)
    if not rows:
        action = "observe"
        uncertainty = "unmeasured"
        expected_value = None
        note = "No recorded events. ROI stays 0x. This is not a modeled forecast."
    else:
        action = "review_recorded_outcomes"
        uncertainty = "recorded_only"
        expected_value = round(revenue, 2)
        note = (
            f"{len(rows)} recorded event(s) · {orders} orders · "
            f"ROI {roi:.2f}x from events, not a viral prediction."
        )
    return {
        "decision_id": "budget_from_events",
        "sku": sku,
        "cost_usd": round(spend, 2),
        "budget_usd": float(budget_usd or 0),
        "expected_value_usd": expected_value,
        "expected_value_status": "not_collected" if expected_value is None else "recorded_revenue",
        "uncertainty": uncertainty,
        "action": action,
        "approver": actor,
        "human_approval_required": True,
        "next_effective_at": None,
        "model_version": BUDGET_MODEL_VERSION,
        "note": note,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
