from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.agent.harness.models import HarnessComponents, HarnessOverlay
from app.services.agent.harness.storage import HarnessStorageService
from app.services.agent.harness.calibrator import HarnessCalibrator
from app.services.agent.nodes import rlm_run_node
from app.services.rlm.budget import RlmBudgetTelemetry
from app.services.rlm.runner import RlmExecutionResult


@pytest.mark.asyncio
async def test_propose_delegates_oversized_trace_to_rlm(tmp_path: Path) -> None:
    store = HarnessStorageService(db_path=str(tmp_path / "harness.duckdb"), mirror_root=tmp_path / "mirror")
    mock_sb = MagicMock()
    calibrator = HarnessCalibrator(storage=store, sandbox_svc=mock_sb)

    oversized_trace = "ERROR: tool failed at line X\n" * 4000  # > 100k chars (~25k+ tokens > 16k window)
    seen_prompt_lengths: list[int] = []

    async def _fake_stream(messages, **kwargs):
        total_chars = sum(len(str(m.content)) for m in messages)
        seen_prompt_lengths.append(total_chars)
        yield type(
            "Delta",
            (),
            {
                "reasoning": "",
                "content": '[{"candidate_id": "c1", "rationale": "rlm", "updates": {"tool_guidance": "Use grep_repo first."}}]',
            },
        )()

    mock_rlm_run = AsyncMock(
        return_value=RlmExecutionResult(
            status="completed",
            final_answer="Root cause: missing pytest -q flag.",
            telemetry=RlmBudgetTelemetry(
                subcall_count=1,
                max_depth_reached=1,
                total_input_tokens=100,
                total_output_tokens=50,
                total_tokens=150,
                elapsed_seconds=0.1,
            ),
            steps_taken=2,
        )
    )

    with patch("app.services.agent.harness.calibrator.inference_engine_manager.generate_stream", _fake_stream), patch(
        "app.services.rlm.runner.RlmTaskRunner.run", mock_rlm_run
    ):
        diffs, rejected, rlm_used = await calibrator.propose(
            workspace_id="ws_rlm",
            task_prompt="Fix failing tests",
            observations=[],
            trace_text=oversized_trace,
            max_candidates=1,
        )

    assert rlm_used is True
    assert mock_rlm_run.await_count == 1
    assert len(diffs) == 1
    assert rejected == 0
    # Ensure no single LLM call in Propose exceeded 16k * 4 chars
    assert all(length < 16384 * 4 for length in seen_prompt_lengths)


@pytest.mark.asyncio
async def test_rlm_run_mounts_overlay_scripts_and_guidance() -> None:
    overlay = HarnessOverlay(
        version_id="hov_rlm1",
        workspace_id="ws_rlm",
        components=HarnessComponents(
            tool_guidance="Use chunk_file with overlap_chars=100.",
            skills={"ast": "Prefer AST slicing for Python."},
            scripts={"custom_grep.py": "def fast_grep(): return []\n"},
        ),
    )

    mock_sb = MagicMock()
    mock_sb.create_session = AsyncMock(return_value=MagicMock(session_id="rlm_sb_1"))
    mock_sb.write_session_file = AsyncMock(return_value=None)
    mock_sb.terminate_session = AsyncMock(return_value=None)

    captured_prompts: list[str] = []

    async def _fake_root_gen(messages):
        captured_prompts.append(str(messages[0].content))
        return "FINAL_ANSWER: Done with custom_grep."

    from app.services.rlm.runner import RlmTaskRunner

    runner = RlmTaskRunner(sandbox_svc=mock_sb, generate_fn=_fake_root_gen)
    with patch("app.services.rlm.runner.RlmTaskRunner._default_root_generate", _fake_root_gen):
        res = await runner.run(
            task_prompt="Inspect repo",
            harness_overlay=overlay.model_dump(mode="json"),
        )

    assert res.status == "completed"
    assert "Use chunk_file with overlap_chars=100." in captured_prompts[0]
    assert "Prefer AST slicing for Python." in captured_prompts[0]
    written_paths = [call.args[1] for call in mock_sb.write_session_file.await_args_list]
    assert ".buddhi/harness/scripts/custom_grep.py" in written_paths
