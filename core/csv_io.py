"""Exportacion e importacion CSV con defensa contra inyeccion de formulas en Excel."""

from __future__ import annotations

import csv
import io

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_cell(value: object) -> str:
    """Neutraliza prefijos ejecutables en Excel/Sheets anteponiendo comilla simple."""
    text = "" if value is None else str(value).replace("\r\n", " ").replace("\n", " ").strip()
    if text and text[0] in FORMULA_PREFIXES:
        return "'" + text
    return text


def export_items_csv(items: list[dict], fields: list[str] | None = None) -> str:
    """Serializa registros a CSV UTF-8 con todas las celdas saneadas."""
    columns = fields or ["id", "module_slug", "title", "subtitle", "contact", "amount_eur", "status", "created_at"]
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(columns)
    for item in items:
        row = [sanitize_csv_cell(item.get(col, "")) for col in columns]
        writer.writerow(row)
    return buf.getvalue()


def parse_items_csv(raw_csv: str, max_rows: int = 500) -> list[dict]:
    """Lee un CSV simple y devuelve filas limpias para alta masiva validada."""
    reader = csv.DictReader(io.StringIO(raw_csv.lstrip("\ufeff")))
    rows: list[dict] = []
    for idx, row in enumerate(reader):
        if idx >= max_rows:
            break
        title = str(row.get("title") or row.get("concepto") or "").strip()
        if not title:
            continue
        rows.append(
            {
                "title": title[:200],
                "subtitle": str(row.get("subtitle") or row.get("cliente") or "").strip()[:240],
                "contact": str(row.get("contact") or row.get("telefono") or "").strip()[:120],
                "amount_eur": float(row.get("amount_eur") or 0),
                "status": str(row.get("status") or "").strip()[:60],
            }
        )
    return rows
