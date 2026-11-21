"""Configuracion local segura desde variables de entorno o fichero .env."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def parse_dotenv(path: Path) -> dict[str, str]:
    """Lee un fichero .env simple sin requerir librerias externas."""
    if not path.is_file():
        return {}
    loaded: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        loaded[key.strip()] = value.strip().strip('"').strip("'")
    return loaded


@dataclass(frozen=True)
class AppConfig:
    """Parametros de ejecucion local para una instancia gruia-pyme."""

    root_dir: Path
    db_path: Path
    backup_dir: Path
    modules_dir: Path
    host: str
    port: int
    auth_mode: str
    company_name: str
    session_secret: str
    show_help_banner: bool


def load_config(base_dir: Path | None = None, env_overrides: dict[str, str] | None = None) -> AppConfig:
    """Carga configuracion combinando .env, entorno del proceso y overrides de test."""
    root = Path(base_dir or Path(__file__).resolve().parent.parent).resolve()
    env = parse_dotenv(root / ".env")
    env.update(os.environ)
    if env_overrides:
        env.update(env_overrides)

    db_path = Path(env.get("GRUIA_DB_PATH") or (root / "data" / "gruia_pyme.db")).resolve()
    backup_dir = Path(env.get("GRUIA_BACKUP_DIR") or (root / "backups")).resolve()
    modules_dir = Path(env.get("GRUIA_MODULES_DIR") or (root / "modules")).resolve()
    auth_mode = env.get("GRUIA_AUTH_MODE", "local").strip().lower()
    if auth_mode not in ("local", "login"):
        auth_mode = "local"

    return AppConfig(
        root_dir=root,
        db_path=db_path,
        backup_dir=backup_dir,
        modules_dir=modules_dir,
        host=env.get("GRUIA_HOST", "127.0.0.1").strip() or "127.0.0.1",
        port=int(env.get("GRUIA_PORT", "8787")),
        auth_mode=auth_mode,
        company_name=env.get("GRUIA_COMPANY_NAME", "Mi Empresa").strip() or "Mi Empresa",
        session_secret=env.get("GRUIA_SESSION_SECRET", "gruia-pyme-local-secret").strip() or "gruia-pyme-local-secret",
        show_help_banner=env.get("GRUIA_SHOW_HELP_BANNER", "1").strip() != "0",
    )
