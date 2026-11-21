"""Suite unitaria y de integracion HTTP para los cimientos de gruia-pyme."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
import urllib.request

from cli import main as cli_main
from core.audit import list_audit
from core.auth import authenticate_user, create_user, has_role, sign_session_token, verify_session_token
from core.config import load_config
from core.csv_io import export_items_csv, parse_items_csv, sanitize_csv_cell
from core.db import apply_migrations, connect_db, create_sqlite_backup, verify_sqlite_integrity
from core.outbox import build_whatsapp_link, list_outbox
from core.registry import create_item, load_modules, scaffold_module, seed_demo_data, update_item_status
from core.server import start_server


class GruiaPymeFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="gruia-pyme-test-"))
        self.repo_root = Path(__file__).resolve().parent.parent
        self.modules_copy = self.tmp / "modules"
        shutil.copytree(self.repo_root / "modules", self.modules_copy)
        self.cfg = load_config(
            base_dir=self.repo_root,
            env_overrides={
                "GRUIA_DB_PATH": str(self.tmp / "data" / "test.db"),
                "GRUIA_BACKUP_DIR": str(self.tmp / "backups"),
                "GRUIA_MODULES_DIR": str(self.modules_copy),
                "GRUIA_HOST": "127.0.0.1",
                "GRUIA_PORT": "0",
                "GRUIA_AUTH_MODE": "local",
                "GRUIA_COMPANY_NAME": "Reformas Prueba SL",
                "GRUIA_SESSION_SECRET": "test-secret-key-only-unit",
            },
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_db_migrations_backup_and_integrity(self) -> None:
        conn = connect_db(self.cfg.db_path)
        self.assertEqual(apply_migrations(conn), [1])
        self.assertEqual(apply_migrations(conn), [])
        modules = load_modules(self.cfg.modules_dir)
        seeded = seed_demo_data(conn, modules)
        self.assertEqual(set(modules.keys()), {"reformas", "clinica-dental", "asesoria-fiscal"})
        self.assertGreaterEqual(seeded, 6)
        conn.close()

        backup_path = create_sqlite_backup(self.cfg.db_path, self.cfg.backup_dir, label="unit")
        self.assertTrue(backup_path.is_file())
        self.assertTrue(verify_sqlite_integrity(self.cfg.db_path))
        self.assertTrue(verify_sqlite_integrity(backup_path))

    def test_auth_hashing_and_signed_tokens(self) -> None:
        conn = connect_db(self.cfg.db_path)
        apply_migrations(conn)
        uid = create_user(conn, "Admin@Empresa.es", "ClaveSegura123!", role="admin")
        self.assertGreater(uid, 0)
        self.assertIsNone(authenticate_user(conn, "admin@empresa.es", "incorrecta"))
        user = authenticate_user(conn, "admin@empresa.es", "ClaveSegura123!")
        self.assertIsNotNone(user)
        assert user is not None
        self.assertTrue(has_role(user, ["admin"]))
        self.assertFalse(has_role(user, ["equipo"]))

        token = sign_session_token(user["id"], user["email"], user["role"], self.cfg.session_secret, ttl_seconds=60)
        verified = verify_session_token(token, self.cfg.session_secret)
        self.assertIsNotNone(verified)
        self.assertEqual(verified["email"], "admin@empresa.es")
        self.assertIsNone(verify_session_token(token + "tamper", self.cfg.session_secret))
        self.assertIsNone(
            verify_session_token(
                sign_session_token(user["id"], user["email"], user["role"], self.cfg.session_secret, ttl_seconds=-5),
                self.cfg.session_secret,
            )
        )
        conn.close()

    def test_csv_formula_injection_and_import(self) -> None:
        for payload in ("=CMD()", "+SUM(A1)", "-1+1", "@SUM(1,2)"):
            self.assertEqual(sanitize_csv_cell(payload), "'" + payload)
        csv_text = export_items_csv(
            [
                {
                    "id": 1,
                    "module_slug": "reformas",
                    "title": '=HYPERLINK("http://evil")',
                    "subtitle": "Cliente A",
                    "contact": "600112233",
                    "amount_eur": 500,
                    "status": "enviado",
                    "created_at": "2026-11-21T00:00:00Z",
                }
            ]
        )
        self.assertIn("'=HYPERLINK", csv_text)
        parsed = parse_items_csv("title,subtitle,contact,amount_eur,status\nPresupuesto Bano,Ana,600112233,1200,enviado\n")
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["amount_eur"], 1200.0)

    def test_audit_outbox_and_registry_crud(self) -> None:
        conn = connect_db(self.cfg.db_path)
        apply_migrations(conn)
        modules = load_modules(self.cfg.modules_dir)
        seed_demo_data(conn, modules)
        created = create_item(
            conn,
            module=modules["reformas"],
            company_name=self.cfg.company_name,
            title="Reforma bano principal",
            subtitle="Luis Perez",
            contact="600998877",
            amount_eur=3400,
            data={"cliente": "Luis Perez"},
            actor="tester@empresa.es",
        )
        updated = update_item_status(
            conn,
            module=modules["reformas"],
            item_id=created["id"],
            new_status="aceptado",
            actor="tester@empresa.es",
        )
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["status"], "aceptado")
        self.assertGreaterEqual(len(list_audit(conn)), 2)
        outbox = list_outbox(conn)
        self.assertEqual(len(outbox), 1)
        self.assertTrue(outbox[0]["draft_url"].startswith("https://wa.me/34600998877?text="))
        self.assertEqual(build_whatsapp_link("600112233", "Hola"), "https://wa.me/34600112233?text=Hola")
        conn.close()

    def test_http_server_crud_xss_and_headers(self) -> None:
        server, app = start_server(self.cfg)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
                self.assertEqual(resp.headers.get("X-Frame-Options"), "DENY")
                self.assertTrue(json.loads(resp.read().decode("utf-8"))["ok"])

            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/modules/clinica-dental/items",
                data=json.dumps(
                    {
                        "title": "<script>alert(1)</script>Limpieza urgente",
                        "subtitle": "Paciente test",
                        "contact": "600123123",
                        "amount_eur": 95,
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 201)

            with urllib.request.urlopen(f"http://127.0.0.1:{port}/?m=clinica-dental", timeout=5) as resp:
                page = resp.read().decode("utf-8")
                self.assertNotIn("<script>alert(1)</script>", page)
                self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;Limpieza urgente", page)
                self.assertIn("https://agenda.gruia.app/robertosimplificando/gruia-demo", page)

            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/modules/clinica-dental/export.csv", timeout=5) as resp:
                self.assertIn("module_slug", resp.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            app.close()

    def test_scaffold_custom_module(self) -> None:
        manifest = scaffold_module(self.modules_copy, slug="taller-mecanico", title="ElevadorPro", sector="Taller mecanico")
        self.assertTrue(manifest.is_file())
        self.assertIn("taller-mecanico", load_modules(self.modules_copy))

    def test_cli_doctor(self) -> None:
        old = dict(os.environ)
        os.environ["GRUIA_DB_PATH"] = str(self.tmp / "data" / "cli.db")
        os.environ["GRUIA_BACKUP_DIR"] = str(self.tmp / "backups")
        os.environ["GRUIA_MODULES_DIR"] = str(self.modules_copy)
        try:
            self.assertEqual(cli_main(["doctor"]), 0)
        finally:
            os.environ.clear()
            os.environ.update(old)


if __name__ == "__main__":
    unittest.main()
