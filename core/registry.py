"""Registro de modulos sectoriales y operaciones CRUD sobre SQLite."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sqlite3

from core.audit import record_audit
from core.db import utc_now_iso
from core.outbox import build_whatsapp_link, enqueue_draft

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}$")


def load_modules(modules_dir: Path) -> dict[str, dict]:
    """Carga todos los manifiestos modules/*/manifest.json ordenados por slug."""
    found: dict[str, dict] = {}
    if not modules_dir.is_dir():
        return found
    for manifest in sorted(modules_dir.glob("*/manifest.json")):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        slug = str(data.get("slug") or manifest.parent.name).strip().lower()
        if not SLUG_RE.fullmatch(slug):
            continue
        data["slug"] = slug
        found[slug] = data
    return found


def seed_demo_data(conn: sqlite3.Connection, modules: dict[str, dict]) -> int:
    """Inserta registros de ejemplo en los modulos que aun no tienen filas."""
    inserted = 0
    now = utc_now_iso()
    for slug, mod in modules.items():
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM module_items WHERE module_slug = ?;",
            (slug,),
        ).fetchone()["n"]
        if count > 0:
            continue
        statuses = mod.get("statuses") or ["pendiente", "cerrado"]
        default_status = statuses[0]
        with conn:
            for item in mod.get("demo_items") or []:
                status = str(item.get("status") or default_status)
                if status not in statuses:
                    status = default_status
                conn.execute(
                    """
                    INSERT INTO module_items
                        (module_slug, title, subtitle, contact, amount_eur, status, payload_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        slug,
                        str(item.get("title") or "Registro ejemplo")[:200],
                        str(item.get("subtitle") or "")[:240],
                        str(item.get("contact") or "")[:120],
                        float(item.get("amount_eur") or 0),
                        status,
                        json.dumps(item.get("data") or {}, ensure_ascii=False),
                        now,
                        now,
                    ),
                )
                inserted += 1
    return inserted


def list_items(conn: sqlite3.Connection, module_slug: str) -> list[dict]:
    """Lista los registros de un modulo del mas reciente al mas antiguo."""
    rows = conn.execute(
        """
        SELECT id, module_slug, title, subtitle, contact, amount_eur, status, payload_json, created_at, updated_at
        FROM module_items
        WHERE module_slug = ?
        ORDER BY id DESC;
        """,
        (module_slug,),
    ).fetchall()
    result: list[dict] = []
    for row in rows:
        item = dict(row)
        item["data"] = json.loads(item.pop("payload_json") or "{}")
        result.append(item)
    return result


def get_item(conn: sqlite3.Connection, module_slug: str, item_id: int) -> dict | None:
    """Obtiene un registro por modulo e ID."""
    row = conn.execute(
        """
        SELECT id, module_slug, title, subtitle, contact, amount_eur, status, payload_json, created_at, updated_at
        FROM module_items
        WHERE module_slug = ? AND id = ?;
        """,
        (module_slug, item_id),
    ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["data"] = json.loads(item.pop("payload_json") or "{}")
    return item


def create_item(
    conn: sqlite3.Connection,
    *,
    module: dict,
    company_name: str,
    title: str,
    subtitle: str = "",
    contact: str = "",
    amount_eur: float = 0.0,
    status: str | None = None,
    data: dict | None = None,
    actor: str = "equipo",
) -> dict:
    """Crea un registro validado, anota auditoria y prepara borrador WhatsApp si hay telefono."""
    clean_title = title.strip()[:200]
    if not clean_title:
        raise ValueError("El titulo o concepto es obligatorio.")
    statuses = module.get("statuses") or ["pendiente", "cerrado"]
    chosen_status = status if status in statuses else statuses[0]
    slug = module["slug"]
    now = utc_now_iso()
    payload = data or {}

    with conn:
        cur = conn.execute(
            """
            INSERT INTO module_items
                (module_slug, title, subtitle, contact, amount_eur, status, payload_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                slug,
                clean_title,
                subtitle.strip()[:240],
                contact.strip()[:120],
                float(amount_eur or 0),
                chosen_status,
                json.dumps(payload, ensure_ascii=False),
                now,
                now,
            ),
        )
        item_id = int(cur.lastrowid)

    record_audit(
        conn,
        actor=actor,
        action="item_created",
        entity_type=slug,
        entity_id=item_id,
        detail={"title": clean_title, "status": chosen_status},
    )

    if contact.strip() and module.get("whatsapp_template"):
        cliente = str(payload.get("cliente") or subtitle.strip() or "equipo")
        msg = str(module["whatsapp_template"]).format(
            cliente=cliente,
            empresa=company_name,
            concepto=clean_title,
        )
        enqueue_draft(
            conn,
            module_slug=slug,
            item_id=item_id,
            channel="whatsapp",
            recipient=contact.strip(),
            body_text=msg,
            draft_url=build_whatsapp_link(contact.strip(), msg),
        )

    return get_item(conn, slug, item_id)


