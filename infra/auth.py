"""Authentication module — user management, password hashing, session helpers.

Uses PBKDF2-HMAC-SHA256 (built-in hashlib) for password hashing.
Default users are seeded on first run.
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from typing import Any

import streamlit as st

from infra.config import (
    DEFAULT_ADMIN_DISPLAY_NAME,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_DEMO_DISPLAY_NAME,
    DEFAULT_DEMO_PASSWORD,
    DEFAULT_DEMO_USERNAME,
    PBKDF2_HASH_ALGORITHM,
    PBKDF2_ITERATIONS,
    SALT_LENGTH,
)
from infra.database import get_connection, init_db


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        PBKDF2_HASH_ALGORITHM,
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()


def _generate_salt() -> str:
    return secrets.token_hex(SALT_LENGTH)


def create_user(username: str, display_name: str, password: str, role: str = "admin") -> None:
    salt = _generate_salt()
    password_hash = _hash_password(password, salt)
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, display_name, password_hash, salt, role) VALUES (?, ?, ?, ?, ?)",
            (username, display_name, password_hash, salt, role),
        )
        conn.commit()
    finally:
        conn.close()


def verify_user(username: str, password: str) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, display_name, password_hash, salt, role FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if not row:
            return None
        expected_hash = _hash_password(password, row["salt"])
        if not secrets.compare_digest(expected_hash, row["password_hash"]):
            return None
        return {"id": row["id"], "username": row["username"], "display_name": row["display_name"], "role": row["role"]}
    finally:
        conn.close()


def count_users() -> int:
    conn = get_connection()
    try:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()
        return row["cnt"]
    finally:
        conn.close()


def _insert_user_if_absent(username: str, display_name: str, password: str, role: str) -> None:
    """Insert one login. Duplicate usernames are a no-op, not a crash.

    Streamlit Cloud can run ``init_auth`` in overlapping sessions. A count-then-insert
    seed loses that race and raises ``sqlite3.IntegrityError`` on the UNIQUE username.
    """

    salt = _generate_salt()
    password_hash = _hash_password(password, salt)
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO users (username, display_name, password_hash, salt, role) "
            "VALUES (?, ?, ?, ?, ?)",
            (username, display_name, password_hash, salt, role),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
    finally:
        conn.close()


def seed_default_users() -> None:
    """Ensure default admin and demo logins exist. Safe to call on every boot."""

    _insert_user_if_absent(
        DEFAULT_ADMIN_USERNAME,
        DEFAULT_ADMIN_DISPLAY_NAME,
        DEFAULT_ADMIN_PASSWORD,
        "admin",
    )
    _insert_user_if_absent(
        DEFAULT_DEMO_USERNAME,
        DEFAULT_DEMO_DISPLAY_NAME,
        DEFAULT_DEMO_PASSWORD,
        "viewer",
    )


def is_authenticated() -> bool:
    """Return True if a user is logged in."""
    return bool(st.session_state.get("auth_user"))


def current_user() -> dict[str, Any]:
    return st.session_state.get("auth_user", {"display_name": "Guest", "role": "viewer", "username": "guest"})


def current_display_name() -> str:
    return current_user().get("display_name", "Guest")


def current_role() -> str:
    return current_user().get("role", "viewer")


WRITE_ROLES = frozenset({"admin"})


def can_write() -> bool:
    """Return True unless a logged-in non-admin is present.

    Pytest and other service-layer callers bootstrap state without ``auth_user``.
    Those paths stay writable. A signed-in viewer is read-only.
    """
    user = st.session_state.get("auth_user")
    if not user:
        return True
    return str(user.get("role", "viewer")) in WRITE_ROLES


def require_role(*roles: str) -> None:
    user = st.session_state.get("auth_user")
    if not user:
        return
    allowed = {str(role) for role in roles}
    if str(user.get("role", "viewer")) not in allowed:
        raise PermissionError(f"Requires role: {', '.join(sorted(allowed))}")


def require_write() -> None:
    if not can_write():
        raise PermissionError("Viewer role is read-only. An admin must approve this action.")


def login(username: str, password: str) -> bool:
    user = verify_user(username, password)
    if user:
        st.session_state.auth_user = user
        return True
    return False


def logout() -> None:
    st.session_state.pop("auth_user", None)


def init_auth() -> None:
    """Initialize auth — ensure DB and default users exist."""
    init_db()
    seed_default_users()
