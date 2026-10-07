from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.sandbox import SandboxExecutionRequest, SandboxSessionCreateRequest
from app.services.sandbox_service import SandboxService


@pytest.mark.asyncio
async def test_session_lifecycle():
    service = SandboxService()
    mock_sandbox = AsyncMock()
    mock_sandbox.id = "sess-123"
    mock_sandbox.destroy = AsyncMock()

    with patch("opensandbox.Sandbox.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_sandbox

        req = SandboxSessionCreateRequest(runtime_image="python:3.11-slim", timeout_s=300)
        session_res = await service.create_session(req)

        assert session_res.session_id == "sess-123"
        assert session_res.status == "running"
        assert session_res.runtime_image == "python:3.11-slim"

        sessions = await service.list_sessions()
        assert len(sessions) == 1
        assert sessions[0].session_id == "sess-123"

        get_sess = await service.get_session("sess-123")
        assert get_sess is not None

        term = await service.terminate_session("sess-123")
        assert term is True
        mock_sandbox.destroy.assert_awaited_once()

        sessions_after = await service.list_sessions()
        assert len(sessions_after) == 0


@pytest.mark.asyncio
async def test_session_file_operations():
    service = SandboxService()
    mock_sandbox = AsyncMock()
    mock_sandbox.id = "sess-file-1"
    mock_sandbox.files.write_file = AsyncMock()
    mock_sandbox.files.read_bytes = AsyncMock(return_value=b"print('hello from workspace')")

    with patch("opensandbox.Sandbox.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_sandbox

        await service.create_session(SandboxSessionCreateRequest())
        write_ok = await service.write_session_file("sess-file-1", "script.py", "print('hello from workspace')")
        assert write_ok is True
        mock_sandbox.files.write_file.assert_awaited_once()

        content = await service.read_session_file("sess-file-1", "script.py")
        assert content == "print('hello from workspace')"


@pytest.mark.asyncio
async def test_session_execute():
    service = SandboxService()
    mock_sandbox = AsyncMock()
    mock_sandbox.id = "sess-exec-1"
    mock_exec = MagicMock()
    mock_exec.exit_code = 0
    mock_exec.error = None
    msg = MagicMock()
    msg.is_error = False
    msg.text = "Session output\n"
    mock_exec.logs.content = [msg]
    mock_sandbox.commands.run = AsyncMock(return_value=mock_exec)

    with patch("opensandbox.Sandbox.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_sandbox

        await service.create_session(SandboxSessionCreateRequest())
        req = SandboxExecutionRequest(code="print('Session output')", language="python")
        result = await service.execute_in_session("sess-exec-1", req)

        assert result.status == "completed"
        assert result.stdout == "Session output\n"
        assert result.exit_code == 0


def test_session_rest_endpoints():
    client = TestClient(app)

    mock_session_data = {
        "session_id": "api-sess-1",
        "runtime_image": "python:3.11-slim",
        "status": "running",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_activity_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": datetime.now(timezone.utc).isoformat(),
        "allow_network": False,
    }

    from app.schemas.sandbox import SandboxSessionResponse

    with patch("app.services.sandbox_service.sandbox_service.create_session", new_callable=AsyncMock) as mock_create, \
         patch("app.services.sandbox_service.sandbox_service.list_sessions", new_callable=AsyncMock) as mock_list, \
         patch("app.services.sandbox_service.sandbox_service.terminate_session", new_callable=AsyncMock) as mock_term, \
         patch("app.services.sandbox_service.sandbox_service.write_session_file", new_callable=AsyncMock) as mock_wf, \
         patch("app.services.sandbox_service.sandbox_service.read_session_file", new_callable=AsyncMock) as mock_rf:

        mock_create.return_value = SandboxSessionResponse(**mock_session_data)
        mock_list.return_value = [SandboxSessionResponse(**mock_session_data)]
        mock_term.return_value = True
        mock_wf.return_value = True
        mock_rf.return_value = "file contents"

        # Create session
        res_create = client.post("/v1/sandbox/sessions", json={"runtime_image": "python:3.11-slim"})
        assert res_create.status_code == 201
        assert res_create.json()["session_id"] == "api-sess-1"

        # List sessions
        res_list = client.get("/v1/sandbox/sessions")
        assert res_list.status_code == 200
        assert len(res_list.json()) == 1

        # Write file
        res_wf = client.post("/v1/sandbox/sessions/api-sess-1/files", json={"path": "main.py", "content": "print(1)"})
        assert res_wf.status_code == 200
        assert res_wf.json()["status"] == "created"

        # Read file
        res_rf = client.get("/v1/sandbox/sessions/api-sess-1/files/main.py")
        assert res_rf.status_code == 200
        assert res_rf.json()["content"] == "file contents"

        # Delete session
        res_del = client.delete("/v1/sandbox/sessions/api-sess-1")
        assert res_del.status_code == 200
        assert res_del.json()["status"] == "terminated"
