from __future__ import annotations

import logging
import re
from typing import Any

from app.core import settings_store
from app.core.config import settings
from app.core.tool_parser import extract_tool_calls
from app.schemas.agent import PlanStep
from app.services.agent.events import AgentEventEmitter
from app.services.agent.prompts import (
    build_act_messages,
    build_analyze_messages,
    build_plan_messages,
    build_review_messages,
)
from app.services.agent.routing import compute_action_hash
from app.services.agent.state import AgentState, Observation
from app.services.agent.tools import AGENT_TOOL_DEFINITIONS, ensure_sandbox_session, execute_tool
from app.services.inference_service import inference_engine_manager

logger = logging.getLogger(__name__)


def parse_plan_text(text: str) -> list[PlanStep]:
    steps: list[PlanStep] = []
    lines = text.strip().splitlines()
    for line in lines:
        cleaned = line.strip()
        # Match "1. Step description" or "- [ ] Step description"
        match = re.match(r"^(\d+\.|\-|\*)\s+(.*)", cleaned)
        if match:
            desc = match.group(2).strip()
            if desc:
                steps.append(PlanStep(title=desc, status="pending"))
    if not steps and text.strip():
        # Fallback to single step if no numbered items matched
        steps.append(PlanStep(title=text.strip()[:100], status="pending"))
    return steps


