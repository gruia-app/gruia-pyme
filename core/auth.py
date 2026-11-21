"""Autenticacion local sin dependencias: hashing PBKDF2-SHA256 y cookies HMAC."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from typing import Iterable

from core.db import utc_now_iso

PBKDF2_ITERATIONS = 200_000


def hash_password(password: str, salt: bytes | None = None) -> str:
    """Deriva un hash PBKDF2-HMAC-SHA256 con sal aleatoria por usuario."""
    if not password or len(password) < 8:
        raise ValueError("La contrasena debe tener al menos 8 caracteres.")
    raw_salt = salt if salt is not None else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), raw_salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${raw_salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    """Comprueba en tiempo constante una contrasena contra su hash guardado."""
    try:
        scheme, iters_s, salt_hex, digest_hex = encoded_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iters_s),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def create_user(conn: sqlite3.Connection, email: str, password: str, role: str = "admin") -> int:
    """Crea un usuario con rol valido (admin o equipo)."""
    clean_email = email.strip().lower()
    if "@" not in clean_email:
        raise ValueError("Correo no valido.")
    if role not in ("admin", "equipo"):
        raise ValueError("Rol no valido.")
    pw_hash = hash_password(password)
    with conn:
        cur = conn.execute(
            "INSERT INTO users (email, role, password_hash, created_at) VALUES (?, ?, ?, ?);",
            (clean_email, role, pw_hash, utc_now_iso()),
        )
        return int(cur.lastrowid)


def authenticate_user(conn: sqlite3.Connection, email: str, password: str) -> dict | None:
    """Autentica correo y contrasena devolviendo la ficha publica o None."""
    row = conn.execute(
        "SELECT id, email, role, password_hash FROM users WHERE email = ?;",
        (email.strip().lower(),),
    ).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        return None
    return {"id": row["id"], "email": row["email"], "role": row["role"]}


def sign_session_token(user_id: int, email: str, role: str, secret: str, ttl_seconds: int = 43200) -> str:
    """Firma un token de sesion compacto con HMAC-SHA256 y caducidad."""
    payload = {"uid": user_id, "email": email, "role": role, "exp": int(time.time()) + ttl_seconds}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    b64 = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hmac.new(secret.encode("utf-8"), b64.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"


def verify_session_token(token: str | None, secret: str) -> dict | None:
    """Valida firma y caducidad de un token de sesion."""
    if not token or "." not in token:
        return None
    try:
        b64, sig = token.split(".", 1)
        expected = hmac.new(secret.encode("utf-8"), b64.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        padded = b64 + "=" * (-len(b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def has_role(session_user: dict | None, allowed_roles: Iterable[str]) -> bool:
    """Comprueba si el usuario autenticado posee uno de los roles permitidos."""
    return bool(session_user and session_user.get("role") in set(allowed_roles))
