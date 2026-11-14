from __future__ import annotations

import asyncio
import json
import logging
from datetime import timezone
from typing import Any, AsyncGenerator, Literal

from app.services.metrics import metrics_writer

logger = logging.getLogger(__name__)


def _row_to_event_dict(row: tuple[Any, ...]) -> dict[str, Any]:
    run_id, seq, event_type, node, turn_id, span_id, parent_span_id, data_json, ts = row
    if ts is not None and ts.tzinfo is None:
        ts_utc = ts.replace(tzinfo=timezone.utc)
    else:
        ts_utc = ts
    epoch_s = ts_utc.timestamp() if ts_utc is not None else 0.0
    try:
        data = json.loads(data_json) if data_json else {}
    except Exception:
        data = {}
    return {
        "event": event_type,
        "run_id": run_id,
        "seq": int(seq),
        "timestamp_ms": int(epoch_s * 1000),
        "turn_id": turn_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "node": node,
        "data": data,
        "timestamp": epoch_s,
    }


class TrajectoryStore:
    """Read and export persisted agent trajectory events from DuckDB."""

    async def list_events_after(
        self,
        run_id: str,
        after_seq: int = 0,
        limit: int = 2000,
    ) -> list[dict[str, Any]]:
        await metrics_writer.flush_trajectory()

        def _query() -> list[dict[str, Any]]:
            cur = metrics_writer.cursor()
            if cur is None:
                return []
            try:
                rows = cur.execute(
                    """
                    SELECT run_id, seq, event_type, node, turn_id, span_id, parent_span_id, data_json, ts
                    FROM trajectory_events
                    WHERE run_id = ? AND seq > ?
                    ORDER BY seq ASC
                    LIMIT ?
                    """,
                    [run_id, after_seq, limit],
                ).fetchall()
                return [_row_to_event_dict(r) for r in rows]
            finally:
                cur.close()

        return await asyncio.to_thread(_query)

    async def stream_export(
        self,
        run_id: str,
        fmt: Literal["json", "jsonl"] = "jsonl",
        after_seq: int = 0,
    ) -> AsyncGenerator[str, None]:
        events = await self.list_events_after(run_id, after_seq=after_seq, limit=100_000)
        if fmt == "jsonl":
            for ev in events:
                yield json.dumps(ev) + "\n"
        else:
            last_seq = events[-1]["seq"] if events else after_seq
            yield json.dumps({"run_id": run_id, "last_seq": last_seq, "events": events})


trajectory_store = TrajectoryStore()
