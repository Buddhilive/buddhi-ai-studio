from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.sandbox import SandboxExecutionRequest
from app.services.sandbox_service import SandboxService


@pytest.mark.asyncio
async def test_sandbox_execute_one_shot_success():
    service = SandboxService()
    mock_sandbox = AsyncMock()
    mock_exec = MagicMock()
    mock_exec.exit_code = 0
    mock_exec.error = None
    msg1 = MagicMock()
    msg1.is_error = False
    msg1.text = "Hello Sandbox\n"
    mock_exec.logs.content = [msg1]

    mock_sandbox.commands.run = AsyncMock(return_value=mock_exec)
    mock_sandbox.destroy = AsyncMock()

    with patch("opensandbox.Sandbox.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_sandbox
        req = SandboxExecutionRequest(code="print('Hello Sandbox')", language="python")
        result = await service.execute_one_shot(req)

        assert result.status == "completed"
        assert result.stdout == "Hello Sandbox\n"
        assert result.stderr == ""
        assert result.exit_code == 0
        mock_create.assert_awaited_once()
        mock_sandbox.destroy.assert_awaited_once()


@pytest.mark.asyncio
async def test_sandbox_execute_one_shot_timeout():
    service = SandboxService()
    mock_sandbox = AsyncMock()

    with patch("opensandbox.Sandbox.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_sandbox
        mock_sandbox.commands.run = AsyncMock(side_effect=TimeoutError())
        mock_sandbox.destroy = AsyncMock()

        req = SandboxExecutionRequest(code="while True: pass", language="python", timeout_s=1)
        result = await service.execute_one_shot(req)

        assert result.status == "timeout"
        assert result.exit_code == 124
        assert "timed out" in result.stderr
        mock_sandbox.destroy.assert_awaited_once()


@pytest.mark.asyncio
async def test_sandbox_check_health():
    service = SandboxService()
    await service.start()

    with patch.object(service._http_client, "get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        status = await service.check_health()
        assert status.status == "healthy"
        assert status.server_connected is True
        assert status.active_sessions_count == 0

    await service.stop()


def test_sandbox_execute_endpoint():
    client = TestClient(app)
    mock_res = {
        "status": "completed",
        "stdout": "42\n",
        "stderr": "",
        "exit_code": 0,
        "execution_time_ms": 150.0,
    }

    with patch("app.services.sandbox_service.sandbox_service.execute_one_shot", new_callable=AsyncMock) as mock_exec:
        from app.schemas.sandbox import SandboxExecutionResult
        mock_exec.return_value = SandboxExecutionResult(**mock_res)

        response = client.post("/v1/sandbox/execute", json={"code": "print(42)", "language": "python"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["stdout"] == "42\n"
        assert data["exit_code"] == 0


def test_sandbox_health_endpoint():
    client = TestClient(app)
    with patch("app.services.sandbox_service.sandbox_service.check_health", new_callable=AsyncMock) as mock_health:
        from app.schemas.sandbox import SandboxHealthStatus
        mock_health.return_value = SandboxHealthStatus(
            status="healthy",
            server_connected=True,
            server_url="http://localhost:8090",
            active_sessions_count=0,
        )

        response = client.get("/v1/sandbox/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["server_connected"] is True
