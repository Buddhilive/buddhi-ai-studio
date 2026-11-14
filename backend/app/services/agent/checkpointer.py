from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, AsyncIterator, Iterator, Sequence
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.memory import InMemorySaver
import duckdb

from app.core.config import settings

logger = logging.getLogger(__name__)


class DuckDBCheckpointSaver(BaseCheckpointSaver):
    """DuckDB persistent state checkpointer for LangGraph agent runs."""

    def __init__(self, db_path: str | None = None) -> None:
        super().__init__()
        self.db_path = db_path or str(settings.metrics_db_path.parent / "agent_checkpoints.duckdb")
        self._memory_fallback = InMemorySaver()
        self._lock = threading.RLock()
        self._is_in_memory = self.db_path == ":memory:"
        self._in_memory_conn: duckdb.DuckDBPyConnection | None = None
        if self._is_in_memory:
            self._in_memory_conn = duckdb.connect(":memory:")
        self._init_db()

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        if self._is_in_memory and self._in_memory_conn is not None:
            return self._in_memory_conn
        return duckdb.connect(self.db_path)

    def _init_db(self) -> None:
        try:
            with self._lock:
                if self._is_in_memory and self._in_memory_conn is not None:
                    conn = self._in_memory_conn
                    self._create_tables(conn)
                else:
                    with duckdb.connect(self.db_path) as conn:
                        self._create_tables(conn)
        except Exception as exc:
            logger.warning("Could not initialize DuckDB checkpoints table: %s. Using in-memory fallback.", exc)

    def _create_tables(self, conn: duckdb.DuckDBPyConnection) -> None:
        # Forward migration: inspect columns of agent_checkpoints if it exists
        cols = [
            row[0].lower()
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'agent_checkpoints'"
            ).fetchall()
        ]
        if cols and "checkpoint_blob" not in cols:
            logger.info("Migrating legacy schema for agent_checkpoints in %s", self.db_path)
            conn.execute("DROP TABLE IF EXISTS agent_checkpoints")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_checkpoints (
                thread_id VARCHAR NOT NULL,
                checkpoint_ns VARCHAR NOT NULL DEFAULT '',
                checkpoint_id VARCHAR NOT NULL,
                parent_checkpoint_id VARCHAR,
                checkpoint_type VARCHAR NOT NULL,
                checkpoint_blob BLOB NOT NULL,
                metadata_type VARCHAR NOT NULL,
                metadata_blob BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_ns
            ON agent_checkpoints (thread_id, checkpoint_ns, checkpoint_id DESC)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_checkpoint_writes (
                thread_id VARCHAR NOT NULL,
                checkpoint_ns VARCHAR NOT NULL DEFAULT '',
                checkpoint_id VARCHAR NOT NULL,
                task_id VARCHAR NOT NULL,
                idx INTEGER NOT NULL,
                channel VARCHAR NOT NULL,
                value_type VARCHAR NOT NULL,
                value_blob BLOB NOT NULL,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
            )
            """
        )

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        if not config or "configurable" not in config or "thread_id" not in config["configurable"]:
            return None

        thread_id = str(config["configurable"]["thread_id"])
        checkpoint_ns = str(config["configurable"].get("checkpoint_ns", ""))
        checkpoint_id = config["configurable"].get("checkpoint_id")

        try:
            with self._lock:
                conn = self._get_connection()
                try:
                    if checkpoint_id:
                        query = """
                            SELECT thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id,
                                   checkpoint_type, checkpoint_blob, metadata_type, metadata_blob
                            FROM agent_checkpoints
                            WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?
                        """
                        params = [thread_id, checkpoint_ns, str(checkpoint_id)]
                    else:
                        query = """
                            SELECT thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id,
                                   checkpoint_type, checkpoint_blob, metadata_type, metadata_blob
                            FROM agent_checkpoints
                            WHERE thread_id = ? AND checkpoint_ns = ?
                            ORDER BY checkpoint_id DESC
                            LIMIT 1
                        """
                        params = [thread_id, checkpoint_ns]

                    row = conn.execute(query, params).fetchone()
                    if not row:
                        return self._memory_fallback.get_tuple(config)

                    (
                        r_thread_id,
                        r_checkpoint_ns,
                        r_checkpoint_id,
                        r_parent_id,
                        ckpt_type,
                        ckpt_blob,
                        meta_type,
                        meta_blob,
                    ) = row

                    checkpoint = self.serde.loads_typed((ckpt_type, bytes(ckpt_blob)))
                    metadata = self.serde.loads_typed((meta_type, bytes(meta_blob)))

                    # Load pending writes
                    writes_query = """
                        SELECT task_id, channel, value_type, value_blob
                        FROM agent_checkpoint_writes
                        WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?
                        ORDER BY task_id, idx
                    """
                    write_rows = conn.execute(writes_query, [r_thread_id, r_checkpoint_ns, r_checkpoint_id]).fetchall()
                    pending_writes = [
                        (w_task_id, w_channel, self.serde.loads_typed((w_val_type, bytes(w_val_blob))))
                        for w_task_id, w_channel, w_val_type, w_val_blob in write_rows
                    ]

                    final_config: RunnableConfig = {
                        "configurable": {
                            "thread_id": r_thread_id,
                            "checkpoint_ns": r_checkpoint_ns,
                            "checkpoint_id": r_checkpoint_id,
                        }
                    }
                    parent_config: RunnableConfig | None = None
                    if r_parent_id:
                        parent_config = {
                            "configurable": {
                                "thread_id": r_thread_id,
                                "checkpoint_ns": r_checkpoint_ns,
                                "checkpoint_id": r_parent_id,
                            }
                        }

                    return CheckpointTuple(
                        config=final_config,
                        checkpoint=checkpoint,
                        metadata=metadata,
                        parent_config=parent_config,
                        pending_writes=pending_writes,
                    )
                finally:
                    if not self._is_in_memory:
                        conn.close()
        except Exception as exc:
            logger.warning("Error reading checkpoint from DuckDB: %s. Falling back to memory.", exc)
            return self._memory_fallback.get_tuple(config)

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        return await asyncio.to_thread(self.get_tuple, config)

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        if not config or "configurable" not in config or "thread_id" not in config["configurable"]:
            return

        thread_id = str(config["configurable"]["thread_id"])
        checkpoint_ns = str(config["configurable"].get("checkpoint_ns", ""))

        try:
            with self._lock:
                conn = self._get_connection()
                try:
                    where_clauses = ["thread_id = ?", "checkpoint_ns = ?"]
                    params: list[Any] = [thread_id, checkpoint_ns]

                    if before and "configurable" in before and "checkpoint_id" in before["configurable"]:
                        where_clauses.append("checkpoint_id < ?")
                        params.append(str(before["configurable"]["checkpoint_id"]))

                    query = f"""
                        SELECT thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id,
                               checkpoint_type, checkpoint_blob, metadata_type, metadata_blob
                        FROM agent_checkpoints
                        WHERE {' AND '.join(where_clauses)}
                        ORDER BY checkpoint_id DESC
                    """
                    if limit is not None:
                        query += f" LIMIT {int(limit)}"

                    rows = conn.execute(query, params).fetchall()
                    for row in rows:
                        (
                            r_thread_id,
                            r_checkpoint_ns,
                            r_checkpoint_id,
                            r_parent_id,
                            ckpt_type,
                            ckpt_blob,
                            meta_type,
                            meta_blob,
                        ) = row
                        checkpoint = self.serde.loads_typed((ckpt_type, bytes(ckpt_blob)))
                        metadata = self.serde.loads_typed((meta_type, bytes(meta_blob)))

                        # Filter match
                        if filter:
                            if not all(metadata.get(k) == v for k, v in filter.items()):
                                continue

                        writes_query = """
                            SELECT task_id, channel, value_type, value_blob
                            FROM agent_checkpoint_writes
                            WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?
                            ORDER BY task_id, idx
                        """
                        write_rows = conn.execute(writes_query, [r_thread_id, r_checkpoint_ns, r_checkpoint_id]).fetchall()
                        pending_writes = [
                            (w_task_id, w_channel, self.serde.loads_typed((w_val_type, bytes(w_val_blob))))
                            for w_task_id, w_channel, w_val_type, w_val_blob in write_rows
                        ]

                        final_config: RunnableConfig = {
                            "configurable": {
                                "thread_id": r_thread_id,
                                "checkpoint_ns": r_checkpoint_ns,
                                "checkpoint_id": r_checkpoint_id,
                            }
                        }
                        parent_config: RunnableConfig | None = None
                        if r_parent_id:
                            parent_config = {
                                "configurable": {
                                    "thread_id": r_thread_id,
                                    "checkpoint_ns": r_checkpoint_ns,
                                    "checkpoint_id": r_parent_id,
                                }
                            }

                        yield CheckpointTuple(
                            config=final_config,
                            checkpoint=checkpoint,
                            metadata=metadata,
                            parent_config=parent_config,
                            pending_writes=pending_writes,
                        )
                finally:
                    if not self._is_in_memory:
                        conn.close()
        except Exception as exc:
            logger.warning("Error listing checkpoints from DuckDB: %s. Falling back to memory.", exc)
            yield from self._memory_fallback.list(config, filter=filter, before=before, limit=limit)

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        loop = asyncio.get_running_loop()
        tuples = await loop.run_in_executor(None, lambda: list(self.list(config, filter=filter, before=before, limit=limit)))
        for item in tuples:
            yield item

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        if not config or "configurable" not in config or "thread_id" not in config["configurable"]:
            return config

        thread_id = str(config["configurable"]["thread_id"])
        checkpoint_ns = str(config["configurable"].get("checkpoint_ns", ""))
        checkpoint_id = checkpoint["id"]
        parent_checkpoint_id = config["configurable"].get("checkpoint_id")

        # Ensure configurable dict has checkpoint_ns for in-memory fallback
        norm_config = dict(config)
        norm_configurable = dict(config.get("configurable", {}))
        norm_configurable.setdefault("checkpoint_ns", "")
        norm_config["configurable"] = norm_configurable

        self._memory_fallback.put(norm_config, checkpoint, metadata, new_versions)

        try:
            ckpt_type, ckpt_blob = self.serde.dumps_typed(checkpoint)
            meta_type, meta_blob = self.serde.dumps_typed(metadata)

            with self._lock:
                conn = self._get_connection()
                try:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO agent_checkpoints (
                            thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id,
                            checkpoint_type, checkpoint_blob, metadata_type, metadata_blob
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            thread_id,
                            checkpoint_ns,
                            str(checkpoint_id),
                            str(parent_checkpoint_id) if parent_checkpoint_id else None,
                            ckpt_type,
                            ckpt_blob,
                            meta_type,
                            meta_blob,
                        ],
                    )
                finally:
                    if not self._is_in_memory:
                        conn.close()
        except Exception as exc:
            logger.warning("Error persisting checkpoint to DuckDB: %s", exc)

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
    ) -> None:
        self._memory_fallback.put_writes(config, writes, task_id)

        if not config or "configurable" not in config or "thread_id" not in config["configurable"]:
            return

        thread_id = str(config["configurable"]["thread_id"])
        checkpoint_ns = str(config["configurable"].get("checkpoint_ns", ""))
        checkpoint_id = str(config["configurable"].get("checkpoint_id", ""))

        try:
            rows_to_insert = []
            for idx, (channel, value) in enumerate(writes):
                val_type, val_blob = self.serde.dumps_typed(value)
                rows_to_insert.append((
                    thread_id,
                    checkpoint_ns,
                    checkpoint_id,
                    str(task_id),
                    idx,
                    channel,
                    val_type,
                    val_blob,
                ))

            with self._lock:
                conn = self._get_connection()
                try:
                    conn.executemany(
                        """
                        INSERT OR REPLACE INTO agent_checkpoint_writes (
                            thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, value_type, value_blob
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        rows_to_insert,
                    )
                finally:
                    if not self._is_in_memory:
                        conn.close()
        except Exception as exc:
            logger.warning("Error persisting checkpoint writes to DuckDB: %s", exc)

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
    ) -> None:
        await asyncio.to_thread(self.put_writes, config, writes, task_id)


agent_checkpointer = DuckDBCheckpointSaver()
