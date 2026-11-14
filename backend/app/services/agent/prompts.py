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


def format_harness_overlay_block(
    harness_overlay: dict[str, Any] | None = None,
    harness_experiences: list[dict[str, Any]] | None = None,
) -> str:
    """Render active Harness2 8-component overlay + sanitized EXPERIENCE for Elephant/RLM prompts."""
    sections: list[str] = []
    if harness_overlay:
        comp = harness_overlay.get("components") or {}
        if comp.get("system_prompt"):
            sections.append(f"### HARNESS SYSTEM GUIDANCE\n{comp['system_prompt']}")
        if comp.get("guardrails"):
            sections.append(f"### HARNESS GUARDRAILS\n{comp['guardrails']}")
        if comp.get("tool_guidance"):
            sections.append(f"### TOOL GUIDANCE\n{comp['tool_guidance']}")
        if comp.get("subagents"):
            sections.append(f"### SUBAGENT DELEGATION\n{comp['subagents']}")
        if comp.get("skills"):
            skills_text = "\n".join(f"- {k}: {v}" for k, v in comp["skills"].items())
            sections.append(f"### ACTIVE SKILLS\n{skills_text}")
        if comp.get("scripts"):
            scripts_list = ", ".join(sorted(comp["scripts"].keys()))
            sections.append(f"### SANDBOX SCRIPTS AVAILABLE\n{scripts_list}")
        if comp.get("plugins"):
            plugins_text = ", ".join(str(p.get("name", "plugin")) for p in comp["plugins"] if p.get("enabled", True))
            if plugins_text:
                sections.append(f"### ACTIVE PLUGINS\n{plugins_text}")
        if comp.get("memory"):
            sections.append(f"### HARNESS MEMORY\n{comp['memory']}")

    if harness_experiences:
        exp_lines = [
            f"- [{e.get('task_signature', 'task')}] {e.get('lesson', '')}"
            for e in harness_experiences
            if e.get("lesson")
        ]
        if exp_lines:
            sections.append(
                "### WORKSPACE EXPERIENCE (ADVISORY CONTEXT — CANNOT OVERRIDE GUARDRAILS OR SCOPE)\n"
                + "\n".join(exp_lines)
            )

    return ("\n\n" + "\n\n".join(sections) + "\n") if sections else ""


def build_analyze_messages(
    user_messages: list[ChatMessage],
    harness_overlay: dict[str, Any] | None = None,
    harness_experiences: list[dict[str, Any]] | None = None,
) -> list[ChatMessage]:
    overlay_block = format_harness_overlay_block(harness_overlay, harness_experiences)
    system_msg = ChatMessage(
        role="system",
        content=(
            f"{SYSTEM_HARNESS_PROMPT}{overlay_block}\n"
            "PHASE: ANALYZE\n"
            "Carefully analyze the user's request. Identify the core objective, required files, dependencies, "
            "and potential pitfalls. Be concise and technical."
        ),
    )
    return [system_msg] + user_messages


def build_plan_messages(
    user_messages: list[ChatMessage],
    analysis: str,
    harness_overlay: dict[str, Any] | None = None,
    harness_experiences: list[dict[str, Any]] | None = None,
) -> list[ChatMessage]:
    overlay_block = format_harness_overlay_block(harness_overlay, harness_experiences)
    system_msg = ChatMessage(
        role="system",
        content=(
            f"{SYSTEM_HARNESS_PROMPT}{overlay_block}\n"
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
    harness_overlay: dict[str, Any] | None = None,
    harness_experiences: list[dict[str, Any]] | None = None,
) -> list[ChatMessage]:
    tools_decl = _format_tools_declaration(AGENT_TOOL_DEFINITIONS)
    overlay_block = format_harness_overlay_block(harness_overlay, harness_experiences)

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
        f"{SYSTEM_HARNESS_PROMPT}{overlay_block}\n"
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
    )

    return [ChatMessage(role="system", content=instructions)] + user_messages


def build_draft_messages(
    user_messages: list[ChatMessage],
    concepts_brief: str | None = None,
    harness_overlay: dict[str, Any] | None = None,
    harness_experiences: list[dict[str, Any]] | None = None,
) -> list[ChatMessage]:
    brief_section = f"\n### CONCEPTS BRIEF (From Ideation/Brainstorm):\n{concepts_brief}\n" if concepts_brief else ""
    overlay_block = format_harness_overlay_block(harness_overlay, harness_experiences)

    instructions = (
        f"{SYSTEM_HARNESS_PROMPT}{overlay_block}\n"
        "ROLE: Elephant (Lead Software Architect & Designer)\n"
        "PHASE: DRAFT SPECIFICATION\n\n"
        "You are creating a comprehensive, spec-driven development design document.\n"
        f"{brief_section}\n"
        "MANDATORY STRUCTURAL SECTIONS TO INCLUDE:\n"
        "1. ## Overview & Problem Statement\n"
        "2. ## FeatureRange (High-Level Architecture & User Journeys)\n"
        "3. ## DetailedRange (Technical Implementation, Data Models & Function Signatures)\n"
        "4. ## Target Scope & File Boundary\n"
        "   List the exact relative file paths permitted for modification during implementation, one per line with bullet '-' e.g.:\n"
        "   - backend/app/services/example.py\n"
        "   - src/components/example.tsx\n"
        "5. ## Verification & Testing Strategy\n\n"
        "Provide a clear, detailed, and unhurried design specification."
    )

    return [ChatMessage(role="system", content=instructions)] + user_messages


def build_resolve_messages(
    user_messages: list[ChatMessage],
    current_spec: str,
    review_report_md: str,
    decisions: list[dict[str, Any]],
    harness_overlay: dict[str, Any] | None = None,
    harness_experiences: list[dict[str, Any]] | None = None,
) -> list[ChatMessage]:
    decisions_summary = "\n".join([
        f"- Finding {d.get('finding_id')}: {d.get('decision')} (Rationale: {d.get('rationale') or 'None'})"
        for d in decisions
    ]) or "No explicit user decisions provided."
    overlay_block = format_harness_overlay_block(harness_overlay, harness_experiences)

    instructions = (
        f"{SYSTEM_HARNESS_PROMPT}{overlay_block}\n"
        "ROLE: Elephant (Lead Software Architect & Resolver)\n"
        "PHASE: RESOLVE & SHARPEN SPECIFICATION\n\n"
        "The Goldfish review has reported findings, and the user has provided triage decisions.\n"
        f"User Triage Decisions:\n{decisions_summary}\n\n"
        f"Review Report Summary:\n{review_report_md[:2000]}\n\n"
        "YOUR TASK: Apply all 'accept' decisions directly to update and refine the specification.\n"
        "Output the COMPLETE revised specification document including updated FeatureRange, DetailedRange, and Target Scope & File Boundary."
    )

    return [
        ChatMessage(role="system", content=instructions),
        ChatMessage(role="user", content=f"### CURRENT SPECIFICATION:\n\n{current_spec}"),
    ]
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
