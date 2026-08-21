from __future__ import annotations

import pytest

from components import state


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


def test_dual_entry_context_preserves_opportunity_and_linked_mission(session):
    mission_context = state.active_context()
    assert mission_context["entry_type"] == "mission"
    assert mission_context["mission_id"] == "launch_x5_us_001"
    assert mission_context["opportunity_id"] is None

    opportunity_context = state.set_active_context("creator_opportunity", "OPP-002")
    assert opportunity_context["entry_type"] == "opportunity"
    assert opportunity_context["entry_id"] == "OPP-002"
    assert opportunity_context["opportunity_id"] == "OPP-002"
    assert opportunity_context["mission_id"] == "launch_x5_us_001"
    assert opportunity_context["creator_id"] == "C003"
    assert opportunity_context["evidence"]

    state.select_creator("C017")
    assert state.active_context()["creator_id"] == "C017"
    assert state.active_context()["opportunity_id"] == "OPP-002"


def test_unlinked_opportunity_does_not_materialize_mission_match(session):
    context = state.set_active_context("opportunity", "OPP-001")
    assert context["mission_id"] is None
    assert state.ranking().empty
    assert state.match_for_creator("C004") is None


def test_unlinked_opportunity_decision_uses_reason_code_without_match(session):
    state.set_active_context("opportunity", "OPP-003")
    decision = state.save_decision(
        "C009",
        "Rejected",
        "Evidence did not pass qualification",
        reason_code="opportunity_rejected",
        note="Regional team should collect a newer evidence sample.",
        evidence=["opportunity://OPP-003"],
    )

    assert decision["match_id"] is None
    assert decision["reason_code"] == "opportunity_rejected"
    assert decision["note"].startswith("Regional team")
    assert state.creator_state("C009") == "closed_lost"


def test_invalid_transition_does_not_mutate_state_or_audit_log(session):
    state.set_active_context("opportunity", "OPP-003")
    assert state.creator_state("C009") == "discovered"

    with pytest.raises(ValueError, match="illegal collaboration transition"):
        state.transition_creator_state(
            "C009",
            "approved",
            actor="Mexico Marketing",
            reason="Attempted to skip required review",
            evidence=["opportunity://OPP-003"],
        )

    assert state.creator_state("C009") == "discovered"
    assert state.workflow_events() == []
    assert session.outreach_cases == []

    with pytest.raises(ValueError, match="illegal collaboration transition"):
        state.transition_creator_state(
            "C009",
            "discovered",
            actor="Mexico Marketing",
            reason="Same-state write is not a transition",
            evidence=["opportunity://OPP-003"],
        )


def test_unapproved_creator_cannot_create_outreach_case(session):
    state.set_active_context("opportunity", "OPP-003")

    with pytest.raises(ValueError, match="requires an approved"):
        state.ensure_outreach_case("C009")

    assert session.outreach_cases == []


def test_approval_creates_one_idempotent_outreach_case(session):
    state.set_active_context("opportunity", "OPP-002")
    assert state.creator_state("C003") == "shortlisted"

    state.transition_creator_state(
        "C003",
        "approved",
        actor="Global Creator Team",
        reason="Evidence and commercial fit approved",
        evidence=["opportunity://OPP-002"],
    )
    first = state.ensure_outreach_case("C003")
    second = state.ensure_outreach_case("C003")

    assert first == second
    assert len(session.outreach_cases) == 1
    assert session.outreach_cases[0]["status"] == "approved"
    assert session.outreach_cases[0]["opportunity_id"] == "OPP-002"
    assert session.outreach_cases[0]["mission_id"] == "launch_x5_us_001"
    assert session.outreach_cases[0]["channel"] == "Not selected"
    assert session.outreach_cases[0]["next_action"] == "Advance to contacted"
    assert session.outreach_cases[0]["updated_at"]
    assert next(item for item in session.opportunities if item["opportunity_id"] == "OPP-002")["status"] == "approved"
    assert len(state.workflow_events()) == 1
    assert state.workflow_events()[0]["mission_id"] == "launch_x5_us_001"
    assert state.workflow_events()[0]["opportunity_id"] == "OPP-002"


def test_ranking_materializes_match_and_decision_references_it(session):
    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    match = state.match_for_creator(creator_id)

    assert match is not None
    assert match["match_id"] == f"match_launch_x5_us_001_{creator_id}"
    assert match["mission_id"] == "launch_x5_us_001"
    assert match["evidence"]

    first = state.save_decision(creator_id, "Approved", "Top-ranked shortlisted creator approved")
    second = state.save_decision(creator_id, "Approved", "Repeated approval request")
    assert first == second
    assert session.decision_log[-1]["match_id"] == match["match_id"]
    assert session.decision_log[-1]["reason_code"] == "strong_fit"
    assert session.decision_log[-1]["note"] == "Top-ranked shortlisted creator approved"
    assert first["coupon"].startswith(f"X5-{creator_id}-")
    assert "utm_source=instaspark" in first["deeplink"]
    assert "utm_medium=creator" in first["deeplink"]
    assert len(session.decision_log) == 1
    assert len(session.outreach_cases) == 1
    assert session.outreach_cases[0]["coupon"] == first["coupon"]
    assert state.tracking_assets()[0]["coupon"] == first["coupon"]


def test_switching_roots_isolates_creator_workflow_state(session):
    state.set_active_context("opportunity", "OPP-002")
    state.transition_creator_state(
        "C003",
        "approved",
        actor="Global Creator Team",
        reason="Approved from creator-first entry",
        evidence=["opportunity://OPP-002"],
    )
    assert state.creator_state("C003") == "approved"

    state.set_active_context("mission", "launch_x5_us_001")
    assert state.creator_state("C003") == "qualified"


def test_workflow_board_is_derived_from_current_context(session):
    from src.domain import WORKFLOW_STATES

    board = state.workflow_board()
    assert list(board) == list(WORKFLOW_STATES[2:])
    assert {record["creator_id"] for record in board["shortlisted"]} == set(session.shortlist_ids)
    assert sum(len(records) for records in board.values()) == 3
    assert board["approved"] == []
    assert board["contacted"] == []
    assert board["measured"] == []
    assert board["closed_lost"] == []


