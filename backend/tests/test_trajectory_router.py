from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


def test_get_trajectory_json_jsonl_and_validation():
    client = TestClient(app)

    # Invalid run_id rejected by FastAPI regex path validation
    bad = client.get("/v1/agent/runs/invalid..id/trajectory")
    assert bad.status_code == 422

    sample_events = [
        {"event": "run.start", "run_id": "run_abc123", "seq": 1, "timestamp_ms": 1000, "data": {}, "timestamp": 1.0},
        {"event": "run.end", "run_id": "run_abc123", "seq": 2, "timestamp_ms": 1100, "data": {"status": "completed"}, "timestamp": 1.1},
    ]

    with patch("app.services.agent.trajectory.trajectory_store.list_events_after", new=AsyncMock(return_value=sample_events)):
        res_json = client.get("/v1/agent/runs/run_abc123/trajectory")
        assert res_json.status_code == 200
        body = res_json.json()
        assert body["run_id"] == "run_abc123"
        assert body["last_seq"] == 2
        assert len(body["events"]) == 2

    async def fake_stream(run_id: str, fmt: str = "jsonl", after_seq: int = 0):
        for ev in sample_events:
            yield json.dumps(ev) + "\n"

    with (
        patch("app.services.agent.trajectory.trajectory_store.list_events_after", new=AsyncMock(return_value=sample_events)),
        patch("app.services.agent.trajectory.trajectory_store.stream_export", side_effect=fake_stream),
    ):
        res_jsonl = client.get("/v1/agent/runs/run_abc123/trajectory?format=jsonl")
        assert res_jsonl.status_code == 200
        assert "application/x-ndjson" in res_jsonl.headers["content-type"]
        assert res_jsonl.headers["x-content-type-options"] == "nosniff"
        lines = [json.loads(line) for line in res_jsonl.text.strip().splitlines()]
        assert [l["seq"] for l in lines] == [1, 2]

    with patch("app.services.agent.trajectory.trajectory_store.list_events_after", new=AsyncMock(return_value=[])):
        res_404 = client.get("/v1/agent/runs/run_missing_99/trajectory")
        assert res_404.status_code == 404
