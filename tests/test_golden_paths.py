"""Golden-path end-to-end tests: full business chains against the real state layer.

No browser. Each chain drives ``components.state`` and the view-level export
helpers exactly as the workspace pages do, then asserts that persistence,
state transitions, audit events and KPI computations actually happened.
GAPs (steps the current code cannot complete) belong in the report, not in
fabricated fixtures — nothing here stubs around the state machine.
"""

from __future__ import annotations

import io

import pandas as pd
import pytest

from components import state
from infra import repository
from src.domain import attributed_roi, filter_performance_events


class SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


@pytest.fixture
def session(monkeypatch):
    fake = SessionState()
    monkeypatch.setattr(state.st, "session_state", fake)
    state.bootstrap_state()
    return fake


GOLDEN_ACTOR = "Golden Operator"
OVERRIDE_REASON = "Golden path: audited operator override, no model-grounded evidence pack here."


def _approve_through_gate(creator_id: str, reason: str) -> dict:
    """Approve via the real gate; record an audited override when it blocks."""

    gate = state.evidence_gate_state(creator_id)
    if gate["blocked"]:
        override = state.record_evidence_gate_override(
            creator_id,
            reason=OVERRIDE_REASON,
            actor=GOLDEN_ACTOR,
        )
        assert override["creator_id"] == creator_id
        assert override["gate_status"] == gate["status"]
    return state.save_decision(
        creator_id,
        "Approved",
        reason,
        reason_code="strong_fit",
        evidence=["golden://approval"],
    )


