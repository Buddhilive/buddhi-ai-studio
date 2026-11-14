from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.chat import ChatMessage
from app.services.agent.egm.nodes import drift_report_node, goldfish_review_node, goldfish_verify_node
from app.services.agent.harness.models import HarnessComponents, HarnessOverlay
from app.services.agent.prompts import build_act_messages, build_draft_messages


@pytest.mark.asyncio
async def test_goldfish_review_and_verify_remain_isolated_from_overlay() -> None:
    sentinel_guidance = "SENTINEL_ELEPHANT_ONLY_GUIDANCE_XYZ"
    sentinel_exp = "SENTINEL_EXPERIENCE_LESSON_ABC"

    overlay_dict = HarnessOverlay(
        version_id="hov_iso",
        workspace_id="ws_iso",
        components=HarnessComponents(tool_guidance=sentinel_guidance),
    ).model_dump(mode="json")
    experiences = [{"task_signature": "t1", "lesson": sentinel_exp}]

    # Elephant prompts MUST receive the sentinels
    draft_msgs = build_draft_messages(
        [ChatMessage(role="user", content="Build feature")],
        harness_overlay=overlay_dict,
        harness_experiences=experiences,
    )
    act_msgs = build_act_messages(
        [ChatMessage(role="user", content="Build feature")],
        plan=[],
        observations=[],
        harness_overlay=overlay_dict,
        harness_experiences=experiences,
    )
    assert sentinel_guidance in draft_msgs[0].content
    assert sentinel_exp in act_msgs[0].content

    # Goldfish prompts MUST NEVER receive the sentinels
    captured_goldfish_prompts: list[str] = []

    async def _fake_goldfish_stream(messages, **kwargs):
        captured_goldfish_prompts.append("\n".join(str(m.content) for m in messages))
        yield type("Delta", (), {"reasoning": "", "content": "VERDICT: pass\nAll clean."})()

    mock_sb = MagicMock()
    mock_sb.execute_in_session = AsyncMock(return_value=MagicMock(stdout="", stderr="", exit_code=0))

    with patch("app.services.inference_service.inference_engine_manager.generate_stream", _fake_goldfish_stream), patch(
        "app.services.agent.egm.nodes.sandbox_service", mock_sb
    ), patch("app.services.agent.egm.nodes.sync_egm_artifact_to_sandbox", AsyncMock(return_value="report.md")):
        state = {
            "run_id": "run_iso",
            "session_id": "sb_iso",
            "is_egm_mode": True,
            "egm_round": 1,
            "egm_max_rounds": 3,
            "spec_contract": {"path": "spec.md", "content": "## Overview\nTest", "target_scope_files": ["a.py"]},
            "allowed_write_paths": ["a.py"],
            "harness_overlay": overlay_dict,
            "harness_experiences": experiences,
            "observations": [],
        }
        await goldfish_review_node(state)
        await goldfish_verify_node(state)

    assert len(captured_goldfish_prompts) >= 2
    for prompt_text in captured_goldfish_prompts:
        assert sentinel_guidance not in prompt_text
        assert sentinel_exp not in prompt_text


@pytest.mark.asyncio
async def test_drift_report_includes_harness_calibration_summary() -> None:
    mock_sb = MagicMock()
    mock_sb.execute_in_session = AsyncMock(return_value=MagicMock(stdout=" M a.py\n===DIFF===\n a.py | 2 +-", stderr="", exit_code=0))

    with patch("app.services.agent.egm.nodes.rehydrate_egm_sandbox_if_needed", AsyncMock(return_value="sb_1")), patch(
        "app.services.agent.egm.nodes.sandbox_service", mock_sb
    ), patch("app.services.agent.egm.nodes.sync_egm_artifact_to_sandbox", AsyncMock(return_value="drift_report.md")):
        res = await drift_report_node(
            {
                "run_id": "run_dr",
                "session_id": "sb_1",
                "spec_contract": {"path": "spec.md", "target_scope_files": ["a.py"]},
                "egm_artifacts": {
                    "harness_calibration_report": '{"status": "adopted", "adopted_components": ["tool_guidance"]}'
                },
            }
        )

    assert "Harness2 Calibration Adaptations" in res["drift_report"]
    assert "tool_guidance" in res["drift_report"]
