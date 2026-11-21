"""Conexion SQLite WAL, migraciones versionadas y copias atomicas."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Callable


MIGRATIONS: list[tuple[int, str, str]] = [
    (
        1,
        "initial_foundation",
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL DEFAULT 'equipo',
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS module_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_slug TEXT NOT NULL,
            title TEXT NOT NULL,
            subtitle TEXT NOT NULL DEFAULT '',
            contact TEXT NOT NULL DEFAULT '',
            amount_eur REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_module_items_slug_status ON module_items (module_slug, status);

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            detail_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS outbox_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_slug TEXT NOT NULL,
            item_id INTEGER,
            channel TEXT NOT NULL,
            recipient TEXT NOT NULL,
            body_text TEXT NOT NULL,
            draft_url TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'borrador',
            created_at TEXT NOT NULL
        );
        """,
    ),
]


def utc_now_iso() -> str:
    """Devuelve la fecha UTC actual en formato ISO 8601 compacto."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect_db(db_path: Path) -> sqlite3.Connection:
    """Abre SQLite en modo WAL con claves foraneas activas."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def apply_migrations(conn: sqlite3.Connection) -> list[int]:
    """Ejecuta migraciones pendientes de forma idempotente y devuelve las aplicadas."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        );
        """
    )
    existing = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations;").fetchall()}
    applied: list[int] = []
    for version, name, sql in MIGRATIONS:
        if version in existing:
            continue
        with conn:
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?);",
                (version, name, utc_now_iso()),
            )
        applied.append(version)
    return applied


def create_sqlite_backup(db_path: Path, backup_dir: Path, label: str = "manual") -> Path:
    """Genera una copia coherente en caliente usando la API nativa SQLite backup()."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_label = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in label).strip("_") or "backup"
    target = backup_dir / f"gruia-pyme-{stamp}-{safe_label}.db"
    src = connect_db(db_path)
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return target


def verify_sqlite_integrity(db_path: Path) -> bool:
    """Ejecuta PRAGMA integrity_check sobre una base SQLite."""
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("PRAGMA integrity_check;").fetchone()
        return bool(row and row[0] == "ok")
    finally:
        conn.close()