def test_human_decision_is_written_to_sqlite(session):
    from infra import repository

    state.set_active_context("opportunity", "OPP-003")
    state.save_decision(
        "C009",
        "Rejected",
        "Evidence did not pass qualification",
        reason_code="opportunity_rejected",
    )

    rows = repository.load_decisions()
    assert len(rows) == 1
    assert rows[0]["creator_id"] == "C009"
    assert rows[0]["decision"] == "Rejected"
    assert rows[0]["reason"] == "Evidence did not pass qualification"


def test_operator_work_survives_a_new_session(session, monkeypatch):
    state.set_active_context("opportunity", "OPP-002")
    state.save_decision(
        "C003",
        "Approved",
        "Evidence and commercial fit approved",
        reason_code="strong_fit",
    )

    fresh = SessionState()
    monkeypatch.setattr(state.st, "session_state", fresh)
    state.bootstrap_state()

    assert fresh["active_entry_type"] == "opportunity"
    assert fresh["active_opportunity_id"] == "OPP-002"
    assert any(item["creator_id"] == "C003" and item["decision"] == "Approved" for item in fresh["decision_log"])
    assert state.creator_state("C003") == "approved"


def test_viewer_cannot_save_decision_or_reset(session):
    session.auth_user = {"username": "demo", "role": "viewer", "display_name": "Demo Viewer"}
    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    with pytest.raises(PermissionError, match="read-only"):
        state.save_decision(creator_id, "Approved", "Viewer should not approve")
    with pytest.raises(PermissionError, match="read-only"):
        state.reset_demo()


def test_approval_issues_unique_coupons_per_creator(session):
    ranked = state.ranking()
    first_id = ranked.iloc[0]["creator_id"]
    second_id = ranked.iloc[1]["creator_id"]
    first = state.save_decision(first_id, "Approved", "Approve first shortlist")
    second = state.save_decision(second_id, "Approved", "Approve second shortlist")
    assert first["coupon"] != second["coupon"]
    assert first["deeplink"] != second["deeplink"]
    assert first["coupon"].startswith(f"X5-{first_id}-")
    assert second["coupon"].startswith(f"X5-{second_id}-")
    assert len(state.tracking_assets()) == 2


def test_record_performance_event_drives_roi_and_survives_reload(session, monkeypatch):
    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    decision = state.save_decision(creator_id, "Approved", "Approve so a coupon exists")

    assert state.performance_events() == []
    assert decision["coupon"].startswith(f"X5-{creator_id}-")

    event = state.record_performance_event(
        creator_id,
        orders=8,
        revenue_usd=2400,
        spend_usd=800,
        coupon=decision["coupon"],
        utm=decision.get("deeplink"),
        note="Operator-entered conversion",
    )

    assert state.creator_state(creator_id) == "approved"

    events = state.performance_events()
    assert len(events) == 1
    assert event["entry_id"] == session.active_mission_id
    assert event["coupon"] == decision["coupon"]
    assert event["recorded_at"]
    assert event["market"]
    revenue = sum(float(item["revenue_usd"]) for item in events)
    spend = sum(float(item["spend_usd"]) for item in events)
    roi = revenue / spend
    assert roi == pytest.approx(3.0)
    assert roi != pytest.approx(4.56)

    fresh = SessionState()
    monkeypatch.setattr(state.st, "session_state", fresh)
    state.bootstrap_state()
    restored = state.performance_events()
    assert len(restored) == 1
    assert restored[0]["revenue_usd"] == 2400
    assert restored[0]["spend_usd"] == 800


def test_viewer_cannot_record_performance_event(session):
    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    state.save_decision(creator_id, "Approved", "Approve before viewer tries to record")
    _advance_linear(creator_id, "published", reason="Walk legal hops to published")
    assert state.creator_state(creator_id) == "published"
    session.auth_user = {"username": "demo", "role": "viewer", "display_name": "Demo Viewer"}
    with pytest.raises(PermissionError, match="read-only"):
        state.record_performance_event(creator_id, orders=1, revenue_usd=100, spend_usd=50)
    assert state.creator_state(creator_id) == "published"
    assert state.performance_events_for(creator_id) == []


def test_live_youtube_evidence_attaches_once_and_blocks_viewer(session):
    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    channel = {
        "channel_id": "UC123",
        "title": "Trail Cam",
        "url": "https://www.youtube.com/channel/UC123",
        "source": "youtube_data_api",
        "country": "US",
        "subscriber_count": 12000,
    }
    first = state.attach_live_evidence(creator_id, channel)
    second = state.attach_live_evidence(creator_id, channel)
    assert first == second
    assert len(state.live_evidence_for(creator_id)) == 1
    session.auth_user = {"username": "demo", "role": "viewer", "display_name": "Demo Viewer"}
    with pytest.raises(PermissionError, match="read-only"):
        state.attach_live_evidence(
            creator_id,
            {**channel, "channel_id": "UC999", "url": "https://www.youtube.com/channel/UC999"},
        )


def test_attaching_live_evidence_increases_ranking_score(session):
    ranked = state.ranking()
    creator_id = ranked.iloc[-1]["creator_id"]
    before = float(ranked.loc[ranked["creator_id"] == creator_id, "total_score"].iloc[0])
    state.attach_live_evidence(
        creator_id,
        {
            "channel_id": "UC-SCORE",
            "title": "Proof Channel",
            "url": "https://www.youtube.com/channel/UC-SCORE",
            "source": "youtube_data_api",
        },
    )
    after_ranked = state.ranking()
    after = float(after_ranked.loc[after_ranked["creator_id"] == creator_id, "total_score"].iloc[0])
    bonus = float(after_ranked.loc[after_ranked["creator_id"] == creator_id, "live_proof_bonus"].iloc[0])
    assert bonus > 0
    assert after > before


