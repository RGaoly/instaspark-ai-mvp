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
    assert len(session.decision_log) == 1
    assert len(session.outreach_cases) == 1


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
