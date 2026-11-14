import asyncio
import sys
import pytest
from unittest.mock import AsyncMock

from app.schemas.sandbox import SandboxExecutionResult
from app.services.agent.egm.nodes import goldfish_verify_node
from app.services.agent.egm.runner import GoldfishRunner, GoldfishVerifyInput
from app.services.agent.nodes import parse_review_verdict
from app.services.agent.state import AgentState
from app.services.sandbox_service import sandbox_service

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def test_strict_verdict_parsing():
    # Strict mode forces 'retry' when no explicit VERDICT line matches
    assert parse_review_verdict("Looks good, tests pass!", strict=True) == "retry"
    assert parse_review_verdict("Everything is broken", strict=True) == "retry"

    # Strict mode accepts explicit VERDICT tokens
    assert parse_review_verdict("Analysis complete.\nVERDICT: pass\nReady to merge.", strict=True) == "pass"
    assert parse_review_verdict("Analysis complete.\nVERDICT: retry\nFix errors.", strict=True) == "retry"
    assert parse_review_verdict("VERDICT: continue", strict=True) == "continue"

    # Default legacy mode defaults to 'pass' for backwards compatibility
    assert parse_review_verdict("Looks good, tests pass!", strict=False) == "pass"


def test_goldfish_verifier_zero_context_prompt():
    runner = GoldfishRunner(concurrency=1)
    inp = GoldfishVerifyInput(
        spec_contract="# Spec\nApproved scope: src/button.tsx",
        git_diff="diff --git a/src/button.tsx b/src/button.tsx",
        test_output="1 passed in 0.05s",
        target_scope_files=("src/button.tsx",),
    )
    msgs = runner.build_verify_messages(inp)
    assert len(msgs) == 2
    assert msgs[0].role == "system"
    assert msgs[1].role == "user"
    assert "Zero-Context Goldfish Implementation Verifier" in msgs[0].content
    assert "src/button.tsx" in msgs[1].content


@pytest.mark.asyncio
async def test_goldfish_verify_fail_closed_on_missing_session():
    # If session is None, verifier fails closed to retry
    state: AgentState = {"run_id": "run_1", "session_id": None}
    res = await goldfish_verify_node(state)
    assert res.get("verdict") == "retry"
    assert "no active sandbox session" in res.get("error", "")


@pytest.mark.asyncio
async def test_goldfish_verify_out_of_boundary_diff():
    # Out of boundary files in git status must trigger retry and citation
    mock_exec = AsyncMock()

    def side_effect(session_id, req):
        if "git diff" in req.code:
            return SandboxExecutionResult(status="completed", stdout="diff ...", stderr="", exit_code=0, execution_time_ms=5)
        elif "git status" in req.code:
            return SandboxExecutionResult(
                status="completed",
                stdout=" M src/button.tsx\n M backend/app/exploit.py\n",
                stderr="",
                exit_code=0,
                execution_time_ms=5,
            )
        return SandboxExecutionResult(status="completed", stdout="tests pass", stderr="", exit_code=0, execution_time_ms=5)

    mock_exec.side_effect = side_effect
    orig_exec = sandbox_service.execute_in_session
    sandbox_service.execute_in_session = mock_exec

    try:
        state: AgentState = {
            "run_id": "run_1",
            "session_id": "sess_1",
            "spec_contract": {"target_scope_files": ["src/button.tsx"]},
        }
        res = await goldfish_verify_node(state)
        assert res.get("verdict") == "retry"
        assert "backend/app/exploit.py" in res.get("error", "")
    finally:
        sandbox_service.execute_in_session = orig_exec
