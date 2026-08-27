"""SQLite database connection and schema management for InstaSparkAI.

All user operations (decisions, approvals, notes, agent events) are persisted
here so they survive page refreshes and browser restarts.
"""

from __future__ import annotations

import sqlite3

from infra.config import DATABASE_PATH as DB_PATH, SQLITE_JOURNAL_MODE

_SCHEMA = """
-- Simple key-value store for scalar / JSON-serialisable state
CREATE TABLE IF NOT EXISTS app_state (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT DEFAULT (datetime('now'))
);

-- Users for authentication
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    display_name  TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    role          TEXT DEFAULT 'admin',
    created_at    TEXT DEFAULT (datetime('now'))
);

-- Append-only logs with structured columns
CREATE TABLE IF NOT EXISTS decisions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id  TEXT NOT NULL,
    decision    TEXT NOT NULL,
    reason      TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS approval_audit (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    approval_id TEXT NOT NULL,
    action      TEXT NOT NULL,
    reason      TEXT,
    actor       TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS knowledge_audit (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    version     TEXT NOT NULL,
    action      TEXT NOT NULL,
    reason      TEXT,
    actor       TEXT,
    impact      TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS command_audit (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action      TEXT NOT NULL,
    actor       TEXT,
    scope       TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stage       INTEGER NOT NULL,
    title       TEXT NOT NULL,
    detail      TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS creator_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id  TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    title       TEXT NOT NULL,
    detail      TEXT,
    actor       TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);
"""


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row factory enabled."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    # Validate journal mode against whitelist to prevent SQL injection
    _valid_journal_modes = {"WAL", "DELETE", "TRUNCATE", "PERSIST", "MEMORY", "OFF"}
    safe_mode = SQLITE_JOURNAL_MODE.upper() if SQLITE_JOURNAL_MODE.upper() in _valid_journal_modes else "WAL"
    conn.execute(f"PRAGMA journal_mode={safe_mode}")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db() -> None:
    """Create all tables if they don't exist."""
    conn = get_connection()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def reset_db() -> None:
    """Drop all data tables — used by 'Reset demo'."""
    _valid_tables = {
        "users", "app_state", "decisions", "approval_audit", "knowledge_audit",
        "command_audit", "agent_events", "creator_events",
    }
    conn = get_connection()
    try:
        for table in _valid_tables:
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
    finally:
        conn.close()
