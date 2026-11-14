from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.agent import Finding, SpecContract
from app.schemas.chat import ChatMessage
from app.schemas.sandbox import SandboxExecutionResult
from app.services.agent.egm.nodes import brainstorm_node, drift_report_node
from app.services.agent.egm.runner import ReviewerOutput
from app.services.agent.routing import route_after_analyze
from app.services.agent.state import AgentState


@pytest.mark.asyncio
async def test_brainstorm_7_lenses_aggregation():
    state: AgentState = {
        "run_id": "test_run_brainstorm",
        "session_id": "sess-test-brainstorm",
        "is_egm_mode": True,
        "egm_skill_mode": "brainstorm",
        "messages": [ChatMessage(role="user", content="Build an AI autonomous factory.")],
        "egm_artifacts": {},
    }

    mock_emitter = AsyncMock()

    # Mock runner outputs for all 7 lenses, with 1 injected retry
    def mock_run_single(inp, stage="brainstorm", **kwargs):
        is_retried = inp.persona_id == "structural"
        return ReviewerOutput(
            persona=inp.persona_id,
            stage=stage,
            status="completed",
            raw_content=f"## Review from {inp.persona_id}\n\n- [BLOCKER] Critical gap in {inp.persona_id}",
            findings=[
                Finding(
                    lens=inp.persona_id,
                    severity="blocker" if is_retried else "major",
                    scope=f"concept-{inp.persona_id}",
                    description=f"Analysis from {inp.persona_id}",
                    recommendation=f"Refine {inp.persona_id}",
                )
            ],
            retried=is_retried,
        )

    with patch("app.services.agent.egm.nodes.GoldfishRunner") as MockRunnerCls, \
         patch("app.services.agent.egm.nodes.sync_egm_artifact_to_sandbox", new_callable=AsyncMock) as mock_sync:
        mock_runner_inst = MagicMock()
        mock_runner_inst.run_single_reviewer = AsyncMock(side_effect=mock_run_single)
        MockRunnerCls.return_value = mock_runner_inst

        result = await brainstorm_node(state, emitter=mock_emitter)

        # Assert all 7 lenses were called
        assert mock_runner_inst.run_single_reviewer.call_count == 7
        assert result["egm_phase"] == "brainstorm"
        assert "concepts_brief" in result
        assert "concepts_brief.md" in mock_sync.call_args[0][1]

        # Check telemetry events
        mock_emitter.emit_node_start.assert_called_with("brainstorm")
        mock_emitter.emit_egm_phase.assert_called_with("brainstorm")
        assert mock_emitter.emit_reviewer_status.call_count == 14  # running + completed for each of 7 lenses
        mock_emitter.emit_artifact.assert_called_once()
        mock_emitter.emit_node_end.assert_called_once_with("brainstorm", {"lenses_count": 7})


@pytest.mark.asyncio
async def test_drift_report_node_divergence_detection():
    spec_contract = SpecContract(
        path="spec.md",
        content="## Target Scope & File Boundary\n- `backend/app/main.py`\n",
        target_scope_files=["backend/app/main.py"],
        approved=True,
    )

    state: AgentState = {
        "run_id": "test_run_drift",
        "session_id": "sess-test-drift",
        "is_egm_mode": True,
        "egm_skill_mode": "drift_report",
        "spec_contract": spec_contract,
        "egm_artifacts": {},
    }

    mock_emitter = AsyncMock()

    # Seeded git status with an authorized modification and an out-of-boundary drift
    git_stdout = (
        " M backend/app/main.py\n"
        "?? backend/app/unauthorized.py\n"
        "===DIFF===\n"
        " backend/app/main.py | 5 +++++\n"
        " 1 file changed, 5 insertions(+)\n"
    )

    mock_sandbox_res = SandboxExecutionResult(
        stdout=git_stdout,
        stderr="",
        exit_code=0,
        timed_out=False,
        status="completed",
        execution_time_ms=10.0,
    )

    with patch("app.services.agent.egm.nodes.rehydrate_egm_sandbox_if_needed", new_callable=AsyncMock, return_value="sess-test-drift"), \
         patch("app.services.agent.egm.nodes.sandbox_service.execute_in_session", new_callable=AsyncMock, return_value=mock_sandbox_res), \
         patch("app.services.agent.egm.nodes.sync_egm_artifact_to_sandbox", new_callable=AsyncMock) as mock_sync:

        result = await drift_report_node(state, emitter=mock_emitter)

        assert result["egm_phase"] == "drift_report"
        drift_report = result["drift_report"]
        assert "EGM Spec-to-Codebase Drift Report" in drift_report
        assert "[BLOCKER DRIFT]" in drift_report
        assert "backend/app/unauthorized.py" in drift_report
        assert "backend/app/main.py" not in drift_report or "Boundary Conformance" in drift_report or "Target Scope Files Declared" in drift_report

        mock_sync.assert_called_once()
        assert mock_sync.call_args[0][1] == "drift_report.md"
        mock_emitter.emit_node_start.assert_called_once_with("drift_report")
        mock_emitter.emit_artifact.assert_called_once()
        mock_emitter.emit_node_end.assert_called_once_with("drift_report", {
            "unauthorized_count": 1,
            "unmodified_count": 0,
        })


def test_egm_skill_mode_routing():
    # Test brainstorm routing
    state_brainstorm: AgentState = {
        "is_egm_mode": True,
        "egm_skill_mode": "brainstorm",
    }
    assert route_after_analyze(state_brainstorm) == "brainstorm"

    # Test drift report routing
    state_drift: AgentState = {
        "is_egm_mode": True,
        "egm_skill_mode": "drift_report",
    }
    assert route_after_analyze(state_drift) == "drift_report"

    # Test bootstrap routing
    state_bootstrap: AgentState = {
        "is_egm_mode": True,
        "egm_skill_mode": "bootstrap",
    }
    assert route_after_analyze(state_bootstrap) == "rlm_run"

    # Test standard EGM mode routing
    state_standard: AgentState = {
        "is_egm_mode": True,
        "egm_skill_mode": "standard",
    }
    assert route_after_analyze(state_standard) == "draft"
