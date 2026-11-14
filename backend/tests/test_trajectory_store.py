from __future__ import annotations

import sys
import asyncio

from app.core.config import settings
from app.schemas.agent import AgentEvent
from app.services.agent.trajectory import TrajectoryStore
from app.services.metrics import MetricsWriter


async def test_trajectory_store_persists_replays_after_seq_and_recovers(tmp_path, monkeypatch):
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    db_file = tmp_path / "test_metrics.duckdb"
    monkeypatch.setattr(settings, "metrics_db_path", db_file)

    writer = MetricsWriter()
    await writer.start()
    monkeypatch.setattr("app.services.agent.trajectory.metrics_writer", writer)

    try:
        for seq in (1, 2, 3):
            writer.log_trajectory(
                AgentEvent(
                    event="text.delta",
                    run_id="run_store_01",
                    seq=seq,
                    turn_id="turn_1",
                    node="act",
                    data={"delta": f"chunk_{seq}"},
                )
            )
        await writer.flush_trajectory()

        store = TrajectoryStore()
        all_events = await store.list_events_after("run_store_01", after_seq=0)
        assert [e["seq"] for e in all_events] == [1, 2, 3]

        tail_events = await store.list_events_after("run_store_01", after_seq=2)
        assert [e["seq"] for e in tail_events] == [3]
    finally:
        await writer.stop()

    # Re-open fresh MetricsWriter to verify durability across restarts
    writer2 = MetricsWriter()
    await writer2.start()
    monkeypatch.setattr("app.services.agent.trajectory.metrics_writer", writer2)
    try:
        store2 = TrajectoryStore()
        reloaded = await store2.list_events_after("run_store_01", after_seq=0)
        assert [e["seq"] for e in reloaded] == [1, 2, 3]
    finally:
        await writer2.stop()
