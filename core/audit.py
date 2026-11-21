"""Registro de auditoria de solo adicion para trazabilidad interna."""

from __future__ import annotations

import json
import sqlite3

from core.db import utc_now_iso


def record_audit(
    conn: sqlite3.Connection,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str | int,
    detail: dict | None = None,
) -> int:
    """Guarda un evento auditable en SQLite y devuelve su identificador."""
    with conn:
        cur = conn.execute(
            """
            INSERT INTO audit_log (actor, action, entity_type, entity_id, detail_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                actor[:120],
                action[:80],
                entity_type[:80],
                str(entity_id)[:80],
                json.dumps(detail or {}, ensure_ascii=False),
                utc_now_iso(),
            ),
        )
        return int(cur.lastrowid)


def list_audit(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    """Devuelve los ultimos eventos de auditoria ordenados del mas reciente al mas antiguo."""
    rows = conn.execute(
        "SELECT id, actor, action, entity_type, entity_id, detail_json, created_at FROM audit_log ORDER BY id DESC LIMIT ?;",
        (max(1, min(limit, 200)),),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "actor": row["actor"],
            "action": row["action"],
            "entity_type": row["entity_type"],
            "entity_id": row["entity_id"],
            "detail": json.loads(row["detail_json"] or "{}"),
            "created_at": row["created_at"],
        }
        for row in rows
    ]