def test_golden_path_mission_first(session):
    """create mission → shortlist → approve → brief → publish → convert → measured."""

    # 1. Create + save a mission; save_mission activates it as the root context.
    base = next(item for item in state.missions() if item["mission_id"] == "launch_x5_us_001")
    saved = state.save_mission(
        {
            **base,
            "mission_id": "mission_golden_a",
            "name": "X5 Golden Path Launch",
            "owner": GOLDEN_ACTOR,
        }
    )
    assert saved["mission_id"] == "mission_golden_a"
    context = state.active_context()
    assert context["entry_type"] == "mission"
    assert context["mission_id"] == "mission_golden_a"

    # 2. Rank under the new mission and select the top creator.
    ranked = state.ranking()
    assert not ranked.empty
    creator_id = ranked.iloc[0]["creator_id"]
    state.select_creator(creator_id)
    assert session.selected_creator_id == creator_id
    assert state.match_for_creator(creator_id) is not None

    # 3. A fresh mission starts this creator at qualified; shortlist for real.
    assert state.creator_state(creator_id) == "qualified"
    state.transition_creator_state(
        creator_id,
        "shortlisted",
        actor=GOLDEN_ACTOR,
        reason="Golden path shortlist",
        evidence=["golden://shortlist"],
    )
    assert state.creator_state(creator_id) == "shortlisted"
    assert creator_id in session.shortlist_ids

    # 4. Approve through the evidence gate (override path when blocked).
    decision = _approve_through_gate(creator_id, "Golden path approval")
    assert decision["decision"] == "Approved"
    assert state.creator_state(creator_id) == "approved"

    # 5. OutreachCase minted with a unique coupon and UTM deeplink.
    cases = [case for case in session.outreach_cases if case["creator_id"] == creator_id]
    assert len(cases) == 1
    case = cases[0]
    assert case["coupon"].startswith(f"X5-{creator_id}-")
    assert "utm_source=instaspark" in case["deeplink"]
    assert f"utm_content={creator_id.lower()}" in case["deeplink"]
    assert decision["coupon"] == case["coupon"]

    # 6. The human decision is persisted in SQLite, not just toasted.
    stored_decisions = repository.load_decisions()
    assert any(
        row["creator_id"] == creator_id and row["decision"] == "Approved" for row in stored_decisions
    )

    # 7. Content Studio brief: saving advances approved → content_in_review.
    asset = state.save_content_asset(
        creator_id,
        "Golden brief · Adventurous",
        "Show the X5 in a real POV ride; keep the verdict native.",
    )
    assert asset["creator_id"] == creator_id
    assert asset["status"] == "in_review"
    assert state.content_assets_for(creator_id)
    assert state.creator_state(creator_id) == "content_in_review"
    brief_hops = [
        (event["from_state"], event["to_state"])
        for event in state.workflow_events_for(creator_id)
        if event["reason"] == "Brief generated in Content Studio"
    ]
    assert brief_hops[-1] == ("contracted", "content_in_review")

    # 8. Outreach advance to published.
    state.transition_creator_state(
        creator_id,
        "published",
        actor=GOLDEN_ACTOR,
        reason="Golden path publish",
        evidence=["golden://published"],
    )
    assert state.creator_state(creator_id) == "published"

    # 9. Record the conversion: event lands and published → measured fires.
    event = state.record_performance_event(
        creator_id,
        orders=12,
        revenue_usd=3600,
        spend_usd=900,
        coupon=case["coupon"],
        utm=case["deeplink"],
        note="Golden path conversion",
    )
    assert state.creator_state(creator_id) == "measured"
    assert event["event_id"] in {item["event_id"] for item in state.performance_events()}
    assert any(
        item["to_state"] == "measured" and item["reason"] == state.GROWTH_MEASURED_REASON
        for item in state.workflow_events_for(creator_id)
    )

    # 10. The event is mirrored into SQLite.
    stored = repository.load_all_state()
    assert event["event_id"] in {item["event_id"] for item in stored["performance_events"]}

    # 11. Growth Review KPI functions compute a positive ROI on the filtered view.
    filtered = filter_performance_events(
        state.performance_events(), period_days=None, market="All markets"
    )
    assert attributed_roi(filtered) == pytest.approx(4.0)
    assert attributed_roi(filtered) > 0

    # 12. Export helpers reflect this live state (no separate demo data).
    from views import creator_compare, content_studio, growth_review, launch_mission

    payload = launch_mission.mission_export_payload(
        state.active_mission(),
        state.workflow_summary(),
        state.ranking(),
        state.mission_health_snapshot(),
        tracking_n=len(state.tracking_assets()),
        in_review_n=state.content_assets_in_review_count(),
        events_n=len(state.performance_events()),
    )
    assert payload["mission"]["mission_id"] == "mission_golden_a"
    assert payload["pipeline_snapshot"]["measured"] == 1
    assert payload["metrics"]["performance_events"] == 1
    assert payload["metrics"]["measured"] == 1

    compare_csv = creator_compare._compare_export_csv(state.ranking().head(3))
    compare_frame = pd.read_csv(io.StringIO(compare_csv))
    assert creator_id in set(compare_frame["creator_id"])
    assert {"creator_name", "match_score", "match_tier", "engagement_rate_pct"} <= set(
        compare_frame.columns
    )

    growth_csv = growth_review._growth_export_csv(
        state.active_context(),
        period_key="All recorded events",
        market_key="All markets",
        events=filtered,
        summary=state.workflow_summary(),
        budget=float(state.active_context().get("budget_usd", 0)),
    )
    growth_frame = pd.read_csv(io.StringIO(growth_csv))
    event_rows = growth_frame[growth_frame["row_type"] == "event"]
    assert event_rows["event_id"].tolist() == [event["event_id"]]
    kpi = growth_frame[growth_frame["row_type"] == "kpi"].set_index("metric")["value"]
    assert float(kpi["roi"]) == pytest.approx(4.0)

    creator_row = ranked.iloc[0].to_dict()
    pack = content_studio._studio_pack(
        state.active_mission(), creator_row, tone="Adventurous", checklist=[]
    )
    brief_md = content_studio._brief_export_markdown(
        state.active_mission(), creator_row, pack, version=session.brief_version
    )
    for section in ("## Brief", "## Script", "## Hooks", "## Captions", "## Localized variants"):
        assert section in brief_md
    assert creator_row["creator_name"] in brief_md


