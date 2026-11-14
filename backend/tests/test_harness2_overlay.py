from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.agent.harness.models import (
    HARNESS_COMPONENT_KEYS,
    HarnessComponents,
    HarnessOverlay,
)
from app.services.agent.harness.storage import HarnessStorageService
from app.services.agent.nodes import analyze_node
from app.services.agent.prompts import build_act_messages, build_analyze_messages, build_plan_messages
from app.schemas.chat import ChatMessage


def test_harness_overlay_8_components_round_trip_and_rollback(tmp_path: Path) -> None:
    db_file = str(tmp_path / "harness.duckdb")
    mirror = tmp_path / ".buddhi" / "harness"
    store = HarnessStorageService(db_path=db_file, mirror_root=mirror)

    v1 = HarnessOverlay(
        version_id="v1_base",
        workspace_id="repo_alpha",
        components=HarnessComponents(
            system_prompt="Base system guidance.",
            guardrails="Never touch .env.",
            memory="Use pytest -q.",
            tool_guidance="Prefer read_file with line ranges.",
            subagents="Use testing-specialist for test plans.",
            skills={"python": "Run ruff before pytest."},
            scripts={"check.py": "print('ok')"},
            plugins=[{"name": "rtk", "kind": "hook", "enabled": True}],
        ),
    )
    assert set(v1.components.model_dump().keys()) == set(HARNESS_COMPONENT_KEYS)
    store.save_overlay_snapshot(v1, activate=True)

    v2 = HarnessOverlay(
        version_id="v2_tuned",
        workspace_id="repo_alpha",
        parent_version_id="v1_base",
        components=HarnessComponents(
            system_prompt="Tuned system guidance.",
            guardrails="Never touch .env.",
            tool_guidance="Always pass -x to pytest.",
        ),
    )
    store.save_overlay_snapshot(v2, activate=True)
    active = store.get_active_overlay("repo_alpha")
    assert active is not None
    assert active.version_id == "v2_tuned"
    assert (mirror / "repo_alpha" / "overlay.json").exists()

    restored = store.rollback_overlay("repo_alpha", "v1_base")
    assert restored.version_id == "v1_base"
    assert store.get_active_overlay("repo_alpha").version_id == "v1_base"
    assert store.get_active_overlay("repo_alpha").components.skills["python"] == "Run ruff before pytest."


@pytest.mark.asyncio
async def test_level2_overlay_load_under_50ms_and_zero_llm_calls(tmp_path: Path) -> None:
    db_file = str(tmp_path / "harness.duckdb")
    mirror = tmp_path / ".buddhi" / "harness"
    store = HarnessStorageService(db_path=db_file, mirror_root=mirror)

    overlay = HarnessOverlay(
        version_id="v1_fast",
        workspace_id="ws_fast",
        components=HarnessComponents(tool_guidance="SENTINEL_TOOL_GUIDANCE: use uv run pytest"),
    )
    store.save_overlay_snapshot(overlay, activate=True)

    call_count = 0

    async def _fake_stream(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        yield type("Delta", (), {"reasoning": "", "content": "Analysis done."})()

    with patch("app.services.agent.nodes.harness_storage_service", store), patch(
        "app.services.agent.nodes.inference_engine_manager.generate_stream", _fake_stream
    ):
        t0 = time.perf_counter()
        result = await analyze_node(
            {
                "run_id": "run_fast",
                "workspace_id": "ws_fast",
                "harness_mode": "auto",
                "messages": [ChatMessage(role="user", content="Run tests")],
            }
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

    # analyze_node itself does 1 LLM call for analysis; Level 2 overlay loading adds 0 extra calls
    assert call_count == 1
    assert result["harness_overlay"] is not None
    assert result["harness_overlay"]["version_id"] == "v1_fast"
    assert elapsed_ms < 500.0

    t_load = time.perf_counter()
    loaded = await store.aget_active_overlay("ws_fast")
    load_ms = (time.perf_counter() - t_load) * 1000.0
    assert loaded is not None
    assert load_ms < 50.0


@pytest.mark.asyncio
async def test_uncalibrated_workspace_falls_back_cleanly(tmp_path: Path) -> None:
    store = HarnessStorageService(db_path=str(tmp_path / "harness.duckdb"), mirror_root=tmp_path / "mirror")
    assert await store.aget_active_overlay("uncalibrated_ws") is None

    msgs_analyze = build_analyze_messages([ChatMessage(role="user", content="Hi")], harness_overlay=None)
    msgs_plan = build_plan_messages([ChatMessage(role="user", content="Hi")], "analysis", harness_overlay=None)
    msgs_act = build_act_messages([ChatMessage(role="user", content="Hi")], [], [], harness_overlay=None)
    assert "PHASE: ANALYZE" in msgs_analyze[0].content
    assert "PHASE: PLAN" in msgs_plan[0].content
    assert "PHASE: ACT" in msgs_act[0].content
