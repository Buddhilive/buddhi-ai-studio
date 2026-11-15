from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from app.core.config import settings

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BuildProjectStorage:
    """Thread-safe DuckDB persistence for Build projects and chat/trajectory history."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        raw_path = str(db_path if db_path is not None else settings.build_projects_db_path)
        self.db_path = raw_path
        self._is_in_memory = raw_path == ":memory:"
        self._lock = threading.RLock()
        self._in_memory_conn: duckdb.DuckDBPyConnection | None = None
        self._init_db()

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        if self._is_in_memory:
            if self._in_memory_conn is None:
                self._in_memory_conn = duckdb.connect(":memory:")
            return self._in_memory_conn
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(self.db_path)

    def _close_connection(self, conn: duckdb.DuckDBPyConnection) -> None:
        if not self._is_in_memory:
            conn.close()

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS build_projects (
                        id VARCHAR PRIMARY KEY,
                        name VARCHAR NOT NULL,
                        description VARCHAR NOT NULL DEFAULT '',
                        template VARCHAR NOT NULL DEFAULT 'nextjs-vibe',
                        db_dialect VARCHAR NOT NULL DEFAULT 'postgresql',
                        active_session_id VARCHAR,
                        runtime_image VARCHAR NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_build_projects_updated ON build_projects (updated_at DESC)"
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS build_project_messages (
                        project_id VARCHAR PRIMARY KEY,
                        messages_json VARCHAR NOT NULL DEFAULT '[]',
                        trajectory_json VARCHAR NOT NULL DEFAULT '[]',
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            finally:
                self._close_connection(conn)

    def create_project(
        self,
        *,
        project_id: str,
        name: str,
        description: str,
        template: str,
        db_dialect: str,
        runtime_image: str,
        active_session_id: str | None = None,
    ) -> dict[str, Any]:
        now = _utc_now()
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO build_projects (
                        id, name, description, template, db_dialect,
                        active_session_id, runtime_image, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        project_id,
                        name,
                        description,
                        template,
                        db_dialect,
                        active_session_id,
                        runtime_image,
                        now,
                        now,
                    ],
                )
                conn.execute(
                    """
                    INSERT INTO build_project_messages (project_id, messages_json, trajectory_json, updated_at)
                    VALUES (?, '[]', '[]', ?)
                    ON CONFLICT (project_id) DO NOTHING
                    """,
                    [project_id, now],
                )
            finally:
                self._close_connection(conn)
        return self.get_project(project_id)  # type: ignore[return-value]

    def list_projects(self) -> list[dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            try:
                rows = conn.execute(
                    """
                    SELECT id, name, description, template, db_dialect,
                           active_session_id, runtime_image, created_at, updated_at
                    FROM build_projects
                    ORDER BY updated_at DESC
                    """
                ).fetchall()
            finally:
                self._close_connection(conn)
        return [self._row_to_project(r) for r in rows]

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self._lock:
            conn = self._get_connection()
            try:
                row = conn.execute(
                    """
                    SELECT id, name, description, template, db_dialect,
                           active_session_id, runtime_image, created_at, updated_at
                    FROM build_projects
                    WHERE id = ?
                    """,
                    [project_id],
                ).fetchone()
            finally:
                self._close_connection(conn)
        return self._row_to_project(row) if row else None

    def update_session(self, project_id: str, session_id: str | None) -> None:
        now = _utc_now()
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    UPDATE build_projects
                    SET active_session_id = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    [session_id, now, project_id],
                )
            finally:
                self._close_connection(conn)

    def touch_project(self, project_id: str) -> None:
        now = _utc_now()
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    "UPDATE build_projects SET updated_at = ? WHERE id = ?",
                    [now, project_id],
                )
            finally:
                self._close_connection(conn)

    def delete_project(self, project_id: str) -> bool:
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN TRANSACTION")
                try:
                    existing = conn.execute(
                        "SELECT id FROM build_projects WHERE id = ?", [project_id]
                    ).fetchone()
                    if not existing:
                        conn.execute("ROLLBACK")
                        return False
                    conn.execute(
                        "DELETE FROM build_project_messages WHERE project_id = ?",
                        [project_id],
                    )
                    conn.execute(
                        "DELETE FROM build_projects WHERE id = ?",
                        [project_id],
                    )
                    conn.execute("COMMIT")
                    return True
                except Exception:
                    conn.execute("ROLLBACK")
                    raise
            finally:
                self._close_connection(conn)

    def get_history(self, project_id: str) -> dict[str, Any]:
        with self._lock:
            conn = self._get_connection()
            try:
                row = conn.execute(
                    """
                    SELECT messages_json, trajectory_json, updated_at
                    FROM build_project_messages
                    WHERE project_id = ?
                    """,
                    [project_id],
                ).fetchone()
            finally:
                self._close_connection(conn)
        if not row:
            return {"messages": [], "trajectory_events": [], "updated_at": None}
        try:
            messages = json.loads(row[0] or "[]")
        except json.JSONDecodeError:
            messages = []
        try:
            trajectory_events = json.loads(row[1] or "[]")
        except json.JSONDecodeError:
            trajectory_events = []
        return {
            "messages": messages if isinstance(messages, list) else [],
            "trajectory_events": trajectory_events if isinstance(trajectory_events, list) else [],
            "updated_at": row[2],
        }

    def save_history(
        self,
        project_id: str,
        messages: list[dict[str, Any]],
        trajectory_events: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        now = _utc_now()
        msg_str = json.dumps(messages, ensure_ascii=False)
        traj_str = json.dumps(trajectory_events or [], ensure_ascii=False)
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO build_project_messages (project_id, messages_json, trajectory_json, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (project_id) DO UPDATE SET
                        messages_json = excluded.messages_json,
                        trajectory_json = excluded.trajectory_json,
                        updated_at = excluded.updated_at
                    """,
                    [project_id, msg_str, traj_str, now],
                )
                conn.execute(
                    "UPDATE build_projects SET updated_at = ? WHERE id = ?",
                    [now, project_id],
                )
            finally:
                self._close_connection(conn)
        return {"messages": messages, "trajectory_events": trajectory_events or [], "updated_at": now}

    @staticmethod
    def _row_to_project(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "id": row[0],
            "name": row[1],
            "description": row[2] or "",
            "template": row[3] or "nextjs-vibe",
            "db_dialect": row[4] or "postgresql",
            "active_session_id": row[5],
            "runtime_image": row[6],
            "created_at": row[7],
            "updated_at": row[8],
        }

    # Async wrappers for FastAPI endpoints
    async def acreate_project(self, **kwargs: Any) -> dict[str, Any]:
        return await asyncio.to_thread(self.create_project, **kwargs)

    async def alist_projects(self) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self.list_projects)

    async def aget_project(self, project_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self.get_project, project_id)

    async def aupdate_session(self, project_id: str, session_id: str | None) -> None:
        await asyncio.to_thread(self.update_session, project_id, session_id)

    async def atouch_project(self, project_id: str) -> None:
        await asyncio.to_thread(self.touch_project, project_id)

    async def adelete_project(self, project_id: str) -> bool:
        return await asyncio.to_thread(self.delete_project, project_id)

    async def aget_history(self, project_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(self.get_history, project_id)

    async def asave_history(
        self,
        project_id: str,
        messages: list[dict[str, Any]],
        trajectory_events: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self.save_history, project_id, messages, trajectory_events)
