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
    board = state.workflow_board()
    assert sum(len(records) for records in board.values()) == 3
    assert set(board) == {"shortlisted"}
    assert {record["creator_id"] for record in board["shortlisted"]} == set(session.shortlist_ids)


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
    session.auth_user = {"username": "demo", "role": "viewer", "display_name": "Demo Viewer"}
    with pytest.raises(PermissionError, match="read-only"):
        state.record_performance_event(creator_id, orders=1, revenue_usd=100, spend_usd=50)


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
