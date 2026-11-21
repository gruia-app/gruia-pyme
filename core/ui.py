"""Interfaz web local en espanol sin CDN externos ni JavaScript fragil."""

from __future__ import annotations

import html
import urllib.parse

from core.config import AppConfig
from core.outbox import build_whatsapp_link
from core.registry import module_metrics


def _esc(val: object) -> str:
    return html.escape("" if val is None else str(val), quote=True)


def _agenda_help_url(mod: dict) -> str:
    params = urllib.parse.urlencode(
        {
            "sector": mod.get("sector", ""),
            "caso": f"Adaptar {mod.get('title', 'app')} a mi empresa en 24h",
            "utm_source": "gruia-pyme",
            "utm_medium": "app-banner",
            "utm_campaign": mod.get("slug", "general"),
        }
    )
    return f"https://agenda.gruia.app/robertosimplificando/gruia-demo?{params}"


BASE_CSS = """
:root {
  --bg: #faf8f3;
  --panel: #f5f0e8;
  --card: #ffffff;
  --ink: #1c1917;
  --muted: #57534e;
  --line: #e5ddd0;
  --accent: #ea580c;
  --accent-dark: #c2410c;
  --ok-bg: #eefbf2;
  --ok-ink: #15803d;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
  line-height: 1.5;
}
.topbar {
  background: var(--card);
  border-top: 4px solid var(--accent);
  border-bottom: 1px solid var(--line);
  padding: 14px 20px;
}
.wrap { max-width: 1120px; margin: 0 auto; padding: 0 16px; }
.top-inner { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; justify-content: space-between; }
.brand { font-weight: 700; font-size: 1.1rem; letter-spacing: -0.01em; }
.brand span { color: var(--accent); }
.tabs { display: flex; flex-wrap: wrap; gap: 8px; }
.tab { display: inline-block; padding: 8px 14px; border: 1px solid var(--line); background: var(--panel); color: var(--ink); text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 0.92rem; }
.tab.active { background: var(--ink); color: #fff; border-color: var(--ink); }
main { padding: 24px 0 40px; }
.grid-kpi { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin: 18px 0 24px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 18px; }
.kpi-val { font-size: 1.65rem; font-weight: 700; margin-top: 4px; }
.kpi-lbl { color: var(--muted); font-size: 0.85rem; }
.layout { display: grid; grid-template-columns: 1fr 2fr; gap: 20px; align-items: start; }
@media (max-width: 860px) { .layout { grid-template-columns: 1fr; } }
label { display: block; font-size: 0.86rem; font-weight: 600; margin: 10px 0 4px; }
input, select, textarea { width: 100%; padding: 9px 11px; border: 1px solid #d6cfc2; border-radius: 7px; font: inherit; background: #fff; }
.btn { display: inline-flex; align-items: center; gap: 6px; padding: 9px 14px; border-radius: 8px; border: 1px solid var(--line); background: var(--card); color: var(--ink); font: inherit; font-weight: 600; font-size: 0.9rem; text-decoration: none; cursor: pointer; }
.btn-primary { background: var(--accent); border-color: var(--accent); color: #fff; }
.btn-primary:hover { background: var(--accent-dark); }
.btn-sm { padding: 5px 10px; font-size: 0.82rem; }
.actions-bar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
.item-row { border-top: 1px solid var(--line); padding: 14px 0; display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; }
.item-row:first-child { border-top: 0; padding-top: 0; }
.badge { display: inline-block; padding: 3px 9px; border-radius: 999px; background: var(--panel); font-size: 0.78rem; font-weight: 600; }
.flash { background: var(--ok-bg); color: var(--ok-ink); border: 1px solid #b7e4c7; padding: 10px 14px; border-radius: 8px; margin-bottom: 16px; font-weight: 500; }
.help-banner { margin-top: 26px; background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 16px 18px; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; }
"""


def render_login_page(error: str = "") -> str:
    """Renderiza pantalla de acceso cuando GRUIA_AUTH_MODE=login."""
    err_html = f'<p class="flash" style="background:#fef3f2;color:#b42318;border-color:#f5c2bd;">{_esc(error)}</p>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Entrar | gruia-pyme</title>
  <style>{BASE_CSS}</style>
