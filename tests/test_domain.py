from datetime import datetime, timezone

import pytest

from src.domain import (
    CollaborationStatus,
    EntryType,
    OutreachCase,
    WORKFLOW_STATES,
    can_transition,
    transition_event,
)


def test_workflow_exposes_canonical_state_order():
    assert WORKFLOW_STATES == (
        "discovered",
        "qualified",
        "shortlisted",
        "approved",
        "contacted",
        "negotiating",
        "contracted",
        "content_in_review",
        "published",
        "measured",
        "closed_lost",
    )


@pytest.mark.parametrize(
    ("from_state", "to_state"),
    [
        ("discovered", "qualified"),
        ("qualified", "shortlisted"),
        ("shortlisted", "approved"),
        ("approved", "contacted"),
        ("contacted", "negotiating"),
        ("negotiating", "contracted"),
        ("contracted", "content_in_review"),
        ("content_in_review", "published"),
        ("published", "measured"),
    ],
)
def test_linear_transitions_are_legal(from_state, to_state):
    assert can_transition(from_state, to_state)


@pytest.mark.parametrize(
    "from_state",
    [
        "discovered",
        "qualified",
        "shortlisted",
        "approved",
        "contacted",
        "negotiating",
    ],
)
def test_precontract_states_can_close_lost(from_state):
    assert can_transition(from_state, "closed_lost")


@pytest.mark.parametrize(
    ("from_state", "to_state"),
    [
        ("discovered", "approved"),
        ("approved", "qualified"),
        ("contracted", "closed_lost"),
        ("content_in_review", "closed_lost"),
        ("published", "closed_lost"),
        ("measured", "published"),
        ("closed_lost", "discovered"),
        ("not_a_state", "qualified"),
    ],
)
def test_invalid_or_terminal_transitions_are_rejected(from_state, to_state):
    assert not can_transition(from_state, to_state)


def test_transition_event_contains_complete_audit_context():
    occurred_at = datetime(2026, 8, 6, 9, 30, tzinfo=timezone.utc)

    event = transition_event(
        entity_id="outreach-42",
        from_state="qualified",
        to_state="shortlisted",
        actor="olivia.chen",
        reason="Strong audience and content fit",
        evidence=["profile://creator-7", "scorecard://match-9"],
        entry_type="launch_mission",
        entry_id="mission-1",
        timestamp=occurred_at,
    )

    assert event.from_state is CollaborationStatus.QUALIFIED
    assert event.to_state is CollaborationStatus.SHORTLISTED
    assert event.entry_type is EntryType.MISSION
    assert event.timestamp == occurred_at
    assert event.actor == "olivia.chen"
    assert event.reason == "Strong audience and content fit"
    assert event.evidence == ("profile://creator-7", "scorecard://match-9")
    assert event.to_dict()["entry_type"] == "mission"
    assert event.to_dict()["timestamp"] == "2026-08-06T09:30:00+00:00"


def test_illegal_transition_does_not_create_an_event():
    with pytest.raises(ValueError, match="illegal collaboration transition"):
        transition_event(
            entity_id="outreach-42",
            from_state="qualified",
            to_state="contracted",
            actor="olivia.chen",
            reason="Skip ahead",
            evidence="manual-review://7",
            entry_type="creator_opportunity",
            entry_id="opportunity-7",
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("entity_id", None, "entity_id is required"),
        ("actor", "", "actor is required"),
        ("actor", None, "actor is required"),
        ("reason", " ", "reason is required"),
        ("reason", None, "reason is required"),
        ("evidence", [], "evidence must contain at least one item"),
        ("evidence", [None], "evidence must contain at least one item"),
        ("evidence", None, "evidence must contain at least one item"),
        ("entry_id", None, "entry_id is required"),
    ],
)
def test_audit_fields_are_required(field, value, message):
    fields = {
        "entity_id": "outreach-42",
        "from_state": "discovered",
        "to_state": "qualified",
        "actor": "olivia.chen",
        "reason": "Verified public profile",
        "evidence": ["profile://creator-7"],
        "entry_type": "creator_opportunity",
        "entry_id": "opportunity-7",
    }
    fields[field] = value

    with pytest.raises(ValueError, match=message):
        transition_event(**fields)


def test_outreach_case_applies_transition_and_retains_history():
    case = OutreachCase(
        outreach_case_id="outreach-42",
        creator_id="creator-7",
        entry_type=EntryType.CREATOR_OPPORTUNITY,
        entry_id="opportunity-7",
        opportunity_id="opportunity-7",
        owner="olivia.chen",
    )

    event = case.transition(
        "qualified",
        actor="olivia.chen",
        reason="Public profile verified",
        evidence=["profile://creator-7"],
    )

    assert case.status is CollaborationStatus.QUALIFIED
    assert case.transitions == [event]
    assert event.entry_id == "opportunity-7"


def test_outreach_case_requires_a_root_reference():
    with pytest.raises(ValueError, match="requires a mission_id or opportunity_id"):
        OutreachCase(
            outreach_case_id="outreach-42",
            creator_id="creator-7",
            entry_type=EntryType.CREATOR_OPPORTUNITY,
            entry_id="opportunity-7",
            owner="olivia.chen",
        )


def test_timestamp_must_be_timezone_aware():
    with pytest.raises(ValueError, match="timezone-aware"):
        transition_event(
            entity_id="outreach-42",
            from_state="discovered",
            to_state="qualified",
            actor="olivia.chen",
            reason="Verified",
            evidence=["profile://creator-7"],
            entry_type="creator_opportunity",
            entry_id="opportunity-7",
            timestamp=datetime(2026, 8, 6, 9, 30),
        )
