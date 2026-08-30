from __future__ import annotations

import sqlite3

from app.core.config import BACKEND_ROOT, settings

SQLITE_DB_PATH = BACKEND_ROOT / "data" / "app.db"

_HF_TOKEN_KEY = "hf_token"
_LITERT_BACKEND_KEY = "litert_backend"
_CHAT_MAX_NUM_TOKENS_KEY = "chat_max_num_tokens"


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


def get_inference_settings() -> dict[str, str | int]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT key, value FROM app_settings WHERE key IN (?, ?)",
            (_LITERT_BACKEND_KEY, _CHAT_MAX_NUM_TOKENS_KEY),
        ).fetchall()
    saved = dict(rows)
    backend_val = saved.get(_LITERT_BACKEND_KEY) or settings.litert_backend
    tokens_val = saved.get(_CHAT_MAX_NUM_TOKENS_KEY)
    try:
        max_num_token = int(tokens_val) if tokens_val is not None else settings.chat_max_num_tokens
    except (ValueError, TypeError):
        max_num_token = settings.chat_max_num_tokens
    return {
        "litert_backend": backend_val,
        "max_num_token": max_num_token,
    }


def set_inference_settings(litert_backend: str, max_num_token: int) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (_LITERT_BACKEND_KEY, litert_backend),
        )
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (_CHAT_MAX_NUM_TOKENS_KEY, str(max_num_token)),
        )
