"""Tests for the SQLite persistence layer."""

from __future__ import annotations

from infra import repository
from infra.database import init_db, reset_db


def test_key_value_state_roundtrip():
    """Save and load a key-value state pair."""
    repository.save_state("content_status", "Approved")
    loaded = repository.load_state("content_status")
    assert loaded == "Approved"


def test_key_value_state_overwrite():
    """Overwriting a key updates the value."""
    repository.save_state("agent_stage", 1)
    repository.save_state("agent_stage", 3)
    assert repository.load_state("agent_stage") == 3


def test_key_value_state_default():
    """Loading a non-existent key returns the default."""
    assert repository.load_state("nonexistent", "default") == "default"


def test_complex_state_persists():
    """JSON-serialisable dicts and lists persist correctly."""
    complex_value = {"C001": "Shortlisted", "C003": "Review ready", "C006": "Approved"}
    repository.save_state("outreach_stage", complex_value)
    assert repository.load_state("outreach_stage") == complex_value


def test_load_all_state():
    """load_all_state returns all persisted keys."""
    repository.save_state("key_a", "value_a")
    repository.save_state("key_b", [1, 2, 3])
    all_state = repository.load_all_state()
    assert all_state["key_a"] == "value_a"
    assert all_state["key_b"] == [1, 2, 3]


def test_decision_log_append_and_load():
    """Decisions are appended and loaded in order."""
    repository.append_decision("C001", "Approved", "Great fit")
    repository.append_decision("C003", "Rejected", "Budget mismatch")
    decisions = repository.load_decisions()
    assert len(decisions) == 2
    assert decisions[0]["creator_id"] == "C001"
    assert decisions[1]["creator_id"] == "C003"


def test_approval_audit_append_and_load():
    """Approval audit entries are appended with timestamps."""
    repository.append_approval_audit("APR-001", "Approved", "Reply verified", "Olivia Chen")
    audit = repository.load_approval_audit()
    assert len(audit) == 1
    assert audit[0]["approval_id"] == "APR-001"
    assert "time" in audit[0]


def test_knowledge_audit_append_and_load():
    """Knowledge audit entries persist all fields."""
    repository.append_knowledge_audit("knowledge-v1.4", "Published", "Facts verified", "PM", "14 assets")
    audit = repository.load_knowledge_audit()
    assert len(audit) == 1
    assert audit[0]["version"] == "knowledge-v1.4"
    assert audit[0]["impact"] == "14 assets"


def test_agent_events_append_and_load():
    """Agent events are appended in order."""
    repository.append_agent_event(1, "Mission grounded", "Facts loaded")
    repository.append_agent_event(3, "Creator approved", "C001 approved")
    events = repository.load_agent_events()
    assert len(events) == 2
    assert events[0]["stage"] == 1
    assert events[1]["stage"] == 3


def test_creator_events_append_and_load():
    """Creator events are loaded in reverse order (newest first)."""
    repository.append_creator_event("C001", "Note", "Note added", "Test note", "Olivia")
    repository.append_creator_event("C001", "Draft", "Follow-up prepared", "Detail", "Olivia")
    events = repository.load_creator_events()
    assert len(events) == 2
    # Newest first
    assert events[0]["type"] == "Draft"
    assert events[1]["type"] == "Note"


def test_command_audit_append_and_load():
    """Command center audit entries persist."""
    repository.append_command_audit("Brief generated", "Olivia Chen", "Full scope")
    audit = repository.load_command_audit()
    assert len(audit) == 1
    assert audit[0]["action"] == "Brief generated"


def test_reset_db_clears_all():
    """reset_db removes all data from all tables."""
    repository.save_state("key", "value")
    repository.append_decision("C001", "Approved", "reason")
    repository.append_agent_event(1, "Test", "detail")
    reset_db()
    assert repository.load_all_state() == {}
    assert repository.load_decisions() == []
    assert repository.load_agent_events() == []


def test_init_db_creates_tables():
    """init_db creates all required tables without error."""
    init_db()
    # If we can save and load, the tables exist
    repository.save_state("test_key", "test_value")
    assert repository.load_state("test_key") == "test_value"
