from __future__ import annotations

from typing import Any
from app.schemas.agent import PlanStep
from app.schemas.chat import ChatMessage
from app.services.agent.state import Observation
from app.services.agent.tools import AGENT_TOOL_DEFINITIONS
from app.services.inference_service import _format_tools_declaration


SYSTEM_HARNESS_PROMPT = (
    "You are BuddhiAI Studio's Autonomous Software Engineer.\n"
    "You operate inside a deterministic LangGraph state machine with full OpenSandbox isolation.\n"
    "All file modifications and command executions must be performed via tools in the sandbox.\n"
)


def build_analyze_messages(user_messages: list[ChatMessage]) -> list[ChatMessage]:
    system_msg = ChatMessage(
        role="system",
        content=(
            f"{SYSTEM_HARNESS_PROMPT}\n"
            "PHASE: ANALYZE\n"
            "Carefully analyze the user's request. Identify the core objective, required files, dependencies, "
            "and potential pitfalls. Be concise and technical."
        ),
    )
    return [system_msg] + user_messages


def build_plan_messages(user_messages: list[ChatMessage], analysis: str) -> list[ChatMessage]:
    system_msg = ChatMessage(
        role="system",
        content=(
            f"{SYSTEM_HARNESS_PROMPT}\n"
            "PHASE: PLAN\n"
            f"Based on the analysis:\n{analysis}\n\n"
            "Break down the implementation into clear, numbered, sequential steps.\n"
            "Format your response as a numbered list, e.g.:\n"
            "1. Create main.py with basic entry point\n"
            "2. Run tests in sandbox\n"
            "3. Verify output"
        ),
    )
    return [system_msg] + user_messages


def build_act_messages(
    user_messages: list[ChatMessage],
    plan: list[PlanStep],
    observations: list[Observation],
    max_recent_observations: int = 4,
) -> list[ChatMessage]:
    tools_decl = _format_tools_declaration(AGENT_TOOL_DEFINITIONS)

    plan_text = "\n".join(f"- [{s.status.upper()}] {s.title}" for s in plan) if plan else "No plan established."

    recent_obs = observations[-max_recent_observations:] if observations else []
    obs_text_parts = []
    for obs in recent_obs:
        obs_text_parts.append(
            f"Tool: {obs.get('name')}\n"
            f"Status: {obs.get('status')} (Exit: {obs.get('exit_code', 0)})\n"
            f"Output:\n{obs.get('output', '')}\n"
        )
    obs_text = "\n---\n".join(obs_text_parts) if obs_text_parts else "No previous tool outputs."

    instructions = (
        f"{SYSTEM_HARNESS_PROMPT}\n"
        "PHASE: ACT\n"
        f"Available Tools:\n{tools_decl}\n\n"
        f"Plan:\n{plan_text}\n\n"
        f"Recent Observations:\n{obs_text}\n\n"
        "Execute the next step using tools. Invoke tool calls using standard syntax:\n"
        '<|tool_call>call:tool_name{"param": "value"}<tool_call|>\n'
        "If all work is finished and no tool call is needed, provide your final response."
    )

    return [ChatMessage(role="system", content=instructions)] + user_messages


def build_review_messages(
    user_messages: list[ChatMessage],
    plan: list[PlanStep],
    observations: list[Observation],
) -> list[ChatMessage]:
    obs_summary = "\n".join(
        f"- {o.get('name')}: {o.get('status')} (exit {o.get('exit_code', 0)})"
        for o in observations[-6:]
    ) or "None"

    instructions = (
        f"{SYSTEM_HARNESS_PROMPT}\n"
        "PHASE: REVIEW\n"
        f"Recent tool outcomes:\n{obs_summary}\n\n"
        "Determine if the user objective has been fully satisfied and verified.\n"
        "You MUST conclude your review with exactly one of the following lines on its own line:\n"
        "VERDICT: pass\n"
        "VERDICT: retry\n"
        "VERDICT: continue\n\n"
        "- 'pass': Objective is fully met and verified.\n"
        "- 'continue': More tool steps are needed according to the plan.\n"
        "- 'retry': Execution hit unexpected failure or tests failed; replanning needed."
    )

    return [ChatMessage(role="system", content=instructions)] + user_messages
