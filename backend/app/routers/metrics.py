from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from app.services.metrics import metrics_writer

router = APIRouter(tags=["metrics"])

REQUESTS = Counter("llm_requests_total", "Total requests", ["endpoint", "status"])
LATENCY = Histogram("llm_request_latency_ms", "Latency in ms", ["model"])
DROPPED_EVENTS = Gauge("llm_metrics_dropped_events_total", "Metrics events dropped due to full queue")


@router.get("/metrics")
def metrics() -> Response:
    DROPPED_EVENTS.set(metrics_writer.dropped_events)
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