def test_empty_nl_query_does_not_change_state_ranking_order(session):
    baseline = state.ranking()
    session.creator_nl_query = ""
    empty = state.ranking()
    session.creator_nl_query = "   "
    whitespace = state.ranking()
    assert list(baseline["creator_id"]) == list(empty["creator_id"]) == list(whitespace["creator_id"])


def test_live_evidence_is_visible_on_compare_and_outreach(session):
    from views import creator_compare, outreach_operations

    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    state.attach_live_evidence(
        creator_id,
        {
            "channel_id": "UC123",
            "title": "Trail Cam Live",
            "url": "https://www.youtube.com/channel/UC123",
            "source": "youtube_data_api",
        },
    )
    panel = creator_compare._evidence_panel(ranked.iloc[0].to_dict(), state.active_context())
    assert "Trail Cam Live" in panel
    assert "https://www.youtube.com/channel/UC123" in panel
    assert "youtube_data_api" in panel
    assert "is-video" not in panel
    assert "42s" not in panel
    assert "60s" not in panel
    assert "78s" not in panel
    assert "View more content (not wired)" in panel

    state.save_decision(creator_id, "Approved", "Need the creator on the outreach board")
    html = outreach_operations._kanban(state.workflow_board())
    assert "Live evidence: 1 attached" in html


def test_mission_health_moves_with_shortlist_approve_and_performance_event(session):
    for record in session.creator_workflows.values():
        record["state"] = "qualified"
    session.shortlist_ids = []
    empty = state.mission_health_snapshot()
    assert empty["band"] == "needs_shortlist"
    assert empty["score"] == 28
    assert empty["counts"]["shortlisted"] == 0
    assert empty["counts"]["performance_events"] == 0

    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    state.transition_creator_state(
        creator_id,
        "shortlisted",
        actor="Olivia Chen",
        reason="Operator shortlisted from Search",
        evidence=["search://shortlist"],
    )
    matching = state.mission_health_snapshot()
    assert matching["band"] == "matching"
    assert matching["score"] == 54
    assert matching["counts"]["shortlisted"] >= 1
    assert matching["counts"]["approved"] == 0

    decision = state.save_decision(creator_id, "Approved", "Approve so tracking exists")
    live = state.mission_health_snapshot()
    assert live["band"] == "outreach_live"
    assert live["score"] == 72
    assert live["counts"]["approved"] >= 1
    assert live["counts"]["tracking_assets"] >= 1
    assert live["counts"]["performance_events"] == 0

    state.record_performance_event(
        creator_id,
        orders=2,
        revenue_usd=400,
        spend_usd=100,
        coupon=decision["coupon"],
    )
    measured = state.mission_health_snapshot()
    assert measured["band"] == "measured"
    assert measured["score"] == 88
    assert measured["counts"]["performance_events"] == 1
    assert "health_score" not in session.missions[session.active_mission_id]


def _launch_progress_snapshot():
    from src.domain import launch_progress, pipeline_counts

    counts = pipeline_counts(state.workflow_summary())
    return launch_progress(
        shortlisted=counts["shortlisted"],
        approved=counts["approved"],
        tracking_assets=len(state.tracking_assets()),
        performance_events=len(state.performance_events()),
    )


def test_launch_checklist_moves_after_shortlist_approve_and_event(session):
    for record in session.creator_workflows.values():
        record["state"] = "qualified"
    session.shortlist_ids = []
    empty = _launch_progress_snapshot()
    assert empty["upcoming"][0]["title"] == "Shortlist creators"
    assert empty["steps"][0]["status"] == "current"

    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    state.transition_creator_state(
        creator_id,
        "shortlisted",
        actor="Olivia Chen",
        reason="Operator shortlisted from Search",
        evidence=["search://shortlist"],
    )
    matching = _launch_progress_snapshot()
    assert matching["upcoming"][0]["title"] == "Approve one creator"
    assert matching["steps"][0]["status"] == "done"
    assert matching["steps"][1]["status"] == "current"

    decision = state.save_decision(creator_id, "Approved", "Approve so tracking exists")
    live = _launch_progress_snapshot()
    assert live["upcoming"][0]["title"] == "Record a conversion on Growth Review"
    assert live["steps"][1]["status"] == "done"
    assert live["steps"][2]["status"] == "current"

    state.record_performance_event(
        creator_id,
        orders=2,
        revenue_usd=400,
        spend_usd=100,
        coupon=decision["coupon"],
    )
    measured = _launch_progress_snapshot()
    assert [step["status"] for step in measured["steps"]] == ["done", "done", "done"]
    assert measured["upcoming"][0]["title"] == "Review recorded outcomes"


def test_growth_filters_exclude_other_market_and_old_window(session):
    from datetime import datetime, timedelta, timezone

    from src.domain import attributed_roi, filter_dated_records, filter_performance_events

    ranked = state.ranking()
    first_id = ranked.iloc[0]["creator_id"]
    second_id = ranked.iloc[1]["creator_id"]
    first = state.save_decision(first_id, "Approved", "Approve US conversion path")
    second = state.save_decision(second_id, "Approved", "Approve Mexico conversion path")
    now = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)

    state.record_performance_event(
        first_id,
        orders=2,
        revenue_usd=200,
        spend_usd=100,
        coupon=first["coupon"],
        market="United States",
        recorded_at=now,
    )
    state.record_performance_event(
        second_id,
        orders=9,
        revenue_usd=900,
        spend_usd=100,
        coupon=second["coupon"],
        market="Mexico",
        recorded_at=now - timedelta(days=40),
    )

    events = state.performance_events()
    us_week = filter_performance_events(events, period_days=7, market="United States", now=now)
    assert len(us_week) == 1
    assert us_week[0]["market"] == "United States"
    assert attributed_roi(us_week) == pytest.approx(2.0)

    mx_week = filter_performance_events(events, period_days=7, market="Mexico", now=now)
    assert mx_week == []
    assert attributed_roi(mx_week) == 0

    mx_all = filter_performance_events(events, period_days=None, market="Mexico", now=now)
    assert len(mx_all) == 1
    assert attributed_roi(mx_all) == pytest.approx(9.0)

    assets = state.tracking_assets()
    assert all(item.get("market") for item in assets)
    us_assets = filter_dated_records(
        assets,
        period_days=None,
        market="United States",
        timestamp_field="created_at",
        market_field="market",
    )
    mx_assets = filter_dated_records(
        assets,
        period_days=None,
        market="Mexico",
        timestamp_field="created_at",
        market_field="market",
    )
    other = filter_dated_records(
        assets,
        period_days=None,
        market="Japan",
        timestamp_field="created_at",
        market_field="market",
    )
    assert {item["creator_id"] for item in us_assets + mx_assets} == {first_id, second_id}
    assert other == []


