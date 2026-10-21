"""Tests for phone registration: normalization, SMS codes, migration."""

from __future__ import annotations

import time

import pytest

from infra import auth
from infra.auth import (
    create_user,
    issue_sms_code,
    normalize_phone,
    register_with_phone,
    validate_password_strength,
    verify_sms_code,
    verify_user,
)
from infra.config import (
    REGISTERED_USER_ROLE,
    SMS_DAILY_CAP_PER_PHONE,
    SMS_MAX_VERIFY_ATTEMPTS,
)
from infra.database import get_connection, init_db

PHONE = "13812345678"


@pytest.fixture
def capture_sms(monkeypatch):
    """Replace the SMS provider with an in-memory outbox: [(phone, code)]."""
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(auth, "send_verification_code", lambda phone, code: sent.append((phone, code)))
    return sent


# ─── normalize_phone ───────────────────────────────────────────


def test_normalize_phone_accepts_common_formats():
    assert normalize_phone("13812345678") == PHONE
    assert normalize_phone("+8613812345678") == PHONE
    assert normalize_phone("86 138-1234-5678") == PHONE
    assert normalize_phone(" 138 1234 5678 ") == PHONE


def test_normalize_phone_rejects_invalid():
    assert normalize_phone("12345") is None
    assert normalize_phone("21012345678") is None
    assert normalize_phone("138abcd5678") is None
    assert normalize_phone("") is None


# ─── validate_password_strength ────────────────────────────────


def test_password_strength_rules():
    assert validate_password_strength("abc12345") is None
    assert validate_password_strength("12345678") == "Password must include both letters and numbers"
    assert validate_password_strength("abcdefgh") == "Password must include both letters and numbers"
    assert validate_password_strength("abc123") == "Password must be at least 8 characters"


# ─── issue / verify lifecycle ──────────────────────────────────


def test_issue_and_verify_roundtrip(capture_sms):
    assert issue_sms_code(PHONE) == (True, "ok")
    assert capture_sms[0][0] == PHONE
    code = capture_sms[0][1]
    assert len(code) == 6 and code.isdigit()
    assert verify_sms_code(PHONE, code) is True


def test_verify_consumes_code(capture_sms):
    issue_sms_code(PHONE)
    code = capture_sms[0][1]
    assert verify_sms_code(PHONE, code) is True
    assert verify_sms_code(PHONE, code) is False  # single use


def test_too_many_wrong_attempts_locks_the_code(capture_sms):
    issue_sms_code(PHONE)
    code = capture_sms[0][1]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(SMS_MAX_VERIFY_ATTEMPTS):
        assert verify_sms_code(PHONE, wrong) is False
    # Even the correct code is rejected once the attempt budget is spent.
    assert verify_sms_code(PHONE, code) is False


def test_resend_cooldown_blocks_second_issue(capture_sms):
    assert issue_sms_code(PHONE) == (True, "ok")
    assert issue_sms_code(PHONE) == (False, "cooldown")
    assert len(capture_sms) == 1


def test_daily_cap_blocks_issue(capture_sms):
    now = int(time.time())
    conn = get_connection()
    try:
        for _ in range(SMS_DAILY_CAP_PER_PHONE):
            conn.execute("INSERT INTO sms_send_log (phone, sent_at) VALUES (?, ?)", (PHONE, now))
        conn.commit()
    finally:
        conn.close()
    assert issue_sms_code(PHONE) == (False, "daily_cap")
    assert capture_sms == []


def test_expired_code_is_rejected(capture_sms):
    issue_sms_code(PHONE)
    code = capture_sms[0][1]
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE sms_codes SET expires_at = ? WHERE phone = ?",
            (int(time.time()) - 1, PHONE),
        )
        conn.commit()
    finally:
        conn.close()
    assert verify_sms_code(PHONE, code) is False


def test_verify_without_issue_returns_false():
    assert verify_sms_code(PHONE, "123456") is False


def test_failed_send_rolls_back_state(monkeypatch):
    def _boom(phone, code):
        raise RuntimeError("provider down")

    monkeypatch.setattr(auth, "send_verification_code", _boom)
    assert issue_sms_code(PHONE) == (False, "send_failed")
    conn = get_connection()
    try:
        assert conn.execute("SELECT COUNT(*) AS c FROM sms_codes WHERE phone = ?", (PHONE,)).fetchone()["c"] == 0
        assert conn.execute("SELECT COUNT(*) AS c FROM sms_send_log WHERE phone = ?", (PHONE,)).fetchone()["c"] == 0
    finally:
        conn.close()
    # No cooldown was armed, so a retry with a healthy provider succeeds.
    monkeypatch.setattr(auth, "send_verification_code", lambda phone, code: None)
    assert issue_sms_code(PHONE) == (True, "ok")