def update_item_status(
    conn: sqlite3.Connection,
    *,
    module: dict,
    item_id: int,
    new_status: str,
    actor: str = "equipo",
) -> dict | None:
    """Actualiza el estado de un registro si pertenece a los estados del modulo."""
    statuses = module.get("statuses") or []
    if new_status not in statuses:
        raise ValueError(f"Estado no valido: {new_status}")
    slug = module["slug"]
    existing = get_item(conn, slug, item_id)
    if not existing:
        return None
    with conn:
        conn.execute(
            "UPDATE module_items SET status = ?, updated_at = ? WHERE module_slug = ? AND id = ?;",
            (new_status, utc_now_iso(), slug, item_id),
        )
    record_audit(
        conn,
        actor=actor,
        action="status_changed",
        entity_type=slug,
        entity_id=item_id,
        detail={"from": existing["status"], "to": new_status},
    )
    return get_item(conn, slug, item_id)


def module_metrics(items: list[dict], statuses: list[str]) -> dict:
    """Calcula conteo total, abiertos y suma economica en EUR."""
    terminal = {statuses[-1]} if statuses else {"cerrado"}
    open_items = [it for it in items if it["status"] not in terminal]
    total_eur = round(sum(float(it.get("amount_eur") or 0) for it in items), 2)
    open_eur = round(sum(float(it.get("amount_eur") or 0) for it in open_items), 2)
    return {
        "total_count": len(items),
        "open_count": len(open_items),
        "total_eur": total_eur,
        "open_eur": open_eur,
    }


def scaffold_module(modules_dir: Path, *, slug: str, title: str, sector: str, landing_url: str = "https://gruia.app/") -> Path:
    """Crea un modulo nuevo listo para personalizar con Claude o Grok."""
    clean_slug = slug.strip().lower()
    if not SLUG_RE.fullmatch(clean_slug):
        raise ValueError("El slug debe usar minusculas, numeros y guiones.")
    target_dir = modules_dir / clean_slug
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = target_dir / "manifest.json"
    if manifest_path.exists():
        return manifest_path
    manifest = {
        "slug": clean_slug,
        "title": title.strip()[:80],
        "sector": sector.strip()[:100],
        "landing_url": landing_url.strip(),
        "tagline": f"Control diario para {sector.strip()[:80]}.",
        "statuses": ["pendiente", "en_curso", "cerrado"],
        "fields": [
            {"key": "cliente", "label": "Cliente", "required": True},
            {"key": "telefono", "label": "Telefono WhatsApp", "required": False},
            {"key": "concepto", "label": "Tarea o concepto", "required": True},
            {"key": "importe_eur", "label": "Importe (EUR)", "required": False},
            {"key": "notas", "label": "Notas", "required": False},
        ],
        "whatsapp_template": "Hola {cliente}, te escribimos de {empresa} por {concepto}.",
        "demo_items": [
            {
                "title": f"Primer registro de ejemplo ({title.strip()})",
                "subtitle": "Cliente ejemplo · Listo para adaptar con tu equipo",
                "contact": "34600000000",
                "amount_eur": 350,
                "status": "pendiente",
                "data": {"cliente": "Cliente ejemplo", "concepto": "Caso inicial"},
            }
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (target_dir / "README.md").write_text(
        f"# Modulo {title.strip()} — {sector.strip()}\n\nModulo generado con `python3 cli.py add-module`.\n",
        encoding="utf-8",
    )
    return manifest_path
