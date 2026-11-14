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


def route_after_analyze(state: AgentState) -> Literal["plan", "rlm_run", "draft", "brainstorm", "drift_report", "end"]:
    if state.get("status") in ("failed", "cancelled"):
        return "end"
    if state.get("is_egm_mode"):
        mode = state.get("egm_skill_mode", "standard")
        if mode == "brainstorm":
            return "brainstorm"
        elif mode == "drift_report":
            return "drift_report"
        elif mode == "bootstrap":
            return "rlm_run"
        return "draft"
    if state.get("is_rlm_mode"):
        return "rlm_run"
    return "plan"


def route_after_act(state: AgentState) -> Literal["observe", "review", "goldfish_verify", "end"]:
    if state.get("status") in ("failed", "cancelled"):
        return "end"

    next_review = "goldfish_verify" if state.get("is_egm_mode") else "review"

    pending_calls = state.get("pending_tool_calls")
    if not pending_calls:
        return next_review

    recent = state.get("recent_actions") or []
    if is_repeated_action(recent, threshold=3):
        # Prevent infinite repetitive tool call loops
        return next_review

    return "observe"


def route_after_observe(state: AgentState) -> Literal["review", "goldfish_verify", "end"]:
    if state.get("status") in ("failed", "cancelled"):
        return "end"
    return "goldfish_verify" if state.get("is_egm_mode") else "review"


def route_after_resolve(state: AgentState) -> Literal["plan", "draft", "goldfish_review", "end"]:
    if state.get("status") in ("failed", "cancelled"):
        return "end"

    if state.get("egm_approved"):
        return "plan"

    round_num = state.get("egm_round", 1)
    max_rounds = state.get("egm_max_rounds", 3)

    # Check for remaining blockers
    review_report = state.get("review_report") or {}
    findings = review_report.get("findings") or []
    has_unresolved_blocker = any(
        isinstance(f, dict) and f.get("severity") == "blocker" and f.get("decision") != "accept"
        for f in findings
    )

    if round_num >= max_rounds and has_unresolved_blocker:
        return "end"

    return "goldfish_review"


def route_after_goldfish_verify(state: AgentState) -> Literal["plan", "act", "end"]:
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

    # Fail closed for EGM
    return "end"


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
