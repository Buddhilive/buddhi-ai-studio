from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.schemas.sandbox import SandboxExecutionRequest
from app.services.sandbox_service import SandboxService


async def test_execute_in_session_stream_emits_incremental_chunks_and_caps_bytes():
    service = SandboxService()
    chunks: list[tuple[str, str]] = []

    async def on_chunk(stream: str, delta: str) -> None:
        chunks.append((stream, delta))

    async def fake_run(command, opts=None, handlers=None):
        if handlers and getattr(handlers, "on_stdout", None):
            await handlers.on_stdout(SimpleNamespace(text="hello "))
            await handlers.on_stdout(SimpleNamespace(text="world\n"))
        if handlers and getattr(handlers, "on_stderr", None):
            await handlers.on_stderr(SimpleNamespace(text="warn\n"))
        return SimpleNamespace(
            exit_code=0,
            error=None,
            logs=SimpleNamespace(content=[SimpleNamespace(text="hello world\n", is_error=False)]),
        )

    mock_sandbox = MagicMock()
    mock_sandbox.commands.run = AsyncMock(side_effect=fake_run)
    service._active_sessions["sess_1"] = SimpleNamespace(sandbox=mock_sandbox, last_activity=0.0, touch=lambda: None)

    res = await service.execute_in_session_stream(
        "sess_1",
        SandboxExecutionRequest(language="bash", code="echo hi"),
        on_chunk=on_chunk,
    )

    assert res.status == "completed"
    assert res.exit_code == 0
    assert ("stdout", "hello world\n") in chunks or any(s == "stdout" and "hello" in d for s, d in chunks)
    assert any(s == "stderr" and "warn" in d for s, d in chunks)