def test_save_content_asset_appends_in_review_for_active_creator(session):
    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    assert state.content_assets_in_review_count() == 0
    first = state.save_content_asset(
        creator_id,
        "X5 brief · Adventurous",
        "Show the product in a real use case. Adventurous tone.",
    )
    second = state.save_content_asset(
        creator_id,
        "X5 brief · Authentic",
        "Keep the verdict native. Authentic tone.",
    )
    assert first["asset_id"] != second["asset_id"]
    assert first["status"] == "in_review"
    assert first["creator_id"] == creator_id
    assert first["excerpt"]
    assert first["created_at"]
    assert first["entry_id"] == session.active_mission_id
    assert state.creator_state(creator_id) == "shortlisted"
    assert state.content_assets_in_review_count() == 2

    from views import launch_mission, outreach_operations

    actions = launch_mission._actions_card(state.workflow_summary(), "United States", 0, 0, state.content_assets_in_review_count())
    assert "2 content assets in review" in actions
    assert "Saved briefs from Content Studio" in actions
    caption_n = state.content_assets_in_review_count()
    html = outreach_operations._kanban(state.workflow_board())
    assert html
    assert caption_n == 2


def test_viewer_cannot_save_content_asset(session):
    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    session.auth_user = {"username": "demo", "role": "viewer", "display_name": "Demo Viewer"}
    with pytest.raises(PermissionError, match="read-only"):
        state.save_content_asset(creator_id, "Viewer brief", "Should not persist")
    assert state.content_assets() == []
    assert state.content_assets_in_review_count() == 0
    assert state.creator_state(creator_id) == "shortlisted"


def test_saving_brief_advances_approved_creator_to_content_in_review(session):
    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    state.save_decision(creator_id, "Approved", "Approve so outreach exists")
    assert state.creator_state(creator_id) == "approved"

    asset = state.save_content_asset(
        creator_id,
        "X5 brief · Adventurous",
        "Show the product in a real use case.",
    )
    assert asset["status"] == "in_review"
    assert state.creator_state(creator_id) == "content_in_review"

    hops = [
        (event["from_state"], event["to_state"])
        for event in state.workflow_events()
        if event["reason"] == "Brief generated in Content Studio"
    ]
    assert hops == [
        ("approved", "contacted"),
        ("contacted", "negotiating"),
        ("negotiating", "contracted"),
        ("contracted", "content_in_review"),
    ]
    board = state.workflow_board()
    assert any(item["creator_id"] == creator_id for item in board.get("content_in_review", []))
    assert not any(item["creator_id"] == creator_id for item in board.get("approved", []))

    from views import outreach_operations

    html = outreach_operations._kanban(board)
    name = ranked.iloc[0]["creator_name"]
    assert "Content In Review" in html
    review_col = html.split("Content In Review", 1)[1]
    if "Published" in review_col:
        review_col = review_col.split("Published", 1)[0]
    assert name in review_col


def test_saving_brief_is_noop_when_not_in_outreach_or_already_past_review(session):
    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    second_id = ranked.iloc[1]["creator_id"]
    assert state.creator_state(creator_id) == "shortlisted"

    state.save_content_asset(creator_id, "Shortlist brief", "Must not skip to content review.")
    assert state.creator_state(creator_id) == "shortlisted"
    assert state.workflow_events() == []

    state.save_decision(second_id, "Approved", "Approve second creator")
    state.transition_creator_state(
        second_id,
        "contacted",
        actor="Olivia Chen",
        reason="Operator moved outreach",
        evidence=["outreach://manual"],
    )
    state.transition_creator_state(
        second_id,
        "negotiating",
        actor="Olivia Chen",
        reason="Operator moved outreach",
        evidence=["outreach://manual"],
    )
    state.transition_creator_state(
        second_id,
        "contracted",
        actor="Olivia Chen",
        reason="Operator moved outreach",
        evidence=["outreach://manual"],
    )
    state.transition_creator_state(
        second_id,
        "content_in_review",
        actor="Olivia Chen",
        reason="Operator moved outreach",
        evidence=["outreach://manual"],
    )
    state.transition_creator_state(
        second_id,
        "published",
        actor="Olivia Chen",
        reason="Operator published",
        evidence=["outreach://manual"],
    )
    before = len(state.workflow_events())
    state.save_content_asset(second_id, "Published brief", "Already past content review.")
    assert state.creator_state(second_id) == "published"
    assert len(state.workflow_events()) == before

    state.set_active_context("opportunity", "OPP-003")
    lost_id = "C009"
    state.save_decision(
        lost_id,
        "Rejected",
        "Evidence did not pass qualification",
        reason_code="opportunity_rejected",
    )
    assert state.creator_state(lost_id) == "closed_lost"
    lost_events = len(state.workflow_events())
    state.save_content_asset(lost_id, "Lost brief", "Closed lost must not reopen.")
    assert state.creator_state(lost_id) == "closed_lost"
    assert len(state.workflow_events()) == lost_events


