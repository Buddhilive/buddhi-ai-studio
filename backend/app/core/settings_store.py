from __future__ import annotations

import sqlite3

from app.core.config import BACKEND_ROOT

SQLITE_DB_PATH = BACKEND_ROOT / "data" / "app.db"

_HF_TOKEN_KEY = "hf_token"


def _connect() -> sqlite3.Connection:
    SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    return conn


def get_hf_token() -> str | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (_HF_TOKEN_KEY,)
        ).fetchone()
    return row[0] if row else None


def set_hf_token(token: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (_HF_TOKEN_KEY, token),
        )


def clear_hf_token() -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM app_settings WHERE key = ?", (_HF_TOKEN_KEY,))
