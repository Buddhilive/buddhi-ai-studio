from __future__ import annotations

import sqlite3

from app.core.settings_store import SQLITE_DB_PATH


def _connect() -> sqlite3.Connection:
    SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS model_metadata "
        "(model_id TEXT PRIMARY KEY, created_at INTEGER NOT NULL)"
    )
    return conn


def record_created(model_id: str, created_at: int) -> None:
    """Records the first-seen download timestamp for a model. Idempotent —
    a model_id already present keeps its original created_at."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO model_metadata (model_id, created_at) VALUES (?, ?) "
            "ON CONFLICT(model_id) DO NOTHING",
            (model_id, created_at),
        )


def get_created(model_id: str) -> int | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT created_at FROM model_metadata WHERE model_id = ?", (model_id,)
        ).fetchone()
    return row[0] if row else None


def delete_created(model_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM model_metadata WHERE model_id = ?", (model_id,))
