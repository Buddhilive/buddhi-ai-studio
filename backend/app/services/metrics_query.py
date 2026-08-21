from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Literal

import duckdb

from app.services.metrics import metrics_writer

Metric = Literal["requests", "tokens", "latency", "errors"]
Bucket = Literal["hour", "day"]

_EVENT_LIST_COLUMNS = (
    "request_id, ts, model_name, endpoint, prompt_tokens, completion_tokens, "
    "total_tokens, latency_ms, status, error_message, stream, client_id"
)
_EVENT_DETAIL_COLUMNS = _EVENT_LIST_COLUMNS + ", input_text, output_text, metadata"

_METRIC_EXPR: dict[Metric, str] = {
    "requests": "COUNT(*)",
    "tokens": "COALESCE(SUM(total_tokens), 0)",
    "latency": "COALESCE(AVG(latency_ms), 0)",
    "errors": "COUNT(*) FILTER (WHERE status = 'error')",
}


def _empty_summary() -> dict[str, Any]:
    return {
        "total_requests": 0,
        "ok_requests": 0,
        "error_requests": 0,
        "error_rate": 0.0,
        "total_tokens": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "avg_latency_ms": 0.0,
        "p95_latency_ms": 0.0,
        "streaming_requests": 0,
    }


def _connect_read_only() -> duckdb.DuckDBPyConnection | None:
    return metrics_writer.cursor()


def _row_to_event(row: tuple, columns: list[str]) -> dict[str, Any]:
    event = dict(zip(columns, row))
    if isinstance(event.get("ts"), datetime):
        event["ts"] = event["ts"].isoformat() + "Z"
    if "metadata" in event and event["metadata"]:
        try:
            event["metadata"] = json.loads(event["metadata"])
        except (TypeError, json.JSONDecodeError):
            event["metadata"] = {}
    return event


async def get_summary(start: datetime, end: datetime) -> dict[str, Any]:
    def _run() -> dict[str, Any]:
        conn = _connect_read_only()
        if conn is None:
            return _empty_summary()
        try:
            row = conn.execute(
                """
                SELECT
                    COUNT(*),
                    COUNT(*) FILTER (WHERE status = 'ok'),
                    COUNT(*) FILTER (WHERE status = 'error'),
                    COALESCE(SUM(total_tokens), 0),
                    COALESCE(SUM(prompt_tokens), 0),
                    COALESCE(SUM(completion_tokens), 0),
                    COALESCE(AVG(latency_ms), 0),
                    COALESCE(QUANTILE_CONT(latency_ms, 0.95), 0),
                    COUNT(*) FILTER (WHERE stream)
                FROM llm_events
                WHERE ts >= ? AND ts <= ?
                """,
                [start, end],
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            return _empty_summary()

        (
            total,
            ok,
            error,
            total_tokens,
            prompt_tokens,
            completion_tokens,
            avg_latency,
            p95_latency,
            streaming,
        ) = row
        return {
            "total_requests": total,
            "ok_requests": ok,
            "error_requests": error,
            "error_rate": (error / total) if total else 0.0,
            "total_tokens": total_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "streaming_requests": streaming,
        }

    return await asyncio.to_thread(_run)


async def get_timeseries(
    metric: Metric, start: datetime, end: datetime, bucket: Bucket
) -> list[dict[str, Any]]:
    def _run() -> list[dict[str, Any]]:
        conn = _connect_read_only()
        if conn is None:
            return []
        try:
            expr = _METRIC_EXPR[metric]
            rows = conn.execute(
                f"""
                SELECT date_trunc(?, ts) AS bucket, {expr} AS value
                FROM llm_events
                WHERE ts >= ? AND ts <= ?
                GROUP BY bucket
                ORDER BY bucket
                """,
                [bucket, start, end],
            ).fetchall()
        finally:
            conn.close()
        return [
            {"bucket": b.isoformat() + "Z" if isinstance(b, datetime) else b, "value": v}
            for b, v in rows
        ]

    return await asyncio.to_thread(_run)


async def list_events(
    start: datetime,
    end: datetime,
    status: str | None,
    model: str | None,
    search: str | None,
    limit: int,
    offset: int,
    sort: Literal["ts_desc", "ts_asc"],
) -> tuple[list[dict[str, Any]], int]:
    def _run() -> tuple[list[dict[str, Any]], int]:
        conn = _connect_read_only()
        if conn is None:
            return [], 0
        try:
            where = ["ts >= ?", "ts <= ?"]
            params: list[Any] = [start, end]
            if status:
                where.append("status = ?")
                params.append(status)
            if model:
                where.append("model_name = ?")
                params.append(model)
            if search:
                where.append("(request_id ILIKE ? OR model_name ILIKE ?)")
                like = f"%{search}%"
                params.extend([like, like])
            where_sql = " AND ".join(where)

            total = conn.execute(
                f"SELECT COUNT(*) FROM llm_events WHERE {where_sql}", params
            ).fetchone()[0]

            order_sql = "ts DESC" if sort == "ts_desc" else "ts ASC"
            rows = conn.execute(
                f"""
                SELECT {_EVENT_LIST_COLUMNS}
                FROM llm_events
                WHERE {where_sql}
                ORDER BY {order_sql}
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
            columns = _EVENT_LIST_COLUMNS.replace(" ", "").split(",")
        finally:
            conn.close()

        events = [_row_to_event(row, columns) for row in rows]
        return events, total

    return await asyncio.to_thread(_run)


async def get_event(request_id: str) -> dict[str, Any] | None:
    def _run() -> dict[str, Any] | None:
        conn = _connect_read_only()
        if conn is None:
            return None
        try:
            row = conn.execute(
                f"SELECT {_EVENT_DETAIL_COLUMNS} FROM llm_events WHERE request_id = ?",
                [request_id],
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        columns = _EVENT_DETAIL_COLUMNS.replace(" ", "").split(",")
        return _row_to_event(row, columns)

    return await asyncio.to_thread(_run)
