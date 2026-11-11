from __future__ import annotations

import sys
from typing import AsyncGenerator
from unittest.mock import AsyncMock

from app.schemas.chat import ChatCompletionChunkDelta
from app.schemas.sandbox import SandboxExecutionResult, SandboxSessionResponse


class ScriptedInferenceEngine:
    """Mock engine that produces deterministic output sequences for testing."""

    def __init__(self) -> None:
        self.call_count = 0

    async def generate_stream(
        self,
        messages: list[Any],
        max_tokens: int | None = None,
        enable_thinking: bool = False,
        model_id: str | None = None,
        tools: list[Any] | None = None,
    ) -> AsyncGenerator[DeltaChunk, None]:
        self.call_count += 1
        prompt = " ".join(str(m.content) for m in messages if hasattr(m, "content"))

        if "PHASE: ANALYZE" in prompt:
            text = "Analysis: The goal is to create and execute hello.py."
        elif "PHASE: PLAN" in prompt:
            text = "1. Write hello.py script\n2. Run hello.py in sandbox\n3. Verify output"
        elif "PHASE: ACT" in prompt:
            if "hello.py" not in prompt:
                text = '<|tool_call>call:write_file{"path": "hello.py", "content": "print(\'hello world\')"}<tool_call|>'
            elif "print('hello world')" in prompt and "hello world" not in prompt:
                text = '<|tool_call>call:run_command{"command": "python hello.py"}<tool_call|>'
            else:
                text = "File was created and executed successfully."
        elif "PHASE: REVIEW" in prompt:
            text = "Review: Objective verified.\nVERDICT: pass"
        else:
            text = "Standard response."

        # Yield as chunks
        yield ChatCompletionChunkDelta(reasoning="Thinking about step...")
        yield ChatCompletionChunkDelta(content=text)


from datetime import datetime, timezone

def create_mock_sandbox():
    now = datetime.now(timezone.utc)
    mock_sb = AsyncMock()
    mock_sb.create_session = AsyncMock(
        return_value=SandboxSessionResponse(
            session_id="test_sess_1",
            runtime_image="python:3.11-slim",
            status="running",
            created_at=now,
            last_activity_at=now,
            expires_at=now,
            allow_network=False,
        )
    )
    mock_sb.get_session = AsyncMock(return_value=None)
    mock_sb.write_session_file = AsyncMock(return_value=True)
    mock_sb.read_session_file = AsyncMock(return_value="print('hello world')")
    mock_sb.execute_in_session = AsyncMock(
        return_value=SandboxExecutionResult(
            status="completed",
            stdout="hello world\n",
            stderr="",
            exit_code=0,
            execution_time_ms=12.0,
        )
    )
    mock_sb.terminate_session = AsyncMock(return_value=True)
    return mock_sb
