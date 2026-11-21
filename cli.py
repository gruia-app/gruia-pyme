#!/usr/bin/env python3
"""CLI oficial de gruia-pyme para inicializacion, copias, diagnostico y modulos."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from core.config import load_config
from core.csv_io import export_items_csv
from core.db import apply_migrations, connect_db, create_sqlite_backup, verify_sqlite_integrity
from core.registry import list_items, load_modules, scaffold_module, seed_demo_data
from core.server import start_server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gruia-pyme", description="Herramienta local MIT para pymes")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="Inicializa SQLite WAL, migraciones y datos ejemplo")
    sub.add_parser("serve", help="Arranca el servidor web local")
    sub.add_parser("backup", help="Crea una copia atomica de la base de datos")
    sub.add_parser("doctor", help="Comprueba Python, integridad SQLite y modulos")
    sub.add_parser("list-modules", help="Lista los modulos disponibles")

    add_mod = sub.add_parser("add-module", help="Crea la plantilla de un modulo nuevo")
    add_mod.add_argument("--slug", required=True)
    add_mod.add_argument("--title", required=True)
    add_mod.add_argument("--sector", required=True)

    exp = sub.add_parser("export-csv", help="Exporta un modulo a CSV saneado")
    exp.add_argument("--module", required=True)
    exp.add_argument("--out", required=True)

    args = parser.parse_args(argv)
    cfg = load_config()
    modules = load_modules(cfg.modules_dir)

    if args.cmd == "init":
        conn = connect_db(cfg.db_path)
        applied = apply_migrations(conn)
        seeded = seed_demo_data(conn, modules)
        conn.close()
        print(json.dumps({"ok": True, "db": str(cfg.db_path), "applied_migrations": applied, "seeded_items": seeded, "modules": sorted(modules)}))
        return 0
    if args.cmd == "backup":
        conn = connect_db(cfg.db_path)
        apply_migrations(conn)
        conn.close()
        target = create_sqlite_backup(cfg.db_path, cfg.backup_dir, label="cli")
        ok = verify_sqlite_integrity(target)
        print(json.dumps({"ok": ok, "backup": str(target)}))
        return 0 if ok else 1
    if args.cmd == "doctor":
        conn = connect_db(cfg.db_path)
        apply_migrations(conn)
        seed_demo_data(conn, modules)
        conn.close()
        db_ok = verify_sqlite_integrity(cfg.db_path)
        out = {
            "ok": db_ok and len(modules) >= 3,
            "python": sys.version.split()[0],
            "sqlite_integrity": db_ok,
            "modules_count": len(modules),
            "modules": sorted(modules),
            "host": cfg.host,
            "port": cfg.port,
            "auth_mode": cfg.auth_mode,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if out["ok"] else 1
    if args.cmd == "list-modules":
        print(json.dumps([{"slug": m["slug"], "title": m["title"], "sector": m["sector"]} for m in modules.values()], ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "add-module":
        manifest = scaffold_module(cfg.modules_dir, slug=args.slug, title=args.title, sector=args.sector)
        print(json.dumps({"ok": True, "manifest": str(manifest)}))
        return 0
    if args.cmd == "export-csv":
        if args.module not in modules:
            print(f"Modulo desconocido: {args.module}", file=sys.stderr)
            return 2
        conn = connect_db(cfg.db_path)
        items = list_items(conn, args.module)
        conn.close()
        Path(args.out).write_text(export_items_csv(items), encoding="utf-8")
        print(json.dumps({"ok": True, "rows": len(items), "out": args.out}))
        return 0
    if args.cmd == "serve":
        server, app = start_server(cfg)
        print(f"gruia-pyme activo en http://{cfg.host}:{cfg.port}/ (modo={cfg.auth_mode})")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            app.close()
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
