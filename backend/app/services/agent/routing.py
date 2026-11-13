from __future__ import annotations

import hashlib
import json
from typing import Literal
from app.services.agent.state import AgentState


def compute_action_hash(tool_name: str, args: dict | str) -> str:
    raw = json.dumps(args, sort_keys=True) if isinstance(args, dict) else str(args)
    return hashlib.sha256(f"{tool_name}:{raw}".encode()).hexdigest()[:16]


def is_repeated_action(recent_actions: list[str] | None, threshold: int = 3) -> bool:
    if not recent_actions or len(recent_actions) < threshold:
        return False
    last_action = recent_actions[-1]
    return recent_actions[-threshold:] == [last_action] * threshold


def route_after_analyze(state: AgentState) -> Literal["plan", "rlm_run", "end"]:
    if state.get("status") in ("failed", "cancelled"):
        return "end"
    if state.get("is_rlm_mode"):
        return "rlm_run"
    return "plan"


def route_after_act(state: AgentState) -> Literal["observe", "review", "end"]:
    if state.get("status") in ("failed", "cancelled"):
        return "end"

    pending_calls = state.get("pending_tool_calls")
    if not pending_calls:
        return "review"

    recent = state.get("recent_actions") or []
    if is_repeated_action(recent, threshold=3):
        # Prevent infinite repetitive tool call loops
        return "review"

    return "observe"


def route_after_observe(state: AgentState) -> Literal["review", "end"]:
    if state.get("status") in ("failed", "cancelled"):
        return "end"
    return "review"


def route_after_review(state: AgentState) -> Literal["plan", "act", "end"]:
    step = state.get("step", 0)
    max_steps = state.get("max_steps", 15)

    if step >= max_steps:
        return "end"

    if state.get("status") in ("failed", "cancelled", "completed"):
        return "end"

    verdict = state.get("verdict")
    if verdict == "pass":
        return "end"
    elif verdict == "retry":
        return "plan"
    elif verdict == "continue":
        return "act"

    # Default fallback
    return "end"
