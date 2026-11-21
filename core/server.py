"""Servidor HTTP local sin dependencias externas para API JSON y workspace."""

from __future__ import annotations

from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import urllib.parse

from core.audit import list_audit, record_audit
from core.auth import authenticate_user, sign_session_token, verify_session_token
from core.config import AppConfig, load_config
from core.csv_io import export_items_csv
from core.db import apply_migrations, connect_db, create_sqlite_backup, verify_sqlite_integrity
from core.outbox import list_outbox
from core.registry import create_item, list_items, load_modules, seed_demo_data, update_item_status
from core.ui import render_login_page, render_workspace_page

SESSION_COOKIE = "gruia_pyme_session"


class GruiaPymeApp:
    """Estado compartido del servidor local SQLite + modulos."""

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.modules = load_modules(cfg.modules_dir)
        self.conn = connect_db(cfg.db_path)
        apply_migrations(self.conn)
        seed_demo_data(self.conn, self.modules)

    def refresh_modules(self) -> None:
        self.modules = load_modules(self.cfg.modules_dir)

    def close(self) -> None:
        self.conn.close()


def make_handler(app: GruiaPymeApp):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            return

        def _send_security_headers(self) -> None:
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'")

        def _send_json(self, code: int, payload: object) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self._send_security_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _send_html(self, code: int, body: str) -> None:
            raw = body.encode("utf-8")
            self.send_response(code)
            self._send_security_headers()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _redirect(self, location: str, cookie_header: str | None = None) -> None:
            self.send_response(HTTPStatus.SEE_OTHER)
            self._send_security_headers()
            if cookie_header:
                self.send_header("Set-Cookie", cookie_header)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _read_body(self, max_bytes: int = 131072) -> bytes:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > max_bytes:
                return b""
            return self.rfile.read(length)

        def _session_user(self) -> dict | None:
            if app.cfg.auth_mode == "local":
                return {"uid": 0, "email": "local@empresa", "role": "admin"}
            raw_cookie = self.headers.get("Cookie")
            if not raw_cookie:
                return None
            jar = SimpleCookie()
            jar.load(raw_cookie)
            morsel = jar.get(SESSION_COOKIE)
            return verify_session_token(morsel.value if morsel else None, app.cfg.session_secret)

        def _require_auth(self, api: bool = False) -> dict | None:
            user = self._session_user()
            if user:
                return user
            if api:
                self._send_json(401, {"error": "authentication_required"})
            else:
                self._redirect("/login")
            return None

        def _parse_json_or_form(self) -> dict:
            raw = self._read_body()
            ctype = (self.headers.get("Content-Type") or "").lower()
            if "application/json" in ctype:
                return json.loads(raw.decode("utf-8") or "{}")
            parsed = urllib.parse.parse_qs(raw.decode("utf-8"), keep_blank_values=True)
            return {k: v[0] if v else "" for k, v in parsed.items()}

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            qs = urllib.parse.parse_qs(parsed.query)

            if path == "/api/health":
                ok = verify_sqlite_integrity(app.cfg.db_path)
                self._send_json(200 if ok else 500, {"ok": ok, "auth_mode": app.cfg.auth_mode, "modules": sorted(app.modules)})
                return
            if path == "/login":
                self._send_html(200, render_login_page())
                return

            user = self._require_auth(api=path.startswith("/api/"))
            if not user:
                return

            if path == "/":
                req_slug = (qs.get("m") or [""])[0].strip().lower()
                slug = req_slug if req_slug in app.modules else next(iter(app.modules))
                self._send_html(
                    200,
                    render_workspace_page(
                        cfg=app.cfg,
                        modules=app.modules,
                        active_mod=app.modules[slug],
                        items=list_items(app.conn, slug),
                        audit_entries=list_audit(app.conn, limit=12),
                        flash=(qs.get("msg") or [""])[0],
                    ),
                )
                return

            if path == "/api/modules":
                self._send_json(200, {"modules": list(app.modules.values())})
                return
            if path == "/api/audit":
                self._send_json(200, {"entries": list_audit(app.conn)})
                return
            if path == "/api/outbox":
                self._send_json(200, {"messages": list_outbox(app.conn)})
                return

            if path.startswith("/api/modules/") and path.endswith("/items"):
                parts = path.strip("/").split("/")
                if len(parts) == 4 and parts[2] in app.modules:
                    self._send_json(200, {"module": parts[2], "items": list_items(app.conn, parts[2])})
                    return

            if path.startswith("/api/modules/") and path.endswith("/export.csv"):
                parts = path.strip("/").split("/")
                if len(parts) == 4 and parts[2] in app.modules:
                    slug = parts[2]
                    raw = export_items_csv(list_items(app.conn, slug)).encode("utf-8")
                    self.send_response(200)
                    self._send_security_headers()
                    self.send_header("Content-Type", "text/csv; charset=utf-8")
                    self.send_header("Content-Disposition", f'attachment; filename="{slug}.csv"')
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return

            self._send_json(404, {"error": "not_found"})

        def do_POST(self) -> None:
            path = urllib.parse.urlparse(self.path).path
            if path == "/login":
                data = self._parse_json_or_form()
                user = authenticate_user(app.conn, str(data.get("email") or ""), str(data.get("password") or ""))
                if not user:
                    self._send_html(401, render_login_page("Correo o contrasena incorrectos."))
                    return
                token = sign_session_token(user["id"], user["email"], user["role"], app.cfg.session_secret)
                self._redirect("/", f"{SESSION_COOKIE}={token}; HttpOnly; SameSite=Lax; Path=/")
                return

            user = self._require_auth(api=path.startswith("/api/"))
            if not user:
                return
            actor = str(user.get("email") or "equipo")

            if path == "/items/create":
                data = self._parse_json_or_form()
                slug = str(data.get("module") or "").strip().lower()
                if slug not in app.modules:
                    self._redirect("/?msg=Modulo+no+valido")
                    return
                try:
                    amount = float(data.get("amount_eur") or 0)
                except ValueError:
                    amount = 0.0
                create_item(
                    app.conn,
                    module=app.modules[slug],
                    company_name=app.cfg.company_name,
                    title=str(data.get("title") or ""),
                    subtitle=f"{str(data.get('cliente') or '').strip()} · {str(data.get('notas') or '').strip()}".strip(" ·"),
                    contact=str(data.get("contact") or ""),
                    amount_eur=amount,
                    data={"cliente": str(data.get("cliente") or "").strip(), "notas": str(data.get("notas") or "").strip()},
                    actor=actor,
                )
                self._redirect(f"/?m={urllib.parse.quote(slug)}&msg=Registro+guardado+en+local")
                return

            if path == "/items/status":
                data = self._parse_json_or_form()
                slug = str(data.get("module") or "").strip().lower()
                if slug not in app.modules:
                    self._redirect("/")
                    return
                update_item_status(
                    app.conn,
                    module=app.modules[slug],
                    item_id=int(data.get("item_id") or 0),
                    new_status=str(data.get("status") or ""),
                    actor=actor,
                )
                self._redirect(f"/?m={urllib.parse.quote(slug)}&msg=Estado+actualizado")
                return

            if path == "/backup":
                data = self._parse_json_or_form()
                slug = str(data.get("module") or "").strip().lower()
                backup_path = create_sqlite_backup(app.cfg.db_path, app.cfg.backup_dir, label="ui")
                record_audit(app.conn, actor=actor, action="sqlite_backup", entity_type="db", entity_id=backup_path.name)
                target = f"/?m={urllib.parse.quote(slug)}&msg=Copia+creada" if slug in app.modules else "/?msg=Copia+creada"
                self._redirect(target)
                return

            if path == "/api/backup":
                backup_path = create_sqlite_backup(app.cfg.db_path, app.cfg.backup_dir, label="api")
                self._send_json(201, {"ok": verify_sqlite_integrity(backup_path), "backup_file": backup_path.name})
                return

            if path.startswith("/api/modules/") and path.endswith("/items"):
                parts = path.strip("/").split("/")
                if len(parts) == 4 and parts[2] in app.modules:
                    data = self._parse_json_or_form()
                    try:
                        created = create_item(
                            app.conn,
                            module=app.modules[parts[2]],
                            company_name=app.cfg.company_name,
                            title=str(data.get("title") or ""),
                            subtitle=str(data.get("subtitle") or ""),
                            contact=str(data.get("contact") or ""),
                            amount_eur=float(data.get("amount_eur") or 0),
                            status=data.get("status"),
                            data=data.get("data") if isinstance(data.get("data"), dict) else {},
                            actor=actor,
                        )
                        self._send_json(201, {"item": created})
                    except ValueError as exc:
                        self._send_json(400, {"error": str(exc)})
                    return

            if path.startswith("/api/modules/") and "/items/" in path and path.endswith("/status"):
                parts = path.strip("/").split("/")
                if len(parts) == 6 and parts[2] in app.modules:
                    try:
                        updated = update_item_status(
                            app.conn,
                            module=app.modules[parts[2]],
                            item_id=int(parts[4]),
                            new_status=str(self._parse_json_or_form().get("status") or ""),
                            actor=actor,
                        )
                        if not updated:
                            self._send_json(404, {"error": "item_not_found"})
                            return
                        self._send_json(200, {"item": updated})
                    except (ValueError, KeyError) as exc:
                        self._send_json(400, {"error": str(exc)})
                    return

            self._send_json(404, {"error": "not_found"})

    return Handler


def start_server(cfg: AppConfig | None = None) -> tuple[ThreadingHTTPServer, GruiaPymeApp]:
    """Crea e inicializa el servidor HTTP local listo para serve_forever()."""
    resolved = cfg or load_config()
    app = GruiaPymeApp(resolved)
    server = ThreadingHTTPServer((resolved.host, resolved.port), make_handler(app))
    return server, app
