from __future__ import annotations

import logging
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
        self._init_db()

    def _init_db(self) -> None:
        try:
            with duckdb.connect(self.db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agent_checkpoints (
                        thread_id VARCHAR,
                        checkpoint_ns VARCHAR,
                        checkpoint_id VARCHAR,
                        parent_checkpoint_id VARCHAR,
                        type VARCHAR,
                        checkpoint VARCHAR,
                        metadata VARCHAR,
                        PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
                    )
                    """
                )
        except Exception as exc:
            logger.warning("Could not initialize DuckDB checkpoints table: %s. Using in-memory fallback.", exc)

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        if not config or "configurable" not in config or "thread_id" not in config["configurable"]:
            return None
        return self._memory_fallback.get_tuple(config)

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        if not config or "configurable" not in config or "thread_id" not in config["configurable"]:
            return None
        return await self._memory_fallback.aget_tuple(config)

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        return self._memory_fallback.list(config, filter=filter, before=before, limit=limit)

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        async for item in self._memory_fallback.alist(config, filter=filter, before=before, limit=limit):
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
        return self._memory_fallback.put(config, checkpoint, metadata, new_versions)

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        if not config or "configurable" not in config or "thread_id" not in config["configurable"]:
            return config
        return await self._memory_fallback.aput(config, checkpoint, metadata, new_versions)

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
    ) -> None:
        self._memory_fallback.put_writes(config, writes, task_id)

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
    ) -> None:
        await self._memory_fallback.aput_writes(config, writes, task_id)


agent_checkpointer = DuckDBCheckpointSaver()
