from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.agent.harness.calibrator import HarnessCalibrator
from app.services.agent.harness.models import (
    HarnessComponents,
    HarnessOverlay,
    OverlayDiff,
    ProbeResult,
)
from app.services.agent.harness.storage import HarnessStorageService


@pytest.mark.asyncio
async def test_compose_stateless_zero_context_and_boundary_rejection(tmp_path: Path) -> None:
    store = HarnessStorageService(db_path=str(tmp_path / "harness.duckdb"), mirror_root=tmp_path / "mirror")
    calibrator = HarnessCalibrator(storage=store, sandbox_svc=MagicMock())

    captured_messages = []

    async def _fake_stream(messages, **kwargs):
        captured_messages.append(messages)
        yield type(
            "Delta",
            (),
            {"reasoning": "", "content": json.dumps({"winner_id": "cand_clean", "reason": "Higher pass rate"})},
        )()

    baseline = HarnessOverlay(
        version_id="v_base",
        workspace_id="ws_cmp",
        components=HarnessComponents(guardrails="Never bypass OpenSandbox."),
    )
    cand_clean = HarnessOverlay(
        version_id="v_clean",
        workspace_id="ws_cmp",
        components=HarnessComponents(guardrails="Never bypass OpenSandbox.", tool_guidance="Use pytest -q."),
    )
    diffs = [OverlayDiff(candidate_id="cand_clean", updates={"tool_guidance": "Use pytest -q."})]
    probes = [
        ProbeResult(
            probe_id="p1",
            candidate_id="cand_clean",
            target_components=["tool_guidance"],
            status="passed",
            steps_taken=2,
            tool_error_count=0,
            test_pass_rate=1.0,
            wall_clock_ms=120,
            trajectory_summary="status=passed, pass_rate=1.00",
        ),
        ProbeResult(
            probe_id="p2",
            candidate_id="cand_violate",
            target_components=["guardrails"],
            status="guardrail_blocked",
            guardrail_violations=["Attempted boundary relaxation"],
        ),
    ]

    with patch("app.services.agent.harness.calibrator.inference_engine_manager.generate_stream", _fake_stream):
        report, adopted = await calibrator.compose(
            workspace_id="ws_cmp",
            run_id="run_cmp",
            calibration_id="cal_cmp",
            round_num=1,
            trigger_reason="retry",
            task_prompt="Fix tests",
            baseline_overlay=baseline,
            baseline_score=0.0,
            diffs=diffs,
            probe_results=probes,
            candidate_overlays={"cand_clean": cand_clean},
        )

    assert report.status == "adopted"
    assert report.winning_candidate_id == "cand_clean"
    assert adopted is not None
    # Stateless zero-context check: exactly 2 messages [system, user], no Elephant chat history
    assert len(captured_messages) == 1
    assert len(captured_messages[0]) == 2
    assert "zero-context" in captured_messages[0][0].content.lower()


@pytest.mark.asyncio
async def test_compose_returns_no_improvement_on_tie_or_worse(tmp_path: Path) -> None:
    store = HarnessStorageService(db_path=str(tmp_path / "harness.duckdb"), mirror_root=tmp_path / "mirror")
    calibrator = HarnessCalibrator(storage=store, sandbox_svc=MagicMock())

    async def _fake_stream(messages, **kwargs):
        yield type("Delta", (), {"reasoning": "", "content": '{"winner_id": null, "reason": "No gain"}'})()

    probes = [
        ProbeResult(
            probe_id="p1",
            candidate_id="cand_tie",
            target_components=["tool_guidance"],
            status="passed",
            steps_taken=4,
            tool_error_count=1,
            test_pass_rate=0.5,
            wall_clock_ms=200,
            trajectory_summary="status=passed, pass_rate=0.50",
        )
    ]
    with patch("app.services.agent.harness.calibrator.inference_engine_manager.generate_stream", _fake_stream):
        report, adopted = await calibrator.compose(
            workspace_id="ws_tie",
            run_id="run_tie",
            calibration_id="cal_tie",
            round_num=1,
            trigger_reason="retry",
            task_prompt="Fix tests",
            baseline_overlay=None,
            baseline_score=0.5,
            diffs=[OverlayDiff(candidate_id="cand_tie", updates={"tool_guidance": "x"})],
            probe_results=probes,
            candidate_overlays={},
        )

    assert report.status == "no_improvement"
    assert adopted is None
