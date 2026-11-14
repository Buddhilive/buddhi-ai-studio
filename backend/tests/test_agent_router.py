import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.agent.events import AgentEventEmitter
from app.services.agent.runs import AgentConcurrencyLimitError, agent_run_manager

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def test_agent_model_validation_failure():
    client = TestClient(app)
    resp = client.post(
        "/v1/agent/runs",
        json={
            "model": "non-existent-model",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert resp.status_code == 400
    assert "does not exist" in resp.json()["error"]["message"]


def test_agent_cancel_endpoint():
    async def _run():
        emitter = AgentEventEmitter("test_cancel_1")
        mock_task = MagicMock()
        mock_task.done.return_value = False
        mock_task.cancel = MagicMock()

        # Insert active run
        from app.services.agent.runs import ActiveRun
        run = ActiveRun("test_cancel_1", emitter, mock_task)
        agent_run_manager._active_runs["test_cancel_1"] = run

        client = TestClient(app)
        resp = client.delete("/v1/agent/runs/test_cancel_1")
        assert resp.status_code == 200
        assert resp.json() == {"status": "cancelled", "run_id": "test_cancel_1"}

        # 404 for unknown run
        resp_404 = client.delete("/v1/agent/runs/unknown_run")
        assert resp_404.status_code == 404

    asyncio.run(_run())


def test_egm_settings_and_artifacts_endpoints():
    client = TestClient(app)

    # 1. Test GET /api/settings/egm
    res = client.get("/api/settings/egm")
    assert res.status_code == 200
    data = res.json()
    assert "enabled" in data
    assert "max_review_rounds" in data

    # 2. Test PUT /api/settings/egm
    put_res = client.put(
        "/api/settings/egm",
        json={
            "enabled": True,
            "max_review_rounds": 5,
            "goldfish_concurrency": 2,
            "reviewer_timeout_s": 120,
            "context_budget_tokens": 8192,
            "enable_brainstorm": True,
            "default_skill_mode": "standard",
        },
    )
    assert put_res.status_code == 200
    assert put_res.json()["enabled"] is True
    assert put_res.json()["max_review_rounds"] == 5

    # Reset
    client.put("/api/settings/egm", json=data)

    # 3. Test 404 on artifacts for nonexistent run
    art_res = client.get("/v1/agent/runs/nonexistent_123/artifacts")
    assert art_res.status_code == 404


def test_agent_concurrency_throttle():
    async def _run():
        with patch.object(
            agent_run_manager,
            "start_run",
            side_effect=AgentConcurrencyLimitError("Concurrency limit reached (2 active runs)."),
        ), patch("app.routers.agent._validate_model"):
            client = TestClient(app)
            resp = client.post(
                "/v1/agent/runs",
                json={
                    "model": "gemma-4-e4b",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )
            assert resp.status_code == 429
            data = resp.json()
            assert "error" in data
            assert data["error"]["type"] == "rate_limit_exceeded"

    asyncio.run(_run())