</head>
<body>
  <div class="wrap" style="max-width:440px;padding-top:64px;">
    <div class="card">
      <h1 style="margin-top:0;">Acceso privado de empresa</h1>
      {err_html}
      <form method="post" action="/login">
        <label for="email">Correo</label>
        <input id="email" name="email" type="email" required autocomplete="email">
        <label for="password">Contrasena</label>
        <input id="password" name="password" type="password" required autocomplete="current-password">
        <div style="margin-top:16px;"><button class="btn btn-primary" type="submit">Entrar</button></div>
      </form>
    </div>
  </div>
</body>
</html>"""


def render_workspace_page(
    *,
    cfg: AppConfig,
    modules: dict[str, dict],
    active_mod: dict,
    items: list[dict],
    audit_entries: list[dict],
    flash: str = "",
) -> str:
    """Renderiza el espacio operativo completo del modulo activo con HTML escapado."""
    slug = active_mod["slug"]
    statuses = active_mod.get("statuses") or ["pendiente", "cerrado"]
    metrics = module_metrics(items, statuses)

    tabs_html = "".join(
        f'<a class="tab {"active" if m_slug == slug else ""}" href="/?m={_esc(m_slug)}">{_esc(m["title"])}</a>'
        for m_slug, m in modules.items()
    )

    items_html_parts: list[str] = []
    for item in items:
        phone = str(item.get("contact") or "")
        cliente = str((item.get("data") or {}).get("cliente") or item.get("subtitle") or "cliente")
        wa_text = str(active_mod.get("whatsapp_template") or "Hola {cliente}, te contactamos de {empresa} por {concepto}.").format(
            cliente=cliente,
            empresa=cfg.company_name,
            concepto=item["title"],
        )
        wa_link = build_whatsapp_link(phone, wa_text) if phone else ""
        status_options = "".join(
            f'<option value="{_esc(st)}" {"selected" if st == item["status"] else ""}>{_esc(st)}</option>'
            for st in statuses
        )
        wa_btn = (
            f'<a class="btn btn-sm" href="{_esc(wa_link)}" target="_blank" rel="noopener noreferrer">Preparar WhatsApp</a>'
            if wa_link
            else ""
        )
        items_html_parts.append(
            f"""
            <div class="item-row">
              <div style="min-width:220px;flex:1;">
                <div style="font-weight:700;">{_esc(item["title"])}</div>
                <div style="color:var(--muted);font-size:0.9rem;">{_esc(item["subtitle"])}</div>
                <div style="margin-top:6px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
                  <span class="badge">{_esc(item["status"])}</span>
                  <span style="font-size:0.85rem;color:var(--muted);">{_esc(f"{float(item.get('amount_eur') or 0):.2f} EUR")}</span>
                </div>
              </div>
              <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                {wa_btn}
                <form method="post" action="/items/status" style="display:flex;gap:6px;align-items:center;">
                  <input type="hidden" name="module" value="{_esc(slug)}">
                  <input type="hidden" name="item_id" value="{_esc(item["id"])}">
                  <select name="status" aria-label="Nuevo estado" style="width:auto;padding:5px 8px;">{status_options}</select>
                  <button class="btn btn-sm" type="submit">Cambiar</button>
                </form>
              </div>
            </div>
            """
        )

    items_block = "".join(items_html_parts) or '<p style="color:var(--muted);">Aun no hay registros. Anade el primero a la izquierda.</p>'
    flash_html = f'<div class="flash" role="status">{_esc(flash)}</div>' if flash else ""
    audit_html = "".join(
        f'<li><code>{_esc(a["created_at"])}</code> · {_esc(a["actor"])} · {_esc(a["action"])} ({_esc(a["entity_type"])} #{_esc(a["entity_id"])})</li>'
        for a in audit_entries[:8]
    ) or "<li>Sin movimientos recientes.</li>"

    banner_html = ""
    if cfg.show_help_banner:
        agenda_url = _agenda_help_url(active_mod)
        landing_url = active_mod.get("landing_url") or "https://gruia.app/"
        banner_html = f"""
        <section class="help-banner" aria-label="Soporte opcional">
          <div>
            <strong>Base abierta gruia-pyme (MIT)</strong>
            <div style="color:var(--muted);font-size:0.9rem;">Funcionando en tu ordenador. Si prefieres tenerlo conectado con tu software y listo para todo tu equipo en 24 h por 1 EUR:</div>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <a class="btn btn-sm" href="{_esc(landing_url)}" target="_blank" rel="noopener noreferrer">Ver guia del sector</a>
            <a class="btn btn-primary btn-sm" href="{_esc(agenda_url)}" target="_blank" rel="noopener noreferrer">Adaptar en 24 h por 1 EUR</a>
          </div>
        </section>
        """

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_esc(active_mod["title"])} | {_esc(cfg.company_name)}</title>
  <style>{BASE_CSS}</style>
</head>
<body>
  <header class="topbar">
    <div class="wrap top-inner">
      <div class="brand">{_esc(cfg.company_name)} · <span>gruia-pyme</span></div>
      <nav class="tabs" aria-label="Modulos">{tabs_html}</nav>
    </div>
  </header>
  <main class="wrap">
    {flash_html}
    <h1 style="margin:0 0 4px;">{_esc(active_mod["title"])} · {_esc(active_mod["sector"])}</h1>
    <p style="margin:0;color:var(--muted);">{_esc(active_mod.get("tagline") or "")}</p>
    <section class="grid-kpi" aria-label="Resumen">
      <div class="card"><div class="kpi-lbl">Registros totales</div><div class="kpi-val">{_esc(metrics["total_count"])}</div></div>
      <div class="card"><div class="kpi-lbl">Pendientes abiertos</div><div class="kpi-val">{_esc(metrics["open_count"])}</div></div>
      <div class="card"><div class="kpi-lbl">Importe abierto</div><div class="kpi-val">{_esc(f'{metrics["open_eur"]:.0f} EUR')}</div></div>
      <div class="card"><div class="kpi-lbl">Importe total</div><div class="kpi-val">{_esc(f'{metrics["total_eur"]:.0f} EUR')}</div></div>
    </section>
    <div class="layout">
      <section class="card" aria-labelledby="alta-h">
        <h2 id="alta-h" style="margin-top:0;font-size:1.05rem;">Anadir registro</h2>
        <form method="post" action="/items/create">
          <input type="hidden" name="module" value="{_esc(slug)}">
          <label for="f-title">Concepto o tarea</label>
          <input id="f-title" name="title" required placeholder="Ej. Presupuesto cocina C/ Mayor">
          <label for="f-cliente">Cliente o paciente</label>
          <input id="f-cliente" name="cliente" placeholder="Ej. Laura Gomez">
          <label for="f-contact">Telefono WhatsApp (opcional)</label>
          <input id="f-contact" name="contact" placeholder="Ej. 600112233">
          <label for="f-amount">Importe estimado (EUR)</label>
          <input id="f-amount" name="amount_eur" type="number" step="0.01" value="0">
          <label for="f-notas">Notas</label>
          <input id="f-notas" name="notas" placeholder="Detalle breve">
          <div style="margin-top:14px;"><button class="btn btn-primary" type="submit">Guardar en SQLite local</button></div>
        </form>
      </section>
      <section class="card" aria-labelledby="lista-h">
        <div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:8px;margin-bottom:10px;">
          <h2 id="lista-h" style="margin:0;font-size:1.05rem;">Seguimiento diario</h2>
          <div class="actions-bar" style="margin:0;">
            <a class="btn btn-sm" href="/api/modules/{_esc(slug)}/export.csv">Exportar CSV limpio</a>
            <form method="post" action="/backup" style="display:inline;">
              <input type="hidden" name="module" value="{_esc(slug)}">
              <button class="btn btn-sm" type="submit">Crear copia SQLite</button>
            </form>
          </div>
        </div>
        {items_block}
      </section>
    </div>
    <section class="card" style="margin-top:20px;" aria-labelledby="audit-h">
      <h2 id="audit-h" style="margin-top:0;font-size:1rem;">Registro de actividad reciente</h2>
      <ul style="margin:0;padding-left:18px;color:var(--muted);font-size:0.88rem;">{audit_html}</ul>
    </section>
    {banner_html}
  </main>
</body>
</html>"""