def test_viewer_cannot_advance_outreach_by_saving_a_brief(session):
    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    state.save_decision(creator_id, "Approved", "Approve before viewer tries to write")
    assert state.creator_state(creator_id) == "approved"
    session.auth_user = {"username": "demo", "role": "viewer", "display_name": "Demo Viewer"}
    with pytest.raises(PermissionError, match="read-only"):
        state.save_content_asset(creator_id, "Viewer brief", "Should not persist")
    assert state.creator_state(creator_id) == "approved"
    assert state.content_assets() == []


def test_save_linked_opportunity_activates_ranking_and_origin_shortlist(session):
    from services.opportunity_service import create_opportunity

    record = create_opportunity(
        session.opportunities,
        creator_id="C004",
        title="Mexico bilingual test",
        source="Operator capture",
        market="Mexico",
        language="Spanish",
        hypothesis="Creator-first signal should drive the workspace.",
        evidence=["opportunity://manual"],
        owner="Regional Creator Team",
        linked_mission_id="launch_x5_us_001",
    )
    saved = state.save_opportunity(record)
    context = state.active_context()
    assert context["entry_type"] == "opportunity"
    assert context["opportunity_id"] == saved["opportunity_id"]
    assert context["mission_id"] == "launch_x5_us_001"
    assert session.selected_creator_id == "C004"
    assert session.shortlist_ids == ["C004"]
    assert session.compare_ids == ["C004"]
    ranked = state.ranking()
    assert not ranked.empty
    assert "C004" in set(ranked["creator_id"])
    linked = state.opportunities_for_mission("launch_x5_us_001")
    assert saved["opportunity_id"] in {item["opportunity_id"] for item in linked}


def test_save_unlinked_opportunity_activates_without_inventing_matches(session):
    from services.opportunity_service import create_opportunity

    record = create_opportunity(
        session.opportunities,
        creator_id="C009",
        title="Unlinked signal",
        source="Nomination",
        market="Mexico",
        language="Spanish",
        hypothesis="Qualify before linking a mission.",
        evidence=["opportunity://manual"],
        owner="Mexico Marketing",
    )
    state.save_opportunity(record)
    assert state.active_context()["entry_type"] == "opportunity"
    assert state.active_context()["mission_id"] is None
    assert state.ranking().empty
    assert session.shortlist_ids == ["C009"]


def test_link_opportunity_is_visible_on_mission_and_preserves_evidence(session):
    original = next(item for item in session.opportunities if item["opportunity_id"] == "OPP-001")
    evidence = list(original["evidence"])
    linked = state.link_opportunity_to_mission("OPP-001", "launch_x5_us_001")
    assert linked["linked_mission_id"] == "launch_x5_us_001"
    assert linked["evidence"] == evidence
    visible = {item["opportunity_id"] for item in state.opportunities_for_mission("launch_x5_us_001")}
    assert {"OPP-001", "OPP-002"} <= visible
    assert "OPP-003" not in visible
    assert state.active_context()["entry_type"] == "mission"


def test_switching_to_opportunity_replaces_then_restores_mission_shortlist(session):
    original = list(session.shortlist_ids)
    assert original
    state.set_active_context("opportunity", "OPP-002")
    assert session.shortlist_ids == ["C003"]
    assert session.compare_ids == ["C003"]
    state.set_active_context("mission", "launch_x5_us_001")
    assert session.shortlist_ids == original


def test_contact_pack_includes_coupon_and_utm_for_approved_creator(session):
    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    state.save_decision(creator_id, "Approved", "Approve so the contact pack exists")
    pack = state.contact_pack_for(creator_id)
    blob = state.format_contact_pack(pack)

    assert pack["coupon"].startswith(f"X5-{creator_id}-")
    assert "utm_source=instaspark" in pack["deeplink"]
    assert "utm_medium=creator" in pack["deeplink"]
    assert pack["coupon"] in blob
    assert pack["deeplink"] in blob
    assert "Coupon:" in blob
    assert "UTM:" in blob
    assert pack["outreach_message"]
    assert pack["coupon"] in pack["outreach_message"]
    assert pack["deeplink"] in pack["outreach_message"]
    assert session.outreach_cases[0]["outreach_message"] == pack["outreach_message"]
    assert session.outreach_cases[0]["outreach_tone"] == "Professional"

    from views import outreach_operations

    html = outreach_operations._kanban(state.workflow_board())
    assert "Contact pack" in html


def test_contact_pack_includes_brief_excerpt_and_live_evidence(session):
    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    state.save_decision(creator_id, "Approved", "Approve before attaching evidence")
    state.save_content_asset(
        creator_id,
        "X5 brief · Adventurous",
        "Show the product in a real use case. Keep the verdict native.",
    )
    state.attach_live_evidence(
        creator_id,
        {
            "channel_id": "UC-demo-pack",
            "title": "Demo channel",
            "url": "https://www.youtube.com/channel/UC-demo-pack",
            "source": "youtube_data_api",
        },
    )
    pack = state.contact_pack_for(creator_id)
    blob = state.format_contact_pack(pack)
    assert "Show the product in a real use case." in pack["brief_excerpt"]
    assert pack["brief_excerpt"] in blob
    assert pack["live_evidence_urls"] == ["https://www.youtube.com/channel/UC-demo-pack"]
    assert "https://www.youtube.com/channel/UC-demo-pack" in blob

    refreshed = state.refresh_outreach_message(creator_id, tone="Adventurous")
    assert "Adventurous" in refreshed["outreach_message"]
    assert refreshed["brief_excerpt"] in refreshed["outreach_message"]
    assert session.outreach_cases[0]["outreach_message"] == refreshed["outreach_message"]
    assert session.outreach_cases[0]["outreach_tone"] == "Adventurous"


def test_viewer_cannot_regenerate_outreach_message(session):
    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    state.save_decision(creator_id, "Approved", "Approve before viewer tries to regenerate")
    original = session.outreach_cases[0]["outreach_message"]
    session.auth_user = {"username": "demo", "role": "viewer", "display_name": "Demo Viewer"}

    pack = state.contact_pack_for(creator_id)
    assert pack["coupon"].startswith(f"X5-{creator_id}-")
    assert original in state.format_contact_pack(pack)

    with pytest.raises(PermissionError, match="read-only"):
        state.refresh_outreach_message(creator_id, tone="Authentic")
    assert session.outreach_cases[0]["outreach_message"] == original


