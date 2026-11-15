from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.chat import ChatMessage
from app.schemas.sandbox import SandboxExecutionResult
from app.services.agent.harness.models import default_vibe_harness_components
from app.services.agent.prompts import build_act_messages, build_analyze_messages, build_plan_messages
from app.services.agent.skill_loader import VIBE_SKILL_NAMES
from app.services.agent.tools import ToolGuardrailContext, execute_tool


def test_seven_official_skills_exist_and_registered() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    skills_dir = repo_root / ".agents" / "skills"
    components = default_vibe_harness_components()

    for skill_name in VIBE_SKILL_NAMES:
        skill_path = skills_dir / skill_name / "SKILL.md"
        assert skill_path.exists(), f"Missing skill file: {skill_path}"
        text = skill_path.read_text(encoding="utf-8")
        assert text.startswith("---"), f"Missing YAML frontmatter in {skill_path}"
        assert f"name: {skill_name}" in text
        assert skill_name in components.skills


def test_selective_skill_loading_stays_within_token_budget() -> None:
    user_msgs = [ChatMessage(role="user", content="Add BetterAuth login dialog with shadcn and Drizzle")]
    analyze_msgs = build_analyze_messages(user_msgs)
    plan_msgs = build_plan_messages(user_msgs, "1. Configure BetterAuth\n2. Build login dialog")
    act_msgs = build_act_messages(user_msgs, [], [])

    for msgs in (analyze_msgs, plan_msgs, act_msgs):
        sys_content = msgs[0].content
        assert "better-auth" in sys_content
        assert "load_skill" in sys_content
        # Ensure we didn't dump all 7 full skills (>12k tokens)
        assert len(sys_content) < 20000


@pytest.mark.asyncio
async def test_load_skill_tool() -> None:
    status, out, code, _ = await execute_tool(
        "load_skill",
        {"skill_name": "drizzle-orm"},
        session_id="sess_1",
    )
    assert status == "completed"
    assert code == 0
    assert "Drizzle ORM Runbook" in out

    s2, o2, c2, _ = await execute_tool(
        "load_skill",
        {"skill_name": "nonexistent-skill"},
        session_id="sess_1",
    )
    assert s2 == "error"
    assert c2 == 1
    assert "Valid skills:" in o2


@pytest.mark.asyncio
async def test_nextjs_devtools_mcp_and_tsc_fallback() -> None:
    mcp_res = SandboxExecutionResult(
        status="completed",
        stdout='{"jsonrpc":"2.0","id":1,"result":{"tools":[{"name":"get_errors"}]}}',
        stderr="",
        exit_code=0,
        execution_time_ms=10.0,
    )
    with patch("app.services.agent.vibe_tools.sandbox_service.execute_in_session", new=AsyncMock(return_value=mcp_res)):
        status, out, code, _ = await execute_tool("nextjs_devtools", {"action": "diagnostics"}, session_id="sess_1")
    assert status == "completed"
    assert code == 0
    assert "get_errors" in out

    # Offline dev server -> falls back to next typegen && tsc --noEmit
    empty_probe = SandboxExecutionResult(status="completed", stdout="", stderr="", exit_code=0, execution_time_ms=5.0)
    tsc_ok = SandboxExecutionResult(status="completed", stdout="Typecheck clean", stderr="", exit_code=0, execution_time_ms=30.0)
    with patch(
        "app.services.agent.vibe_tools.sandbox_service.execute_in_session",
        new=AsyncMock(side_effect=[empty_probe, tsc_ok]),
    ) as mock_exec:
        s2, o2, c2, _ = await execute_tool("nextjs_devtools", {"action": "diagnostics"}, session_id="sess_1")
    assert s2 == "completed"
    assert c2 == 0
    assert "tsc --noEmit" in mock_exec.call_args_list[1].args[1].code


@pytest.mark.asyncio
async def test_shadcn_registry_and_better_auth_cli() -> None:
    ok_res = SandboxExecutionResult(status="completed", stdout="Done", stderr="", exit_code=0, execution_time_ms=12.0)
    with patch("app.services.agent.vibe_tools.sandbox_service.execute_in_session", new=AsyncMock(return_value=ok_res)) as mock_exec:
        status, _, code, _ = await execute_tool(
            "shadcn_registry",
            {"action": "add", "components": ["dialog", "table"]},
            session_id="sess_1",
            guardrail_ctx=ToolGuardrailContext(workspace_id="ws_1", spec_approved=True),
        )
        assert status == "completed"
        assert code == 0
        assert "shadcn@latest add dialog table --yes" in mock_exec.call_args.args[1].code

    # Injection attempt rejected
    s_bad, o_bad, c_bad, _ = await execute_tool(
        "shadcn_registry",
        {"action": "add", "components": ["dialog; rm -rf /"]},
        session_id="sess_1",
    )
    assert s_bad == "error"
    assert c_bad == 1
    assert "Invalid component name" in o_bad

    with patch("app.services.agent.vibe_tools.sandbox_service.execute_in_session", new=AsyncMock(return_value=ok_res)):
        s_ba, _, c_ba, _ = await execute_tool(
            "better_auth_cli",
            {"action": "generate"},
            session_id="sess_1",
            guardrail_ctx=ToolGuardrailContext(workspace_id="ws_1", spec_approved=True),
        )
    assert s_ba == "completed"
    assert c_ba == 0
