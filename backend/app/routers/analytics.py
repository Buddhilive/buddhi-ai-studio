from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.services import metrics_query
from app.services.metrics import metrics_writer

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _validate_range(start: datetime, end: datetime) -> None:
    if start > end:
        raise HTTPException(status_code=422, detail="start must be <= end")


def _auto_bucket(start: datetime, end: datetime) -> Literal["hour", "day"]:
    return "hour" if (end - start) <= timedelta(days=2) else "day"


@router.get("/summary")
async def summary(start: datetime, end: datetime) -> dict:
    _validate_range(start, end)
    data = await metrics_query.get_summary(start, end)
    data["dropped_events"] = metrics_writer.dropped_events
    return data


@router.get("/timeseries")
async def timeseries(
    metric: Literal["requests", "tokens", "latency", "errors"],
    start: datetime,
    end: datetime,
    bucket: Literal["hour", "day"] | None = None,
) -> list[dict]:
    _validate_range(start, end)
    resolved_bucket = bucket or _auto_bucket(start, end)
    return await metrics_query.get_timeseries(metric, start, end, resolved_bucket)


@router.get("/events")
async def events(
    start: datetime,
    end: datetime,
    status: Literal["ok", "error"] | None = None,
    model: str | None = None,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort: Literal["ts_desc", "ts_asc"] = "ts_desc",
) -> dict:
    _validate_range(start, end)
    items, total = await metrics_query.list_events(
        start, end, status, model, search, limit, offset, sort
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/events/{request_id}")
async def event_detail(request_id: str) -> dict:
    event = await metrics_query.get_event(request_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event