def _advance_linear(creator_id: str, to_state: str, *, reason: str) -> None:
    hops = 0
    while state.creator_state(creator_id) != to_state:
        nxt = state.next_linear_creator_state(creator_id)
        assert nxt is not None, state.creator_state(creator_id)
        state.transition_creator_state(
            creator_id,
            nxt,
            actor="Operator",
            reason=reason,
            evidence=["test://linear-advance"],
        )
        hops += 1
        assert hops < 12


def test_advance_approved_to_contacted_records_reason_on_timeline(session):
    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    state.save_decision(creator_id, "Approved", "Approve so outreach exists")
    assert state.creator_state(creator_id) == "approved"
    assert state.next_linear_creator_state(creator_id) == "contacted"

    record = state.transition_creator_state(
        creator_id,
        "contacted",
        actor="Olivia Chen",
        reason="Operator sent the contact pack",
        evidence=["outreach://contact-pack"],
    )
    assert record["state"] == "contacted"
    events = state.workflow_events_for(creator_id)
    assert any(
        event["from_state"] == "approved"
        and event["to_state"] == "contacted"
        and event["reason"] == "Operator sent the contact pack"
        and event["actor"] == "Olivia Chen"
        for event in events
    )


def test_illegal_skip_from_approved_raises_and_does_not_mutate(session):
    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    state.save_decision(creator_id, "Approved", "Approve so outreach exists")
    before = list(state.workflow_events_for(creator_id))

    with pytest.raises(ValueError, match="illegal collaboration transition"):
        state.transition_creator_state(
            creator_id,
            "published",
            actor="Operator",
            reason="Skip ahead",
            evidence=["outreach://illegal-skip"],
        )
    assert state.creator_state(creator_id) == "approved"
    assert state.workflow_events_for(creator_id) == before


def test_viewer_cannot_advance_creator_state(session):
    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    state.save_decision(creator_id, "Approved", "Approve before viewer tries to advance")
    session.auth_user = {"username": "demo", "role": "viewer", "display_name": "Demo Viewer"}

    with pytest.raises(PermissionError, match="read-only"):
        state.transition_creator_state(
            creator_id,
            "contacted",
            actor="Demo Viewer",
            reason="Viewer should not advance",
            evidence=["outreach://viewer"],
        )
    assert state.creator_state(creator_id) == "approved"


def test_published_does_not_create_performance_events_and_measured_needs_one(session):
    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    state.save_decision(creator_id, "Approved", "Approve so the case exists")
    _advance_linear(creator_id, "published", reason="Walk legal hops to published")

    assert state.creator_state(creator_id) == "published"
    assert state.performance_events() == []
    assert state.performance_events_for(creator_id) == []
    assert state.next_linear_creator_state(creator_id) == "measured"

    with pytest.raises(ValueError, match="Mark measured only after recording events"):
        state.transition_creator_state(
            creator_id,
            "measured",
            actor="Operator",
            reason="Mark measured without evidence",
            evidence=["outreach://measured-too-soon"],
        )
    assert state.creator_state(creator_id) == "published"

    state.record_performance_event(creator_id, orders=1, revenue_usd=120, spend_usd=40)
    assert state.creator_state(creator_id) == "measured"
    assert len(state.performance_events_for(creator_id)) == 1
    assert any(
        event["to_state"] == "measured"
        and event["reason"] == "Conversion recorded on Growth Review"
        for event in state.workflow_events_for(creator_id)
    )


def test_approved_record_does_not_skip_to_measured(session):
    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    state.save_decision(creator_id, "Approved", "Approve so a coupon exists")
    assert state.creator_state(creator_id) == "approved"

    state.record_performance_event(creator_id, orders=1, revenue_usd=80, spend_usd=20)
    assert state.creator_state(creator_id) == "approved"
    assert len(state.performance_events_for(creator_id)) == 1


def test_second_event_on_measured_is_idempotent(session):
    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    state.save_decision(creator_id, "Approved", "Approve so the case exists")
    _advance_linear(creator_id, "published", reason="Walk legal hops to published")
    state.record_performance_event(creator_id, orders=1, revenue_usd=120, spend_usd=40)
    assert state.creator_state(creator_id) == "measured"

    second = state.record_performance_event(creator_id, orders=2, revenue_usd=90, spend_usd=30)
    assert second["orders"] == 2
    assert state.creator_state(creator_id) == "measured"
    assert len(state.performance_events_for(creator_id)) == 2
    measured_hops = [
        event
        for event in state.workflow_events_for(creator_id)
        if event["to_state"] == "measured"
    ]
    assert len(measured_hops) == 1


def test_kanban_keeps_empty_domain_columns_and_shows_growth_next_after_published(session):
    from views import outreach_operations

    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    board = state.workflow_board()
    html = outreach_operations._kanban(board)
    assert "Shortlisted" in html
    assert "Approved" in html
    assert "Contacted" in html
    assert "Negotiating" in html
    assert "Contracted" in html
    assert "Content In Review" in html
    assert "Published" in html
    assert "Measured" in html
    assert "in_outreach" not in html

    state.save_decision(creator_id, "Approved", "Approve so the case exists")
    _advance_linear(creator_id, "published", reason="Walk legal hops to published")
    published_board = state.workflow_board()
    assert published_board["published"]
    assert published_board["measured"] == []
    html = outreach_operations._kanban(published_board)
    assert "Record a conversion on Growth Review" in html


