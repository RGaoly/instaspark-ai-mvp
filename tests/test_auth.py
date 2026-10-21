"""Tests for the authentication module — user creation, verification, password hashing."""

from __future__ import annotations

import pytest

from infra.auth import (
    _hash_password,
    _generate_salt,
    can_write,
    create_user,
    verify_user,
    count_users,
    require_role,
    require_write,
    seed_default_users,
)
from infra.database import get_connection, init_db, reset_db


def test_password_hash_is_deterministic():
    """Same password + salt should produce the same hash."""
    salt = _generate_salt()
    h1 = _hash_password("secret123", salt)
    h2 = _hash_password("secret123", salt)
    assert h1 == h2


def test_password_hash_changes_with_salt():
    """Different salts should produce different hashes."""
    h1 = _hash_password("secret123", _generate_salt())
    h2 = _hash_password("secret123", _generate_salt())
    assert h1 != h2


def test_create_user_inserts_row():
    create_user("alice", "Alice Wang", "pass456", role="admin")
    assert count_users() == 1
    conn = get_connection()
    try:
        row = conn.execute("SELECT username, display_name, role FROM users WHERE username = ?", ("alice",)).fetchone()
        assert row["username"] == "alice"
        assert row["display_name"] == "Alice Wang"
        assert row["role"] == "admin"
    finally:
        conn.close()


def test_verify_user_correct_credentials():
    create_user("bob", "Bob Li", "bobpass", role="viewer")
    user = verify_user("bob", "bobpass")
    assert user is not None
    assert user["username"] == "bob"
    assert user["display_name"] == "Bob Li"
    assert user["role"] == "viewer"


def test_verify_user_wrong_password():
    create_user("carol", "Carol Zhao", "rightpass", role="admin")
    assert verify_user("carol", "wrongpass") is None


def test_verify_user_nonexistent_user():
    assert verify_user("nobody", "whatever") is None


def test_seed_default_users_creates_two():
    assert count_users() == 0
    seed_default_users()
    assert count_users() == 2

    admin = verify_user("admin", "admin123")
    assert admin is not None
    assert admin["role"] == "admin"

    demo = verify_user("demo", "demo123")
    assert demo is not None
    assert demo["role"] == "viewer"


def test_seed_default_users_idempotent():
    seed_default_users()
    seed_default_users()
    assert count_users() == 2


def test_seed_default_users_tolerates_concurrent_seeding(monkeypatch):
    """Two sessions booting against an empty DB must not crash each other."""
    from infra import auth

    monkeypatch.setattr(auth, "count_users", lambda: 0)
    seed_default_users()
    seed_default_users()  # second concurrent seeder hits the unique constraint
    monkeypatch.undo()
    assert count_users() == 2


def test_create_user_duplicate_username_raises():
    create_user("dup", "First", "pass1")
    with pytest.raises(Exception):
        create_user("dup", "Second", "pass2")


def test_login_page_does_not_render_an_empty_card():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "components" / "auth.py").read_text(encoding="utf-8")
    assert "auth-card" not in source
    assert "auth-hero" in source
    assert 'key="auth_username"' in source
    assert 'key="auth_submit"' in source
    assert "st.segmented_control" in source
    assert 'key="login_language_switcher"' in source
    assert source.index('st.session_state.get("login_language_switcher")') < source.index(
        "Product finds creator."
    )
    assert "Not TikTok Creator Marketplace" in source
    assert "auth-why" in source


def test_password_hash_not_stored_in_plaintext():
    create_user("secure", "Secure User", "plaintext_pw")
    conn = get_connection()
    try:
        row = conn.execute("SELECT password_hash FROM users WHERE username = ?", ("secure",)).fetchone()
        assert row["password_hash"] != "plaintext_pw"
        assert len(row["password_hash"]) == 64  # SHA-256 hex digest
    finally:
        conn.close()


class _Session(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def test_can_write_defaults_open_without_login(monkeypatch):
    from infra import auth

    fake = _Session()
    monkeypatch.setattr(auth.st, "session_state", fake)
    assert can_write() is True
    require_write()


def test_viewer_cannot_write(monkeypatch):
    from infra import auth

    fake = _Session()
    fake.auth_user = {"username": "demo", "role": "viewer", "display_name": "Demo Viewer"}
    monkeypatch.setattr(auth.st, "session_state", fake)
    assert can_write() is False
    with pytest.raises(PermissionError, match="read-only"):
        require_write()
    with pytest.raises(PermissionError, match="admin"):
        require_role("admin")


def test_admin_can_write(monkeypatch):
    from infra import auth

    fake = _Session()
    fake.auth_user = {"username": "admin", "role": "admin", "display_name": "Admin"}
    monkeypatch.setattr(auth.st, "session_state", fake)
    assert can_write() is True
    require_write()
    require_role("admin")


# ─── Persistent-login auth tokens ──────────────────────────────


def test_auth_token_roundtrip():
    from infra.auth import issue_auth_token, verify_auth_token

    token = issue_auth_token("admin")
    assert verify_auth_token(token) == "admin"


def test_auth_token_rejects_tampered_signature():
    from infra.auth import issue_auth_token, verify_auth_token

    token = issue_auth_token("admin")
    version, username_hex, expires, _sig = token.split(".")
    forged = ".".join([version, username_hex, expires, "0" * 64])
    assert verify_auth_token(forged) is None


def test_auth_token_rejects_forged_username():
    """Swapping the username without re-signing must fail."""
    from infra.auth import issue_auth_token, verify_auth_token

    token = issue_auth_token("demo")
    version, _username_hex, expires, sig = token.split(".")
    forged = ".".join([version, "admin".encode("utf-8").hex(), expires, sig])
    assert verify_auth_token(forged) is None


def test_auth_token_rejects_expired():
    from infra.auth import _sign_token_payload, verify_auth_token

    payload = f"v1.{'admin'.encode('utf-8').hex()}.1"  # expired at epoch 1
    token = f"{payload}.{_sign_token_payload(payload)}"
    assert verify_auth_token(token) is None


def test_auth_token_rejects_garbage():
    from infra.auth import verify_auth_token

    assert verify_auth_token("not-a-token") is None
    assert verify_auth_token("") is None
    assert verify_auth_token(None) is None
    assert verify_auth_token("v1.zzz.notanint.abc") is None


def test_login_logout_without_browser_runtime(monkeypatch):
    """login/logout must work with no cookie controller (pytest, scripts)."""
    from infra import auth

    create_user("nocookie", "No Cookie", "pw12345", role="viewer")
    fake = _Session()
    monkeypatch.setattr(auth.st, "session_state", fake)
    assert auth.login("nocookie", "pw12345") is True
    assert fake["auth_user"]["username"] == "nocookie"
    auth.logout()
    assert "auth_user" not in fake
    assert fake["_auth_logged_out"] is True


def test_restore_skipped_when_logged_out(monkeypatch):
    """The logout guard blocks cookie restore for the rest of the session."""
    from infra import auth

    fake = _Session()
    fake["_auth_logged_out"] = True
    monkeypatch.setattr(auth.st, "session_state", fake)
    auth.restore_session_from_cookie()
    assert "auth_user" not in fake
