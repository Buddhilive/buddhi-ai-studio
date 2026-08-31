import pytest
from unittest.mock import AsyncMock, patch

from app.mcp_server import (
    mcp_server,
    sandbox_execute_code,
    sandbox_run_command,
    sandbox_write_file,
    sandbox_read_file,
)
from app.schemas.sandbox import SandboxExecutionResult


@pytest.mark.asyncio
async def test_mcp_sandbox_tools_registered():
    tools = await mcp_server.list_tools()
    tool_names = [t.name for t in tools]
    assert "sandbox_execute_code" in tool_names
    assert "sandbox_run_command" in tool_names
    assert "sandbox_write_file" in tool_names
    assert "sandbox_read_file" in tool_names

    exec_tool = next(t for t in tools if t.name == "sandbox_execute_code")
    assert "code" in exec_tool.inputSchema["properties"]
    assert "language" in exec_tool.inputSchema["properties"]


@pytest.mark.asyncio
async def test_mcp_sandbox_execute_code_success():
    mock_result = SandboxExecutionResult(
        status="completed",
        stdout="144\n",
        stderr="",
        exit_code=0,
        execution_time_ms=120.0,
    )

    with patch("app.mcp_server.sandbox_service.execute_one_shot", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_result
        res = await sandbox_execute_code(code="print(12 * 12)")
        assert res["status"] == "completed"
        assert res["stdout"] == "144\n"
        assert res["exit_code"] == 0


@pytest.mark.asyncio
async def test_mcp_sandbox_execute_code_error_handling():
    with patch("app.mcp_server.sandbox_service.execute_one_shot", new_callable=AsyncMock) as mock_exec:
        mock_exec.side_effect = RuntimeError("Docker daemon disconnected")
        res = await sandbox_execute_code(code="print('fail')")
        assert res["status"] == "error"
        assert "Docker daemon disconnected" in res["error"]


@pytest.mark.asyncio
async def test_mcp_sandbox_run_command():
    mock_result = SandboxExecutionResult(
        status="completed",
        stdout="Linux\n",
        stderr="",
        exit_code=0,
        execution_time_ms=80.0,
    )

    with patch("app.mcp_server.sandbox_service.execute_one_shot", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_result
        res = await sandbox_run_command(command="uname -s")
        assert res["status"] == "completed"
        assert res["stdout"] == "Linux\n"


@pytest.mark.asyncio
async def test_mcp_sandbox_file_tools():
    with patch("app.mcp_server.sandbox_service.write_session_file", new_callable=AsyncMock) as mock_write, \
         patch("app.mcp_server.sandbox_service.read_session_file", new_callable=AsyncMock) as mock_read:
        mock_write.return_value = True
        mock_read.return_value = "hello world"

        write_res = await sandbox_write_file(session_id="test-123", path="test.txt", content="hello world")
        assert write_res["status"] == "success"

        read_res = await sandbox_read_file(session_id="test-123", path="test.txt")
        assert read_res["status"] == "success"
        assert read_res["content"] == "hello world"