def test_published_with_zero_events_next_action_page_is_growth_review(session):
    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    name = ranked.iloc[0]["creator_name"]
    state.save_decision(creator_id, "Approved", "Approve so the case exists")
    _advance_linear(creator_id, "published", reason="Walk legal hops to published")

    assert state.performance_events_for(creator_id) == []
    assert state.next_outreach_action_page(creator_id) == "growth-review"

    state.prepare_growth_review_record(creator_id, choice_label=f"{name} · {creator_id}")
    assert session.selected_creator_id == creator_id
    assert session.growth_record_event_open is True
    assert session.perf_event_creator == f"{name} · {creator_id}"

    state.record_performance_event(creator_id, orders=1, revenue_usd=120, spend_usd=40)
    assert state.creator_state(creator_id) == "measured"
    assert state.next_outreach_action_page(creator_id) is None


def test_content_in_review_without_asset_next_action_page_is_content_studio(session):
    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    state.save_decision(creator_id, "Approved", "Approve so the case exists")
    _advance_linear(creator_id, "content_in_review", reason="Walk legal hops to review")

    from views import outreach_operations

    assert state.content_assets_for(creator_id) == []
    assert state.next_outreach_action_page(creator_id) == "content-studio"
    html = outreach_operations._kanban(state.workflow_board())
    assert "Create a brief in Content Studio" in html

    state.save_content_asset(creator_id, "Review brief", "Body of the brief for this mission.")
    assert state.content_assets_for(creator_id)
    assert state.next_outreach_action_page(creator_id) is None


def test_selecting_via_kanban_updates_selected_creator_id(session):
    from views import outreach_operations

    ranked = state.ranking()
    first_id = ranked.iloc[0]["creator_id"]
    second_id = ranked.iloc[1]["creator_id"]
    state.select_creator(first_id)
    assert session.selected_creator_id == first_id

    result = outreach_operations.select_kanban_creator(second_id)
    assert result == second_id
    assert session.selected_creator_id == second_id
    assert session.outreach_focus_creator_id == second_id

    html = outreach_operations._kanban(state.workflow_board(), selected_id=second_id)
    assert "is-kanban-card-selected" in html
    assert second_id in html
    assert "Measured" in html
    measured_col = html.split("Measured", 1)[1]
    assert "is-kanban-card" not in measured_col.split("Closed Lost", 1)[0]


def test_selecting_via_list_updates_selected_creator_id(session):
    from views import outreach_operations

    ranked = state.ranking()
    first_id = ranked.iloc[0]["creator_id"]
    second_id = ranked.iloc[1]["creator_id"]
    second_name = ranked.iloc[1]["creator_name"]
    state.select_creator(first_id)
    assert session.selected_creator_id == first_id

    result = outreach_operations.select_list_creator(second_id)
    assert result == second_id
    assert session.selected_creator_id == second_id
    assert session.outreach_focus_creator_id == second_id

    html = outreach_operations._list_view(state.workflow_board(), selected_id=second_id)
    assert "is-selected" in html
    assert second_name in html
    assert 'open_workspace_page' not in outreach_operations._render_list.__code__.co_names


def test_opportunity_cta_targets_growth_and_content_studio(session):
    from views import creator_opportunity

    state.set_active_context("opportunity", "OPP-002")
    creator_id = "C003"
    name = str(state.creators().set_index("creator_id").loc[creator_id]["creator_name"])

    state.transition_creator_state(
        creator_id,
        "approved",
        actor="Global Creator Team",
        reason="Evidence and commercial fit approved",
        evidence=["opportunity://OPP-002"],
    )
    _advance_linear(creator_id, "content_in_review", reason="Walk legal hops to review")
    assert state.content_assets_for(creator_id) == []
    assert creator_opportunity.opportunity_cta_page(creator_id) == "content-studio"
    assert creator_opportunity.opportunity_cta_page(creator_id) == state.next_outreach_action_page(
        creator_id
    )

    jumped = state.prepare_next_action_jump(creator_id, creator_name=name)
    assert jumped == "content-studio"
    assert session.selected_creator_id == creator_id

    state.save_content_asset(creator_id, "Review brief", "Body of the brief for this opportunity.")
    assert creator_opportunity.opportunity_cta_page(creator_id) is None

    _advance_linear(creator_id, "published", reason="Walk legal hops to published")
    assert state.performance_events_for(creator_id) == []
    assert creator_opportunity.opportunity_cta_page(creator_id) == "growth-review"

    opened = creator_opportunity.open_opportunity_cta(creator_id, creator_name=name)
    assert opened == "growth-review"
    assert session.selected_creator_id == creator_id
    assert session.growth_record_event_open is True
    assert session.perf_event_creator == f"{name} · {creator_id}"

    state.record_performance_event(creator_id, orders=1, revenue_usd=120, spend_usd=40)
    assert state.creator_state(creator_id) == "measured"
    assert creator_opportunity.opportunity_cta_page(creator_id) is None


def test_search_and_compare_cta_targets_match_helper(session):
    from views import creator_compare, creator_search

    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    name = str(ranked.iloc[0]["creator_name"])
    state.save_decision(creator_id, "Approved", "Approve so the case exists")
    _advance_linear(creator_id, "content_in_review", reason="Walk legal hops to review")
    assert state.content_assets_for(creator_id) == []

    helper = state.next_outreach_action_page(creator_id)
    assert helper == "content-studio"
    assert creator_search.search_cta_page(creator_id) == helper
    assert creator_compare.compare_cta_page(creator_id) == helper

    jumped = creator_search.open_search_cta(creator_id, creator_name=name)
    assert jumped == "content-studio"
    assert jumped == state.next_outreach_action_page(creator_id)
    assert session.selected_creator_id == creator_id

    state.save_content_asset(creator_id, "Review brief", "Body of the brief for this search.")
    assert creator_search.search_cta_page(creator_id) is None
    assert creator_compare.compare_cta_page(creator_id) is None
    assert state.next_outreach_action_page(creator_id) is None

    _advance_linear(creator_id, "published", reason="Walk legal hops to published")
    assert state.performance_events_for(creator_id) == []
    helper = state.next_outreach_action_page(creator_id)
    assert helper == "growth-review"
    assert creator_search.search_cta_page(creator_id) == helper
    assert creator_compare.compare_cta_page(creator_id) == helper

    opened = creator_compare.open_compare_cta(creator_id, creator_name=name)
    assert opened == "growth-review"
    assert session.selected_creator_id == creator_id
    assert session.growth_record_event_open is True
    assert session.perf_event_creator == f"{name} · {creator_id}"

    state.record_performance_event(creator_id, orders=1, revenue_usd=120, spend_usd=40)
    assert creator_search.search_cta_page(creator_id) is None
    assert creator_compare.compare_cta_page(creator_id) is None
    assert state.next_outreach_action_page(creator_id) is None


