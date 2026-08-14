"""Repository layer — bridges session_state and SQLite persistence.

Every mutating function in state.py calls the corresponding repository method
to persist the change. On bootstrap, repository.load_all() restores prior state.
"""

from __future__ import annotations

import json
from typing import Any

from infra.database import get_connection, init_db


def _encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _decode(raw: str) -> Any:
    return json.loads(raw)


# ── Key-value state ──────────────────────────────────────────────

def save_state(key: str, value: Any) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO app_state (key, value, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')",
            (key, _encode(value)),
        )
        conn.commit()
    finally:
        conn.close()


def load_state(key: str, default: Any = None) -> Any:
    conn = get_connection()
    try:
        row = conn.execute("SELECT value FROM app_state WHERE key = ?", (key,)).fetchone()
        return _decode(row["value"]) if row else default
    finally:
        conn.close()


def load_all_state() -> dict[str, Any]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT key, value FROM app_state").fetchall()
        return {row["key"]: _decode(row["value"]) for row in rows}
    finally:
        conn.close()


# ── Append-only: decisions ───────────────────────────────────────

def append_decision(creator_id: str, decision: str, reason: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO decisions (creator_id, decision, reason) VALUES (?, ?, ?)",
            (creator_id, decision, reason),
        )
        conn.commit()
    finally:
        conn.close()


def load_decisions() -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT creator_id, decision, reason FROM decisions ORDER BY id").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ── Append-only: approval audit ──────────────────────────────────

def append_approval_audit(approval_id: str, action: str, reason: str, actor: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO approval_audit (approval_id, action, reason, actor) VALUES (?, ?, ?, ?)",
            (approval_id, action, reason, actor),
        )
        conn.commit()
    finally:
        conn.close()


def load_approval_audit() -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT approval_id, action, reason, actor, created_at AS time FROM approval_audit ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ── Append-only: knowledge audit ─────────────────────────────────

def append_knowledge_audit(version: str, action: str, reason: str, actor: str, impact: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO knowledge_audit (version, action, reason, actor, impact) VALUES (?, ?, ?, ?, ?)",
            (version, action, reason, actor, impact),
        )
        conn.commit()
    finally:
        conn.close()


def load_knowledge_audit() -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT version, action, reason, actor, created_at AS time, impact FROM knowledge_audit ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ── Append-only: command center audit ────────────────────────────

def append_command_audit(action: str, actor: str, scope: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO command_audit (action, actor, scope) VALUES (?, ?, ?)",
            (action, actor, scope),
        )
        conn.commit()
    finally:
        conn.close()


def load_command_audit() -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT action, actor, created_at AS time, scope FROM command_audit ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ── Append-only: agent events ────────────────────────────────────

def append_agent_event(stage: int, title: str, detail: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO agent_events (stage, title, detail) VALUES (?, ?, ?)",
            (stage, title, detail),
        )
        conn.commit()
    finally:
        conn.close()


def load_agent_events() -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT stage, title, detail FROM agent_events ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ── Append-only: creator events (timeline + audit) ───────────────

def append_creator_event(creator_id: str, event_type: str, title: str, detail: str, actor: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO creator_events (creator_id, event_type, title, detail, actor) VALUES (?, ?, ?, ?, ?)",
            (creator_id, event_type, title, detail, actor),
        )
        conn.commit()
    finally:
        conn.close()


def load_creator_events() -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT creator_id, event_type AS type, title, detail, actor, created_at AS time "
            "FROM creator_events ORDER BY id DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