def test_golden_path_creator_first(session):
    """inbound import → activate → assign → reply draft → approve → advance → convert."""

    # 1. Import the synthetic inbound corpus.
    result = state.import_inbound_corpus()
    assert result["imported"] == 30
    assert result["opportunities"] == 30

    # 2. Take one catalog-matched opportunity and make it the active context.
    opportunity_id = "OPP-INB-014"
    opportunity = next(
        item for item in session.opportunities if item["opportunity_id"] == opportunity_id
    )
    assert opportunity["identity_status"] == "matched"
    creator_id = opportunity["creator_id"]
    context = state.set_active_context("opportunity", opportunity_id)
    assert context["entry_type"] == "opportunity"
    assert context["opportunity_id"] == opportunity_id
    assert context["creator_id"] == creator_id

    # 3. Assign an owner: the human override lands on the routing audit trail.
    assigned = state.assign_inbound_owner(
        opportunity_id, "LATAM Creator Marketing", actor=GOLDEN_ACTOR
    )
    assert assigned["owner"] == "LATAM Creator Marketing"
    assert assigned["inbound_status"] == "mission_matched"
    overrides = [
        row for row in session.routing_decisions if row.get("human_override") == GOLDEN_ACTOR
    ]
    assert overrides and overrides[-1]["opportunity_id"] == opportunity_id

    # 4. Generate the local-language reply draft: status → reply_ready.
    replied = state.generate_inbound_reply(opportunity_id)
    assert replied["inbound_status"] == "reply_ready"
    assert replied["reply_draft"].strip()

    # 5. Approve the draft for Outreach: creator walks to approved, one case opens.
    approved = state.approve_inbound_for_outreach(
        opportunity_id,
        actor=GOLDEN_ACTOR,
        reason="Golden path inbound approval; nothing sent externally.",
    )
    assert approved["sent"] is False
    assert approved["creator_state"] == "approved"
    assert state.creator_state(creator_id) == "approved"
    case = approved["outreach_case"]
    assert case["creator_id"] == creator_id
    assert case["coupon"].startswith(f"X5-{creator_id}-")
    assert "utm_source=instaspark" in case["deeplink"]
    assert case["outreach_message"].strip()
    opportunity = next(
        item for item in session.opportunities if item["opportunity_id"] == opportunity_id
    )
    assert opportunity["status"] == "approved"
    assert opportunity["linked_mission_id"] == "launch_x5_mx_001"

    # 6. Advance outreach one governed hop: approved → contacted.
    state.transition_creator_state(
        creator_id,
        "contacted",
        actor=GOLDEN_ACTOR,
        reason="Golden path contact",
        evidence=["golden://contact"],
    )
    assert state.creator_state(creator_id) == "contacted"

    # 7. Record the conversion for this entry; state stays contacted (not published).
    event = state.record_performance_event(
        creator_id,
        orders=3,
        revenue_usd=450,
        spend_usd=150,
        coupon=case["coupon"],
        note="Golden path inbound conversion",
    )
    assert state.performance_events_for(creator_id)[-1]["event_id"] == event["event_id"]
    assert state.creator_state(creator_id) == "contacted"
    assert attributed_roi(state.performance_events()) == pytest.approx(3.0)

    # 8. The audit chain is complete: every step left a real trail.
    events = state.workflow_events_for(creator_id)
    assert events, "approval hops + contacted hop must be audited"
    for item in events:
        assert item["actor"]
        assert item["reason"]
        assert item["occurred_at"]
        assert item["evidence"]
        assert item["opportunity_id"] == opportunity_id
    hops = [(item["from_state"], item["to_state"]) for item in events]
    for (_, to_state), (next_from, _) in zip(hops, hops[1:]):
        assert to_state == next_from, f"broken hop chain: {hops}"
    assert hops[-1][1] == "contacted"

    stored_events = [
        row for row in repository.load_creator_events() if row["creator_id"] == creator_id
    ]
    state_changes = [row for row in stored_events if row["type"] == "State change"]
    assert len(state_changes) >= len(hops)

    stored = repository.load_all_state()
    assert event["event_id"] in {item["event_id"] for item in stored["performance_events"]}
    assert any(
        row.get("human_override") == GOLDEN_ACTOR and row.get("opportunity_id") == opportunity_id
        for row in stored["routing_decisions"]
    )
