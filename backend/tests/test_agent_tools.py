import asyncio
import sys
from unittest.mock import AsyncMock
import pytest

from app.schemas.sandbox import SandboxExecutionResult
from app.services.agent.tools import (
    ToolGuardrailContext,
    _truncate_output,
    execute_tool,
    sandbox_service,
    validate_workspace_path,
)

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

    asyncio.run(_run())


def test_egm_guardrails_pre_approval_writes():
    async def _run():
        mock_write = AsyncMock(return_value=True)
        orig_write = sandbox_service.write_session_file
        sandbox_service.write_session_file = mock_write

        try:
            # Pre-approval context (Phases 1-4)
            ctx = ToolGuardrailContext(
                is_egm_mode=True,
                run_id="run_abc",
                egm_phase="draft",
                spec_approved=False,
            )

            # 1. Attempting to write production source file should fail closed
            status, output, exit_code, _ = await execute_tool(
                "write_file",
                {"path": "backend/app/main.py", "content": "print('exploit')"},
                "sess_1",
                guardrail_ctx=ctx,
            )
            assert status == "error"
            assert "EGM Guardrail Violation: Phases 1-4 restrict writes" in output
            assert mock_write.call_count == 0

            # 2. Writing to .buddhi/specs/run_abc/spec.md should succeed
            status, output, exit_code, _ = await execute_tool(
                "write_file",
                {"path": ".buddhi/specs/run_abc/spec.md", "content": "# Spec"},
                "sess_1",
                guardrail_ctx=ctx,
            )
            assert status == "completed"
            assert mock_write.call_count == 1

            # 3. Path traversal should fail
            status, output, exit_code, _ = await execute_tool(
                "write_file",
                {"path": "../../etc/passwd", "content": "hacked"},
                "sess_1",
                guardrail_ctx=ctx,
            )
            assert status == "error"
            assert "EGM Path Validation Error" in output

            # 4. Mutating command pre-approval should be blocked
            status, output, exit_code, _ = await execute_tool(
                "run_command",
                {"command": "echo 'hack' > file.txt"},
                "sess_1",
                guardrail_ctx=ctx,
            )
            assert status == "error"
            assert "EGM Guardrail Violation" in output

        finally:
            sandbox_service.write_session_file = orig_write

    asyncio.run(_run())


def test_egm_guardrails_phase5_scope():
    async def _run():
        mock_write = AsyncMock(return_value=True)
        orig_write = sandbox_service.write_session_file
        sandbox_service.write_session_file = mock_write

        try:
            # Post-approval context (Phase 5 act)
            ctx = ToolGuardrailContext(
                is_egm_mode=True,
                run_id="run_abc",
                egm_phase="act",
                spec_approved=True,
                target_scope_files=("src/app/page.tsx", "src/components/button.tsx"),
            )

            # 1. Out-of-boundary file write fails
            status, output, exit_code, _ = await execute_tool(
                "write_file",
                {"path": "backend/app/database.py", "content": "mutated"},
                "sess_1",
                guardrail_ctx=ctx,
            )
            assert status == "error"
            assert "EGM Boundary Violation" in output

            # 2. Approved file write succeeds
            status, output, exit_code, _ = await execute_tool(
                "write_file",
                {"path": "src/components/button.tsx", "content": "export function Button() {}"},
                "sess_1",
                guardrail_ctx=ctx,
            )
            assert status == "completed"

        finally:
            sandbox_service.write_session_file = orig_write

    asyncio.run(_run())
