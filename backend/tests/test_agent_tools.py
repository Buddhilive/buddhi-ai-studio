import asyncio
import sys
from unittest.mock import AsyncMock
import pytest

from app.schemas.sandbox import SandboxExecutionResult
from app.services.agent.tools import _truncate_output, execute_tool, sandbox_service

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def test_truncate_output():
    short_text = "Hello world"
    res, truncated = _truncate_output(short_text, cap=50)
    assert res == short_text
    assert not truncated

    long_text = "A" * 100
    res, truncated = _truncate_output(long_text, cap=20)
    assert truncated
    assert res.startswith("A" * 20)
    assert "[TRUNCATED - 80 characters omitted]" in res


def test_execute_tool_run_command_success():
    async def _run():
        mock_exec = AsyncMock()
        mock_exec.return_value = SandboxExecutionResult(
            status="completed",
            stdout="test output\n",
            stderr="",
            exit_code=0,
            execution_time_ms=15.0,
        )
        orig = sandbox_service.execute_in_session
        sandbox_service.execute_in_session = mock_exec
        try:
            status, output, exit_code, truncated = await execute_tool(
                "run_command",
                {"command": "echo 'test'"},
                "session_123",
            )
            assert status == "completed"
            assert output == "test output\n"
            assert exit_code == 0
            assert not truncated
        finally:
            sandbox_service.execute_in_session = orig

    asyncio.run(_run())


def test_execute_tool_write_and_read_file():
    async def _run():
        mock_write = AsyncMock(return_value=True)
        mock_read = AsyncMock(return_value="file content here")

        orig_write = sandbox_service.write_session_file
        orig_read = sandbox_service.read_session_file
        sandbox_service.write_session_file = mock_write
        sandbox_service.read_session_file = mock_read
        try:
            # write_file
            status, output, exit_code, _ = await execute_tool(
                "write_file",
                {"path": "test.txt", "content": "file content here"},
                "session_123",
            )
            assert status == "completed"
            assert "written successfully" in output
            assert exit_code == 0
            mock_write.assert_awaited_once_with("session_123", "test.txt", "file content here")

            # read_file
            status, output, exit_code, _ = await execute_tool(
                "read_file",
                {"path": "test.txt"},
                "session_123",
            )
            assert status == "completed"
            assert output == "file content here"
            assert exit_code == 0
            mock_read.assert_awaited_once_with("session_123", "test.txt")
        finally:
            sandbox_service.write_session_file = orig_write
            sandbox_service.read_session_file = orig_read

    asyncio.run(_run())


def test_execute_tool_unknown_or_missing_args():
    async def _run():
        status, output, exit_code, _ = await execute_tool("unknown_tool", {}, "session_123")
        assert status == "error"
        assert "Unknown tool" in output
        assert exit_code == 1

        status, output, exit_code, _ = await execute_tool("run_command", {}, "session_123")
        assert status == "error"
        assert "required" in output

    asyncio.run(_run())
