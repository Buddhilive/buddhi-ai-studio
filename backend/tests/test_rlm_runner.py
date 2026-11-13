from unittest.mock import AsyncMock, MagicMock
from app.schemas.sandbox import SandboxExecutionResult, SandboxSessionResponse
from app.services.rlm.runner import RlmTaskRunner
from datetime import datetime, timezone


def test_rlm_runner_execution_flow():
    mock_sandbox_svc = MagicMock()

    # Mock session create/get/terminate
    mock_active = MagicMock()
    mock_active.sandbox.files = MagicMock()
    mock_active.sandbox.files.write_file = AsyncMock()
    mock_active.sandbox.files.list_directory = AsyncMock(return_value=[])

    session_resp = SandboxSessionResponse(
        session_id="session-test-123",
        runtime_image="python:3.11-slim",
        status="running",
        created_at=datetime.now(timezone.utc),
        last_activity_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
        allow_network=False,
    )
    mock_sandbox_svc.create_session = AsyncMock(return_value=session_resp)
    mock_sandbox_svc.get_session = AsyncMock(return_value=mock_active)
    mock_sandbox_svc.write_session_file = AsyncMock()
    mock_sandbox_svc.terminate_session = AsyncMock(return_value=True)

    # Step 1: Model outputs code
    # Step 2: Model concludes with FINAL_ANSWER
    model_turns = [
        "```python\nimport rlm_helpers\nchunks = rlm_helpers.chunk_file('main.py')\nprint(f'Chunks: {len(chunks)}')\n```",
        "Based on analysis: FINAL_ANSWER: The module handles data ingestion and parsing.",
    ]
    turn_idx = 0

    async def mock_root_gen(history):
        nonlocal turn_idx
        ans = model_turns[turn_idx]
        turn_idx += 1
        return ans

    mock_exec_res = SandboxExecutionResult(
        status="completed",
        stdout="Chunks: 5\n",
        stderr="",
        exit_code=0,
        execution_time_ms=50.0,
    )
    mock_sandbox_svc.execute_in_session = AsyncMock(return_value=mock_exec_res)

    runner = RlmTaskRunner(
        sandbox_svc=mock_sandbox_svc,
        generate_fn=mock_root_gen,
    )

    import asyncio
    result = asyncio.run(runner.run("Analyze the ingestion pipeline"))

    assert result.status == "completed"
    assert "The module handles data ingestion and parsing" in result.final_answer
    assert result.steps_taken == 2
    mock_sandbox_svc.terminate_session.assert_called_once_with("session-test-123")