def parse_review_verdict(text: str) -> str:
    match = re.search(r"VERDICT:\s*(pass|retry|continue)", text, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    # Default to pass if positive or stop indicators, otherwise pass if final output ready
    if "pass" in text.lower():
        return "pass"
    return "pass"


async def generate_with_streaming(
    messages: list[Any],
    model_id: str,
    node_name: str,
    emitter: AgentEventEmitter | None = None,
    tools: list[Any] | None = None,
) -> tuple[str, str]:
    """Generates completion and emits reasoning and text deltas."""
    output_parts: list[str] = []
    reasoning_parts: list[str] = []

    try:
        async for delta in inference_engine_manager.generate_stream(
            messages=messages,
            max_tokens=settings.chat_max_tokens_default,
            enable_thinking=True,
            model_id=model_id,
            tools=tools,
        ):
            if delta.reasoning and emitter:
                reasoning_parts.append(delta.reasoning)
                await emitter.emit_reasoning_delta(node_name, delta.reasoning)
            if delta.content:
                output_parts.append(delta.content)
                if emitter:
                    await emitter.emit_text_delta(node_name, delta.content)
    except Exception as exc:
        logger.error("Error in inference stream for node %s: %s", node_name, exc)
        raise

    full_output = "".join(output_parts)
    full_reasoning = "".join(reasoning_parts)
    return full_output, full_reasoning


async def analyze_node(state: AgentState, emitter: AgentEventEmitter | None = None) -> dict[str, Any]:
    if emitter:
        await emitter.emit_node_start("analyze")

    model_id = state.get("model", settings.agent_default_model) if "model" in state else settings.agent_default_model
    messages = build_analyze_messages(state.get("messages", []))

    text, _ = await generate_with_streaming(messages, model_id, "analyze", emitter)

    step = state.get("step", 0) + 1
    if emitter:
        await emitter.emit_node_end("analyze", {"analysis": text[:100]})

    # Check RLM activation condition
    rlm_conf = settings_store.get_rlm_settings()
    is_rlm_mode = False
    if rlm_conf.get("enabled", True):
        mode = rlm_conf.get("mode", "auto")
        if mode == "always":
            is_rlm_mode = True
        elif mode == "auto":
            all_content = " ".join(
                str(m.content) for m in state.get("messages", []) if hasattr(m, "content") and m.content
            )
            estimated_tokens = max(1, len(all_content) // 4)
            current_max_tokens = int(settings_store.get_inference_settings().get("max_num_token", 16384))
            ratio = float(rlm_conf.get("auto_threshold_ratio", 0.6))
            threshold = int(current_max_tokens * ratio)
            if estimated_tokens >= threshold or "rlm" in all_content.lower():
                is_rlm_mode = True

    return {
        "step": step,
        "status": "running",
        "is_rlm_mode": is_rlm_mode,
    }


async def plan_node(state: AgentState, emitter: AgentEventEmitter | None = None) -> dict[str, Any]:
    if emitter:
        await emitter.emit_node_start("plan")

    model_id = state.get("model", settings.agent_default_model) if "model" in state else settings.agent_default_model
    messages = build_plan_messages(state.get("messages", []), analysis="")

    text, _ = await generate_with_streaming(messages, model_id, "plan", emitter)
    plan_steps = parse_plan_text(text)

    if emitter:
        await emitter.emit_plan_update([s.model_dump() for s in plan_steps])
        await emitter.emit_node_end("plan", {"steps_count": len(plan_steps)})

    return {
        "plan": plan_steps,
        "step": state.get("step", 0) + 1,
    }


async def act_node(state: AgentState, emitter: AgentEventEmitter | None = None) -> dict[str, Any]:
    if emitter:
        await emitter.emit_node_start("act")

    model_id = state.get("model", settings.agent_default_model) if "model" in state else settings.agent_default_model
    messages = build_act_messages(
        state.get("messages", []),
        state.get("plan", []),
        state.get("observations", []),
    )

    text, _ = await generate_with_streaming(
        messages,
        model_id,
        "act",
        emitter,
        tools=AGENT_TOOL_DEFINITIONS,
    )

    residual_text, tool_calls = extract_tool_calls(text)

    new_action_hashes: list[str] = []
    if tool_calls:
        for tc in tool_calls:
            h = compute_action_hash(tc.function.name or "", tc.function.arguments or "")
            new_action_hashes.append(h)
            if emitter:
                await emitter.emit_tool_call(tc.id, tc.function.name or "", tc.function.arguments or "")

    step = state.get("step", 0) + 1
    if emitter:
        await emitter.emit_node_end("act", {"tool_calls_count": len(tool_calls)})

    return {
        "pending_tool_calls": tool_calls,
        "recent_actions": new_action_hashes,
        "final_output": residual_text or text if not tool_calls else None,
        "step": step,
    }


async def observe_node(state: AgentState, emitter: AgentEventEmitter | None = None) -> dict[str, Any]:
    if emitter:
        await emitter.emit_node_start("observe")

    session_id = await ensure_sandbox_session(state.get("session_id"))
    pending = state.get("pending_tool_calls") or []
    new_obs: list[Observation] = []

    for tc in pending:
        t_name = tc.function.name or ""
        t_args = tc.function.arguments or "{}"
        status, output, exit_code, truncated = await execute_tool(t_name, t_args, session_id)

        if emitter:
            await emitter.emit_tool_result(
                tool_call_id=tc.id,
                tool_name=t_name,
                status=status,
                output=output,
                exit_code=exit_code,
                truncated=truncated,
            )

        new_obs.append(
            Observation(
                tool_call_id=tc.id,
                name=t_name,
                status=status,
                output=output,
                exit_code=exit_code,
                truncated=truncated,
            )
        )

    step = state.get("step", 0) + 1
    if emitter:
        await emitter.emit_node_end("observe", {"executed_count": len(new_obs)})

    return {
        "session_id": session_id,
        "pending_tool_calls": [],
        "observations": new_obs,
        "step": step,
    }


async def review_node(state: AgentState, emitter: AgentEventEmitter | None = None) -> dict[str, Any]:
    if emitter:
        await emitter.emit_node_start("review")

    model_id = state.get("model", settings.agent_default_model) if "model" in state else settings.agent_default_model
    messages = build_review_messages(
        state.get("messages", []),
        state.get("plan", []),
        state.get("observations", []),
    )

    text, _ = await generate_with_streaming(messages, model_id, "review", emitter)
    verdict = parse_review_verdict(text)

    step = state.get("step", 0) + 1
    max_steps = state.get("max_steps", settings.agent_max_steps)

    status = state.get("status", "running")
    if verdict == "pass" or not state.get("pending_tool_calls") and state.get("final_output"):
        status = "completed"
    elif step >= max_steps:
        status = "max_steps_reached"

    if emitter:
        await emitter.emit_node_end("review", {"verdict": verdict, "status": status})

    return {
        "verdict": verdict,
        "status": status,
        "step": step,
    }


async def rlm_run_node(state: AgentState, emitter: AgentEventEmitter | None = None) -> dict[str, Any]:
    """Autonomous RLM execution node running in an isolated OpenSandbox session."""
    if emitter:
        await emitter.emit_node_start("rlm_run")

    from app.services.rlm.runner import RlmTaskRunner
    from dataclasses import asdict

    user_messages = [m for m in state.get("messages", []) if getattr(m, "role", "") == "user"]
    task_prompt = user_messages[-1].content if user_messages else "Analyze repository codebase"
    if isinstance(task_prompt, list):
        task_prompt = " ".join(str(p) for p in task_prompt)

    runner = RlmTaskRunner()
    result = await runner.run(task_prompt=str(task_prompt))

    if emitter:
        await emitter.emit_text_delta("rlm_run", result.final_answer)
        await emitter.emit_node_end("rlm_run", {
            "status": result.status,
            "steps": result.steps_taken,
            "telemetry": asdict(result.telemetry),
        })

    return {
        "status": "completed" if result.status == "completed" else "failed",
        "final_output": result.final_answer,
        "rlm_telemetry": asdict(result.telemetry),
        "is_rlm_mode": True,
    }
