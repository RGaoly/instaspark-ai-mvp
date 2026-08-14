"""Tests for the authentication module — user creation, verification, password hashing."""

from __future__ import annotations

import pytest

from infra.auth import (
    _hash_password,
    _generate_salt,
    create_user,
    verify_user,
    count_users,
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


def test_password_hash_not_stored_in_plaintext():
    create_user("secure", "Secure User", "plaintext_pw")
    conn = get_connection()
    try:
        row = conn.execute("SELECT password_hash FROM users WHERE username = ?", ("secure",)).fetchone()
        assert row["password_hash"] != "plaintext_pw"
        assert len(row["password_hash"]) == 64  # SHA-256 hex digest
    finally:
        conn.close()