# ─── register_with_phone ───────────────────────────────────────


def test_register_success_creates_user_with_phone(capture_sms):
    issue_sms_code(PHONE)
    code = capture_sms[0][1]
    assert register_with_phone("+86 138-1234-5678", "passw0rd1", code) == (True, "ok")
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT username, display_name, role, phone FROM users WHERE phone = ?",
            (PHONE,),
        ).fetchone()
        assert row["username"] == PHONE
        assert row["phone"] == PHONE
        assert row["display_name"] == f"User {PHONE[-4:]}"
        assert row["role"] == REGISTERED_USER_ROLE
    finally:
        conn.close()


def test_register_rejects_invalid_phone():
    assert register_with_phone("12345", "passw0rd1", "123456") == (False, "invalid_phone")


def test_register_rejects_weak_password():
    ok, key = register_with_phone(PHONE, "123", "123456")
    assert ok is False
    assert key == "Password must be at least 8 characters"


def test_register_rejects_wrong_code(capture_sms):
    issue_sms_code(PHONE)
    assert register_with_phone(PHONE, "passw0rd1", "999999") == (False, "invalid_or_expired_code")


def test_register_rejects_duplicate_phone(capture_sms):
    issue_sms_code(PHONE)
    assert register_with_phone(PHONE, "passw0rd1", capture_sms[0][1]) == (True, "ok")
    # Successful verification consumed the first code, so a fresh issue is
    # neither on cooldown nor over the daily cap.
    issue_sms_code(PHONE)
    assert register_with_phone(PHONE, "passw0rd2", capture_sms[1][1]) == (False, "phone_taken")


# ─── login by username or phone ────────────────────────────────


def test_verify_user_accepts_username_and_phone():
    create_user("phoneuser", "Phone User", "pw123abc", role="viewer", phone="13912345678")
    by_name = verify_user("phoneuser", "pw123abc")
    by_phone = verify_user("13912345678", "pw123abc")
    by_prefixed_phone = verify_user("+86 139-1234-5678", "pw123abc")
    assert by_name is not None and by_name["username"] == "phoneuser"
    assert by_phone is not None and by_phone["username"] == "phoneuser"
    assert by_prefixed_phone is not None and by_prefixed_phone["username"] == "phoneuser"
    assert verify_user("13912345678", "wrong") is None


def test_create_user_without_phone_still_works():
    """Legacy callers never pass phone; the column stays NULL."""
    create_user("legacy", "Legacy User", "pw123abc", role="admin")
    conn = get_connection()
    try:
        row = conn.execute("SELECT phone FROM users WHERE username = ?", ("legacy",)).fetchone()
        assert row["phone"] is None
    finally:
        conn.close()


# ─── schema migration ──────────────────────────────────────────


def test_init_db_migrates_legacy_users_table():
    """A pre-phone users table gains the column without losing data."""
    conn = get_connection()
    try:
        conn.execute("DROP TABLE users")
        conn.execute(
            "CREATE TABLE users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT UNIQUE NOT NULL,"
            "  display_name TEXT NOT NULL,"
            "  password_hash TEXT NOT NULL,"
            "  salt TEXT NOT NULL,"
            "  role TEXT DEFAULT 'admin',"
            "  created_at TEXT DEFAULT (datetime('now'))"
            ")"
        )
        conn.execute(
            "INSERT INTO users (username, display_name, password_hash, salt, role) "
            "VALUES ('legacy', 'Legacy', 'h', 's', 'admin')"
        )
        conn.commit()
    finally:
        conn.close()

    init_db()

    conn = get_connection()
    try:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        assert "phone" in columns
        row = conn.execute("SELECT username, role, phone FROM users WHERE username = 'legacy'").fetchone()
        assert row["role"] == "admin"
        assert row["phone"] is None
        # The partial unique index tolerates any number of NULL phones.
        conn.execute(
            "INSERT INTO users (username, display_name, password_hash, salt, role) "
            "VALUES ('legacy2', 'Legacy Two', 'h', 's', 'viewer')"
        )
        conn.commit()
    finally:
        conn.close()


# ─── demo provider safety ──────────────────────────────────────


def test_demo_sender_is_safe_outside_streamlit_runtime():
    """Bare pytest: no runtime, no session — the demo sender must not raise."""
    from services.sms_service import send_verification_code

    send_verification_code(PHONE, "123456")


def test_demo_issue_end_to_end_without_monkeypatch():
    """The real demo provider path (log + optional session mirror) works."""
    assert issue_sms_code(PHONE) == (True, "ok")
    conn = get_connection()
    try:
        row = conn.execute("SELECT phone, attempts FROM sms_codes WHERE phone = ?", (PHONE,)).fetchone()
        assert row is not None and row["attempts"] == 0
    finally:
        conn.close()
