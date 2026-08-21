from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
import time
import uuid
from dataclasses import dataclass, field

import duckdb

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMEvent:
    request_id: str
    ts: float
    model_name: str
    endpoint: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    status: str = "ok"
    error_message: str | None = None
    stream: bool = False
    input_text: str | None = None
    output_text: str | None = None
    client_id: str | None = None
    metadata: dict = field(default_factory=dict)


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS llm_events (
    request_id VARCHAR PRIMARY KEY,
    ts TIMESTAMP,
    model_name VARCHAR,
    endpoint VARCHAR,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    latency_ms DOUBLE,
    status VARCHAR,
    error_message VARCHAR,
    stream BOOLEAN,
    input_text VARCHAR,
    output_text VARCHAR,
    client_id VARCHAR,
    metadata VARCHAR
)
"""

_CLEANUP_INTERVAL_S = 24 * 60 * 60


class MetricsWriter:
    """
    Single background consumer. Owns the only DuckDB connection used
    for writes. Never call duckdb write methods from anywhere else.
    """

    def __init__(self) -> None:
        self.queue: asyncio.Queue[LLMEvent] = asyncio.Queue(maxsize=settings.metrics_queue_size)
        self._conn: duckdb.DuckDBPyConnection | None = None
        self._run_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None
        self.dropped_events = 0

    async def start(self) -> None:
        settings.metrics_db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(str(settings.metrics_db_path))
        self._conn.execute(_SCHEMA_SQL)
        self._run_task = asyncio.create_task(self._run())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        for task in (self._run_task, self._cleanup_task):
            if task is not None:
                task.cancel()
        for task in (self._run_task, self._cleanup_task):
            if task is not None:
                try:
                    await asyncio.wait_for(task, timeout=5)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
        await self._drain_and_write()
        if self._conn is not None:
            self._conn.close()

    def log(self, event: LLMEvent) -> None:
        """Call this from request handlers. Never awaits, never blocks."""
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            self.dropped_events += 1
            logger.warning("Metrics queue full, dropping event %s", event.request_id)

    async def _run(self) -> None:
        while True:
            await self._drain_and_write()
            await asyncio.sleep(settings.metrics_flush_interval_s)

    async def _drain_and_write(self) -> None:
        batch: list[LLMEvent] = []
        while len(batch) < settings.metrics_batch_size:
            try:
                batch.append(self.queue.get_nowait())
            except asyncio.QueueEmpty:
                break

        if not batch:
            return

        await asyncio.to_thread(self._write_batch, batch)

    def _write_batch(self, batch: list[LLMEvent]) -> None:
        if self._conn is None:
            return
        try:
            self._conn.executemany(
                """
                INSERT INTO llm_events (
                    request_id, ts, model_name, endpoint, prompt_tokens,
                    completion_tokens, total_tokens, latency_ms, status,
                    error_message, stream, input_text, output_text, client_id, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    [
                        e.request_id,
                        datetime.fromtimestamp(e.ts, tz=timezone.utc).replace(tzinfo=None),
                        e.model_name,
                        e.endpoint,
                        e.prompt_tokens,
                        e.completion_tokens,
                        e.total_tokens,
                        e.latency_ms,
                        e.status,
                        e.error_message,
                        e.stream,
                        e.input_text,
                        e.output_text,
                        e.client_id,
                        json.dumps(e.metadata),
                    ]
                    for e in batch
                ],
            )
        except Exception:
            logger.exception("Failed to write metrics batch")

    async def cleanup_old_traces(self) -> None:
        if self._conn is None:
            return

        def _run() -> None:
            self._conn.execute(
                "UPDATE llm_events SET input_text = NULL, output_text = NULL "
                "WHERE ts < now() - INTERVAL (?) DAYS AND input_text IS NOT NULL",
                [settings.trace_retention_days],
            )

        try:
            await asyncio.to_thread(_run)
        except Exception:
            logger.exception("Trace retention cleanup failed")

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(_CLEANUP_INTERVAL_S)
            await self.cleanup_old_traces()


metrics_writer = MetricsWriter()


def new_request_id() -> str:
    return f"req-{uuid.uuid4().hex}"


def now_ts() -> float:
    return time.time()
