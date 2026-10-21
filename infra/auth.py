"""Authentication module — user management, password hashing, session helpers.

Uses PBKDF2-HMAC-SHA256 (built-in hashlib) for password hashing.
Default users are seeded on first run.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Any

import streamlit as st

from infra.config import (
    AUTH_COOKIE_MAX_RETRIES,
    AUTH_COOKIE_NAME,
    AUTH_TOKEN_SECRET,
    AUTH_TOKEN_TTL_SECONDS,
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


def get_user_by_username(username: str) -> dict[str, Any] | None:
    """Fetch a user row without checking the password (used by cookie restore)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, display_name, role FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if not row:
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


def seed_default_users() -> None:
    """Create default admin and demo users if the users table is empty."""
    if count_users() > 0:
        return
    create_user(DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_DISPLAY_NAME, DEFAULT_ADMIN_PASSWORD, role="admin")
    create_user(DEFAULT_DEMO_USERNAME, DEFAULT_DEMO_DISPLAY_NAME, DEFAULT_DEMO_PASSWORD, role="viewer")


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


# ─── Persistent login (signed auth cookie) ─────────────────────
# st.session_state dies with the websocket session, so a full page refresh
# would always land back on the login page. After a successful login we also
# drop a signed cookie; on the next cold start restore_session_from_cookie()
# verifies it and repopulates auth_user without asking for the password again.
# The cookie holds only `v1.<hex(username)>.<expires>.<hmac>` — never a
# password. Set AUTH_TOKEN_SECRET via Streamlit Cloud Secrets / env / .env;
# without it an ephemeral per-process secret is used and every app restart
# invalidates outstanding cookies.

_TOKEN_VERSION = "v1"
_ephemeral_token_secret: str | None = None


def _token_secret() -> str:
    if AUTH_TOKEN_SECRET:
        return AUTH_TOKEN_SECRET
    global _ephemeral_token_secret
    if _ephemeral_token_secret is None:
        _ephemeral_token_secret = secrets.token_hex(32)
    return _ephemeral_token_secret


def _sign_token_payload(payload: str) -> str:
    return hmac.new(
        _token_secret().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def issue_auth_token(username: str) -> str:
    """Mint a signed, expiring token carrying only the username."""
    expires = int(time.time()) + AUTH_TOKEN_TTL_SECONDS
    payload = f"{_TOKEN_VERSION}.{username.encode('utf-8').hex()}.{expires}"
    return f"{payload}.{_sign_token_payload(payload)}"


def verify_auth_token(token: object) -> str | None:
    """Return the username for a valid, unexpired token, else None."""
    parts = str(token or "").split(".")
    if len(parts) != 4:
        return None
    version, username_hex, expires_text, signature = parts
    if version != _TOKEN_VERSION:
        return None
    payload = f"{version}.{username_hex}.{expires_text}"
    if not hmac.compare_digest(signature, _sign_token_payload(payload)):
        return None
    try:
        expires = int(expires_text)
        username = bytes.fromhex(username_hex).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    if expires < int(time.time()):
        return None
    return username


def _cookie_controller() -> Any:
    """The per-run CookieController created by init_auth_cookies(), if any."""
    return st.session_state.get("_auth_cookie_controller")


def init_auth_cookies() -> None:
    """Instantiate the cookie controller once per run, then restore the login.

    CookieController renders a hidden component that syncs document.cookie
    into the backend; a second instance with the same key in one run raises a
    duplicate-widget error, so app.py is the single call site. Outside a
    running Streamlit runtime (pytest, scripts) there is no browser and every
    cookie helper degrades to a no-op.
    """
    controller = None
    try:
        from streamlit import runtime

        if runtime.exists():
            from streamlit_cookies_controller import CookieController

            controller = CookieController(key="instaspark_auth_cookie")
    except Exception:
        controller = None
    st.session_state["_auth_cookie_controller"] = controller
    restore_session_from_cookie()


def _persist_auth_cookie(username: str) -> None:
    controller = _cookie_controller()
    if controller is None:
        return
    try:
        # max_age is in seconds; the library default is only 1 day, so the
        # configured TTL must be passed explicitly.
        controller.set(
            AUTH_COOKIE_NAME,
            issue_auth_token(username),
            max_age=float(AUTH_TOKEN_TTL_SECONDS),
        )
    except Exception:
        # A cookie failure must never break logging in.
        pass


def _clear_auth_cookie() -> None:
    controller = _cookie_controller()
    if controller is None:
        return
    try:
        controller.remove(AUTH_COOKIE_NAME)
        # The removal is applied client-side; give the component a beat
        # before the caller's st.rerun(), otherwise the stale cookie
        # survives and would silently log the user back in.
        time.sleep(1)
    except Exception:
        pass


def restore_session_from_cookie() -> None:
    """Repopulate auth_user from the signed cookie after a cold start."""
    if is_authenticated() or st.session_state.get("_auth_logged_out"):
        return
    controller = _cookie_controller()
    if controller is None:
        return
    try:
        token = controller.get(AUTH_COOKIE_NAME)
    except Exception:
        return
    if token is None:
        # First runs of a session: the component may not have synced the
        # browser cookies yet. Retry a bounded number of times, then treat
        # the visitor as logged out.
        retries = int(st.session_state.get("_auth_cookie_retries", 0))
        if retries < AUTH_COOKIE_MAX_RETRIES:
            st.session_state["_auth_cookie_retries"] = retries + 1
            time.sleep(0.4)
            st.rerun()
        return
    username = verify_auth_token(token)
    if username is None:
        # Forged or expired cookie — remove it so we stop re-checking it.
        try:
            controller.remove(AUTH_COOKIE_NAME)
        except Exception:
            pass
        return
    user = get_user_by_username(username)
    if user is not None:
        st.session_state.auth_user = user


def login(username: str, password: str) -> bool:
    user = verify_user(username, password)
    if user:
        st.session_state.auth_user = user
        st.session_state["_auth_logged_out"] = False
        _persist_auth_cookie(user["username"])
        return True
    return False


def logout() -> None:
    st.session_state.pop("auth_user", None)
    # Guards the rest of this session even if the cookie removal has not
    # reached the browser yet.
    st.session_state["_auth_logged_out"] = True
    _clear_auth_cookie()


def init_auth() -> None:
    """Initialize auth — ensure DB and default users exist."""
    init_db()
    seed_default_users()
