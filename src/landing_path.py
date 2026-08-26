"""Pilot landing path: the operating model that closes the business loop.

This is the implementation path a judge can walk, not a slide. Each phase names
the artifact, the owner, and the exit gate. External email send stays out of
scope; the contact pack plus Advance is the operational handoff.
"""

from __future__ import annotations

from typing import Any

LANDING_PATH_ID = "pilot_2_week_x5_v1"
LANDING_PATH_VERSION = 1

PHASES: tuple[dict[str, Any], ...] = (
    {
        "id": "dna_freeze",
        "week": "Day 1–2",
        "title": "Freeze Product DNA",
        "owner": "Brand / product marketer",
        "artifact": "Versioned Product DNA (claims, scenes, visual proof, guardrails)",
        "exit_gate": "dna_id and version committed; guardrails written as checkable patterns",
        "in_this_demo": "data/product_dna.json · dna_x5_v1 · 4 claims (all_day, pov, rugged, 360)",
    },
    {
        "id": "underwrite_book",
        "week": "Day 3–5",
        "title": "Build the underwriting book",
        "owner": "Creator ops + Evidence Reader",
        "artifact": "Evidence Reader cache over public YouTube timedtext",
        "exit_gate": "Spend-ready cut is claim-underwritten; unevidenced creators cannot be approved without an audited override",
        "in_this_demo": "python -m scripts.run_evidence_reader --workers 6 → data/evidence_extractions.json",
    },
    {
        "id": "human_desk",
        "week": "Day 6–10",
        "title": "Human desk: approve, brief, handoff",
        "owner": "Operator + approver",
        "artifact": "Decision + CEG trace + localized brief + contact pack (coupon / UTM)",
        "exit_gate": "Approved creators have a grounded claim, a saved brief, and a copyable contact pack; Advance moves contacted → … → published",
        "in_this_demo": "Compare approve gate · Content Studio · Outreach contact pack. Send to Creator stays disabled; Advance is the legal hop.",
    },
    {
        "id": "measure_calibrate",
        "week": "Day 11–14",
        "title": "Measure and calibrate",
        "owner": "Growth + operator",
        "artifact": "Recorded performance events + BudgetDecision + Calibrator weight proposal",
        "exit_gate": "ROI from recorded events only; reason codes propose the next book's mix weights; human applies",
        "in_this_demo": "Growth Review conversion form · events_only_v1 budget · reason_code_calibrator_v1",
    },
)

SCALE_NEXT: tuple[str, ...] = (
    "Add the next SKU as a new Product DNA version; regenerate the Evidence Reader cache.",
    "Add caption languages the same way (public timedtext in, grounded quotes out).",
    "Optional live YouTube attach stays evidence, never a new ranked catalog row.",
    "Write OutreachCase + tracking assets to the brand CRM / Feishu table when the pilot graduates.",
    "Keep human approval on spend. Calibrator proposes; it does not auto-trade.",
)

ROLES: tuple[dict[str, str], ...] = (
    {"role": "Operator", "who": "Global creator team", "does": "Run Search, inspect the claim matrix, shortlist, write briefs, copy the contact pack, Advance the state machine."},
    {"role": "Approver", "who": "Regional marketing lead", "does": "Approve or override with a reason. Applies Calibrator weights. Signs BudgetDecision."},
    {"role": "Viewer", "who": "demo account", "does": "Read-only. Cannot approve, override, or record events."},
)

STACK: tuple[dict[str, str], ...] = (
    {"layer": "App", "choice": "Streamlit + SQLite (data/instaspark.db)", "why": "One command, one file of state, viewer write-lock."},
    {"layer": "Host", "choice": "Local, Docker, or Streamlit Cloud from GitHub main", "why": "Same app.py + requirements.txt. Secrets stay in the host, never in git."},
    {"layer": "Model", "choice": "OpenAI-compatible LLM_API_KEY (Evidence Reader + BriefWriter)", "why": "No key → Evidence Reader blocks, spend-ready cut blocked, BriefWriter degrades to template. No keyword fake."},
    {"layer": "Evidence", "choice": "Public YouTube timedtext + committed extraction cache", "why": "Reproducible underwriting book without live keys at demo time."},
)


def landing_path() -> dict[str, Any]:
    return {
        "path_id": LANDING_PATH_ID,
        "version": LANDING_PATH_VERSION,
        "horizon": "2-week pilot, 1 SKU, 2 markets, 60-channel public catalog",
        "closed_loop": (
            "Mission/Opportunity → claim-underwritten Match → human Decision → "
            "Brief → contact pack + Advance → PerformanceEvent → BudgetDecision → Calibrator"
        ),
        "phases": [dict(item) for item in PHASES],
        "roles": [dict(item) for item in ROLES],
        "stack": [dict(item) for item in STACK],
        "scale_next": list(SCALE_NEXT),
        "out_of_scope": [
            "Live mailbox send (Send to Creator stays disabled)",
            "TikTok / Instagram ingest",
            "Creator payout",
            "First-party conversion claim",
        ],
        "note": "This path is the operating model of the running demo, not a future slide.",
    }
