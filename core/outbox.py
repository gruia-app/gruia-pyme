"""Bandeja segura de avisos: genera enlaces wa.me y mailto sin enviar por su cuenta."""

from __future__ import annotations

import re
import sqlite3
import urllib.parse

from core.db import utc_now_iso


def _digits_only(phone: str) -> str:
    digits = re.sub(r"\D+", "", phone or "")
    if len(digits) == 9 and digits.startswith(("6", "7", "9")):
        return "34" + digits
    return digits


def build_whatsapp_link(phone: str, message: str) -> str:
    """Construye un enlace https://wa.me/... listo para revisar antes de enviar."""
    digits = _digits_only(phone)
    encoded = urllib.parse.quote(message.strip())
    if digits:
        return f"https://wa.me/{digits}?text={encoded}"
    return f"https://wa.me/?text={encoded}"


def build_mailto_link(email: str, subject: str, body: str) -> str:
    """Construye un borrador mailto: para abrir en el cliente de correo del equipo."""
    qs = urllib.parse.urlencode({"subject": subject.strip(), "body": body.strip()})
    return f"mailto:{urllib.parse.quote(email.strip())}?{qs}"


def enqueue_draft(
    conn: sqlite3.Connection,
    *,
    module_slug: str,
    item_id: int | None,
    channel: str,
    recipient: str,
    body_text: str,
    draft_url: str,
) -> int:
    """Guarda un borrador de aviso para revision humana antes de enviarlo."""
    with conn:
        cur = conn.execute(
            """
            INSERT INTO outbox_messages (module_slug, item_id, channel, recipient, body_text, draft_url, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'borrador', ?);
            """,
            (module_slug, item_id, channel, recipient[:120], body_text[:1000], draft_url[:1500], utc_now_iso()),
        )
        return int(cur.lastrowid)


def list_outbox(conn: sqlite3.Connection, limit: int = 30) -> list[dict]:
    """Lista los borradores recientes preparados por la aplicacion."""
    rows = conn.execute(
        "SELECT id, module_slug, item_id, channel, recipient, body_text, draft_url, status, created_at FROM outbox_messages ORDER BY id DESC LIMIT ?;",
        (max(1, min(limit, 100)),),
    ).fetchall()
    return [dict(row) for row in rows]
