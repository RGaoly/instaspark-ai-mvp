"""Calibrator: reason codes from the human desk become the next book's weight proposal.

The sixth CEG role. It never mints a claim_id and never auto-applies. An operator
must accept the proposal. Without decisions the step is skipped, not invented.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.scoring import DEFAULT_WEIGHTS

CALIBRATOR_VERSION = "reason_code_calibrator_v1"

# Rejected / review codes pull weight toward commercial and safety; strong_fit is a no-op.
REASON_HINTS: dict[str, dict[str, float]] = {
    "risk_or_cost": {"commercial_fit": 0.04, "brand_safety": 0.04, "topic_overlap": -0.04, "momentum": -0.04},
    "needs_review": {"topic_overlap": 0.03, "mission_fit": 0.02, "momentum": -0.05},
    "opportunity_rejected": {"brand_safety": 0.05, "commercial_fit": 0.03, "momentum": -0.04, "topic_overlap": -0.04},
    "strong_fit": {},
}


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize(weights: Mapping[str, float] | None) -> dict[str, float]:
    base = dict(DEFAULT_WEIGHTS)
    if weights:
        for key in base:
            if key in weights:
                base[key] = float(weights[key])
            elif key == "mission_fit" and "audience_fit" in weights:
                base[key] = float(weights["audience_fit"])
            elif key == "topic_overlap" and "content_fit" in weights:
                base[key] = float(weights["content_fit"])
    total = sum(base.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)
    return {key: round(value / total, 4) for key, value in base.items()}


def count_reason_codes(decisions: Sequence[Mapping[str, Any]] | None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in decisions or []:
        code = _as_text(item.get("reason_code"))
        if not code:
            continue
        counts[code] = counts.get(code, 0) + 1
    return counts


def propose(
    decisions: Sequence[Mapping[str, Any]] | None,
    current_weights: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Return a weight proposal. Empty decisions → skipped, not a fake calibration."""

    current = _normalize(current_weights)
    counts = count_reason_codes(decisions)
    if not counts:
        return {
            "status": "skipped",
            "version": CALIBRATOR_VERSION,
            "reason_counts": {},
            "current_weights": current,
            "proposed_weights": dict(current),
            "deltas": {key: 0.0 for key in current},
            "note": "No reason codes on the decision log. Calibrator does not invent a proposal.",
            "auto_applied": False,
        }
    raw = dict(current)
    for code, n in counts.items():
        hint = REASON_HINTS.get(code) or {}
        for key, delta in hint.items():
            if key in raw:
                raw[key] = max(0.05, raw[key] + delta * n)
    proposed = _normalize(raw)
    deltas = {key: round(proposed[key] - current[key], 4) for key in current}
    moved = any(abs(value) > 1e-9 for value in deltas.values())
    return {
        "status": "ok" if moved else "unchanged",
        "version": CALIBRATOR_VERSION,
        "reason_counts": counts,
        "current_weights": current,
        "proposed_weights": proposed,
        "deltas": deltas,
        "note": (
            "Proposal from recorded reason codes. Human must apply. "
            "Never auto-applies. Does not mint DNA claims."
        ),
        "auto_applied": False,
    }
