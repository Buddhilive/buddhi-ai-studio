from app.schemas.chat import FunctionCall, ToolCall
from app.services.agent.routing import (
    compute_action_hash,
    is_repeated_action,
    route_after_act,
    route_after_analyze,
    route_after_observe,
    route_after_review,
)
from app.services.agent.state import AgentState


def test_action_hash_and_repeat_detection():
    h1 = compute_action_hash("run_command", {"command": "ls"})
    h2 = compute_action_hash("run_command", {"command": "ls"})
    h3 = compute_action_hash("run_command", {"command": "pwd"})
    assert h1 == h2
    assert h1 != h3

    assert not is_repeated_action([h1, h2])
    assert is_repeated_action([h1, h1, h1])
    assert is_repeated_action([h3, h1, h1, h1])
    assert not is_repeated_action([h1, h1, h3])


def test_route_after_analyze():
    state: AgentState = {"status": "running"}
    assert route_after_analyze(state) == "plan"

    state = {"status": "failed"}
    assert route_after_analyze(state) == "end"

    state = {"status": "running", "is_rlm_mode": True}
    assert route_after_analyze(state) == "rlm_run"


def test_route_after_act():
    # No tool calls -> goes to review
    state: AgentState = {"status": "running", "pending_tool_calls": []}
    assert route_after_act(state) == "review"

    # Tool call present -> goes to observe
    tc = ToolCall(function=FunctionCall(name="run_command", arguments='{"command": "pytest"}'))
    state = {"status": "running", "pending_tool_calls": [tc], "recent_actions": []}
    assert route_after_act(state) == "observe"

    # Repeat action threshold triggered -> routes to review
    h = compute_action_hash("run_command", '{"command": "pytest"}')
    state["recent_actions"] = [h, h, h]
    assert route_after_act(state) == "review"


def test_egm_routing():
    # EGM mode on -> routes to draft
    state: AgentState = {"status": "running", "is_egm_mode": True, "egm_skill_mode": "standard"}
    assert route_after_analyze(state) == "draft"

    # Brainstorm mode -> routes to brainstorm
    state = {"status": "running", "is_egm_mode": True, "egm_skill_mode": "brainstorm"}
    assert route_after_analyze(state) == "brainstorm"

    # Drift report mode -> routes to drift_report
    state = {"status": "running", "is_egm_mode": True, "egm_skill_mode": "drift_report"}
    assert route_after_analyze(state) == "drift_report"

    # Act routes to goldfish_verify in EGM mode
    state = {"status": "running", "is_egm_mode": True, "pending_tool_calls": []}
    assert route_after_act(state) == "goldfish_verify"

    # Observe routes to goldfish_verify in EGM mode
    assert route_after_observe(state) == "goldfish_verify"

    # Default mode regression check
    state_default: AgentState = {"status": "running", "is_egm_mode": False, "pending_tool_calls": []}
    assert route_after_act(state_default) == "review"
    assert route_after_observe(state_default) == "review"


def test_route_after_observe():
    state: AgentState = {"status": "running"}
    assert route_after_observe(state) == "review"

    state = {"status": "cancelled"}
    assert route_after_observe(state) == "end"


def test_route_after_review():
    # Normal verdicts
    state: AgentState = {"step": 1, "max_steps": 10, "verdict": "pass", "status": "running"}
    assert route_after_review(state) == "end"

    state = {"step": 1, "max_steps": 10, "verdict": "continue", "status": "running"}
    assert route_after_review(state) == "act"

    state = {"step": 1, "max_steps": 10, "verdict": "retry", "status": "running"}
    assert route_after_review(state) == "plan"

    # Max steps budget exhausted
    state = {"step": 10, "max_steps": 10, "verdict": "continue", "status": "running"}
    assert route_after_review(state) == "end"