def test_launch_cta_targets_match_helper(session):
    from views import launch_mission

    ranked = state.ranking()
    creator_id = ranked.iloc[0]["creator_id"]
    name = str(ranked.iloc[0]["creator_name"])
    state.save_decision(creator_id, "Approved", "Approve so the case exists")
    _advance_linear(creator_id, "content_in_review", reason="Walk legal hops to review")
    assert state.content_assets_for(creator_id) == []

    helper = state.next_outreach_action_page(creator_id)
    assert helper == "content-studio"
    assert launch_mission.launch_cta_page(creator_id) == helper

    jumped = launch_mission.open_launch_cta(creator_id, creator_name=name)
    assert jumped == "content-studio"
    assert jumped == state.next_outreach_action_page(creator_id)
    assert session.selected_creator_id == creator_id

    state.save_content_asset(creator_id, "Review brief", "Body of the brief for this launch.")
    assert launch_mission.launch_cta_page(creator_id) is None
    assert state.next_outreach_action_page(creator_id) is None

    _advance_linear(creator_id, "published", reason="Walk legal hops to published")
    assert state.performance_events_for(creator_id) == []
    helper = state.next_outreach_action_page(creator_id)
    assert helper == "growth-review"
    assert launch_mission.launch_cta_page(creator_id) == helper

    opened = launch_mission.open_launch_cta(creator_id, creator_name=name)
    assert opened == "growth-review"
    assert session.selected_creator_id == creator_id
    assert session.growth_record_event_open is True
    assert session.perf_event_creator == f"{name} · {creator_id}"

    state.record_performance_event(creator_id, orders=1, revenue_usd=120, spend_usd=40)
    assert launch_mission.launch_cta_page(creator_id) is None
    assert state.next_outreach_action_page(creator_id) is None


def test_launch_cta_prefers_selected_then_workflow_creator(session):
    from views import launch_mission

    ranked = state.ranking()
    selected_id = ranked.iloc[0]["creator_id"]
    workflow_id = ranked.iloc[1]["creator_id"]
    workflow_name = str(ranked.iloc[1]["creator_name"])
    state.select_creator(selected_id)
    assert launch_mission.launch_cta_page(selected_id) is None
    assert launch_mission.launch_cta_creator() is None

    state.save_decision(workflow_id, "Approved", "Approve so the case exists")
    _advance_linear(workflow_id, "content_in_review", reason="Walk legal hops to review")
    assert state.content_assets_for(workflow_id) == []
    state.select_creator(selected_id)

    fallback = launch_mission.launch_cta_creator()
    assert fallback is not None
    assert fallback["creator_id"] == workflow_id
    assert launch_mission.launch_cta_page(fallback["creator_id"]) == "content-studio"

    state.select_creator(workflow_id)
    preferred = launch_mission.launch_cta_creator()
    assert preferred is not None
    assert preferred["creator_id"] == workflow_id
    assert preferred.get("creator_name") == workflow_name


def test_opportunity_cannot_skip_approved_to_published(session):
    from views import creator_opportunity

    state.set_active_context("opportunity", "OPP-002")
    state.transition_creator_state(
        "C003",
        "approved",
        actor="Global Creator Team",
        reason="Evidence and commercial fit approved",
        evidence=["opportunity://OPP-002"],
    )
    assert state.creator_state("C003") == "approved"
    assert state.next_linear_creator_state("C003") == "contacted"

    record = creator_opportunity.advance_opportunity_creator(
        "C003",
        actor="Global Creator Team",
        reason="Legal hop only",
        evidence=["opportunity://OPP-002"],
    )
    assert record["state"] == "contacted"
    assert state.creator_state("C003") == "contacted"

    with pytest.raises(ValueError, match="illegal collaboration transition"):
        state.transition_creator_state(
            "C003",
            "published",
            actor="Global Creator Team",
            reason="Skip ahead",
            evidence=["opportunity://OPP-002"],
        )
    assert state.creator_state("C003") == "contacted"


def test_opportunity_measured_with_zero_events_refused(session):
    from views import creator_opportunity

    state.set_active_context("opportunity", "OPP-002")
    state.transition_creator_state(
        "C003",
        "approved",
        actor="Global Creator Team",
        reason="Evidence and commercial fit approved",
        evidence=["opportunity://OPP-002"],
    )
    _advance_linear("C003", "published", reason="Walk legal hops to published")
    assert state.creator_state("C003") == "published"
    assert state.performance_events_for("C003") == []
    assert state.next_linear_creator_state("C003") == "measured"

    with pytest.raises(ValueError, match="Mark measured only after recording events"):
        creator_opportunity.advance_opportunity_creator(
            "C003",
            actor="Global Creator Team",
            reason="Mark measured without evidence",
            evidence=["opportunity://OPP-002"],
        )
    assert state.creator_state("C003") == "published"
    assert not any(event["to_state"] == "measured" for event in state.workflow_events_for("C003"))


def test_opportunity_viewer_cannot_advance(session):
    from views import creator_opportunity

    state.set_active_context("opportunity", "OPP-002")
    session.auth_user = {"username": "demo", "role": "viewer", "display_name": "Demo Viewer"}
    with pytest.raises(PermissionError, match="read-only"):
        creator_opportunity.advance_opportunity_creator(
            "C003",
            actor="Demo Viewer",
            reason="Viewer should not advance",
            evidence=["opportunity://OPP-002"],
        )
    assert state.creator_state("C003") == "shortlisted"
