from __future__ import annotations

import logging
import re
from typing import Any

from app.core import settings_store
from app.core.config import settings
from app.core.tool_parser import extract_tool_calls
from app.schemas.agent import PlanStep
from app.services.agent.events import AgentEventEmitter
from app.services.agent.harness.storage import harness_storage_service
from app.services.agent.harness.validator import validate_workspace_id
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


def parse_review_verdict(text: str, strict: bool = False) -> str:
    match = re.search(r"VERDICT:\s*(pass|retry|continue)", text, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    if strict:
        return "retry"
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

    # Zero-cost Level 2 Harness2 overlay + EXPERIENCE load
    harness_mode = state.get("harness_mode") or "auto"
    workspace_id = state.get("workspace_id") or "default"
    harness_overlay = state.get("harness_overlay")
    harness_experiences = state.get("harness_experiences") or []
    if harness_mode != "off" and validate_workspace_id(workspace_id):
        if harness_overlay is None:
            loaded_overlay = await harness_storage_service.aget_active_overlay(workspace_id)
            if loaded_overlay is not None:
                harness_overlay = loaded_overlay.model_dump(mode="json")
        if not harness_experiences:
            loaded_exps = await harness_storage_service.aget_active_experiences(workspace_id)
            harness_experiences = [e.model_dump(mode="json") for e in loaded_exps]

    model_id = state.get("model", settings.agent_default_model) if "model" in state else settings.agent_default_model
    messages = build_analyze_messages(
        state.get("messages", []),
        harness_overlay=harness_overlay,
        harness_experiences=harness_experiences,
    )

    text, _ = await generate_with_streaming(messages, model_id, "analyze", emitter)

    step = state.get("step", 0) + 1
    if emitter:
        await emitter.emit_node_end("analyze", {"analysis": text[:100]})

    # Check RLM activation condition
    if "is_rlm_mode" in state and state.get("is_rlm_mode") is not None:
        is_rlm_mode = bool(state["is_rlm_mode"])
    else:
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
        "harness_overlay": harness_overlay,
        "harness_experiences": harness_experiences,
    }


async def plan_node(state: AgentState, emitter: AgentEventEmitter | None = None) -> dict[str, Any]:
    if emitter:
        await emitter.emit_node_start("plan")

    model_id = state.get("model", settings.agent_default_model) if "model" in state else settings.agent_default_model
    messages = build_plan_messages(
        state.get("messages", []),
        analysis="",
        harness_overlay=state.get("harness_overlay"),
        harness_experiences=state.get("harness_experiences"),
    )

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
        harness_overlay=state.get("harness_overlay"),
        harness_experiences=state.get("harness_experiences"),
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

    # Build guardrail context from state
    from app.services.agent.tools import ToolGuardrailContext
    spec_contract = state.get("spec_contract") or {}
    guardrail_ctx = ToolGuardrailContext(
        is_egm_mode=bool(state.get("is_egm_mode")),
        run_id=str(state.get("run_id") or ""),
        egm_phase=state.get("egm_phase"),
        spec_approved=bool(state.get("egm_approved")),
        target_scope_files=tuple(spec_contract.get("target_scope_files") or ()),
        allowed_write_paths=tuple(state.get("allowed_write_paths") or ()),
    )

    for tc in pending:
        t_name = tc.function.name or ""
        t_args = tc.function.arguments or "{}"
        status, output, exit_code, truncated = await execute_tool(
            t_name, t_args, session_id, guardrail_ctx=guardrail_ctx
        )

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
    result = await runner.run(
        task_prompt=str(task_prompt),
        harness_overlay=state.get("harness_overlay"),
    )

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


async def harness_calibrate_node(state: AgentState, emitter: AgentEventEmitter | None = None) -> dict[str, Any]:
    """Level 1 Propose -> Probe -> Compose calibration node."""
    if emitter:
        await emitter.emit_node_start("harness_calibrate")

    import uuid
    from app.services.agent.harness.calibrator import compute_failure_signature, harness_calibrator
    from app.services.agent.harness.models import HarnessOverlay

    workspace_id = state.get("workspace_id") or "default"
    run_id = state.get("run_id") or f"run_{uuid.uuid4().hex[:8]}"
    round_num = int(state.get("harness_calibration_rounds") or 0) + 1
    model_id = state.get("model", settings.agent_default_model) if "model" in state else settings.agent_default_model

    user_messages = [m for m in state.get("messages", []) if getattr(m, "role", "") == "user"]
    task_prompt = str(user_messages[-1].content) if user_messages else "Complete coding task"
    observations = state.get("observations") or []
    failure_sig = compute_failure_signature(observations, state.get("error"))
    trigger_reason = (
        "explicit_opt_in"
        if state.get("harness_mode") == "calibrate" and round_num == 1
        else ("goldfish_verify_retry" if state.get("is_egm_mode") else "retry_or_uncalibrated")
    )

    raw_overlay = state.get("harness_overlay")
    baseline_overlay = HarnessOverlay.model_validate(raw_overlay) if raw_overlay else None
    harness_conf = settings_store.get_harness_settings()
    max_candidates = int(harness_conf.get("max_candidates", settings.harness_max_candidates))
    concurrency = int(harness_conf.get("probe_concurrency", settings.harness_probe_concurrency))
    probe_max_steps = int(harness_conf.get("probe_max_steps", settings.harness_probe_max_steps))
    probe_timeout_s = int(harness_conf.get("probe_timeout_s", settings.harness_probe_timeout_s))

    calibration_id = f"cal_{uuid.uuid4().hex[:10]}"
    diffs, rejected_static, rlm_used = await harness_calibrator.propose(
        workspace_id=workspace_id,
        task_prompt=task_prompt,
        observations=observations,
        baseline_overlay=baseline_overlay,
        max_candidates=max_candidates,
        model_id=model_id,
    )
    if emitter:
        await emitter.emit_harness_propose(
            round_num=round_num,
            trigger_reason=trigger_reason,
            rlm_used=rlm_used,
            candidate_count=len(diffs),
            rejected_static=rejected_static,
        )

    if not diffs:
        report_dict = {
            "calibration_id": calibration_id,
            "workspace_id": workspace_id,
            "run_id": run_id,
            "round": round_num,
            "trigger_reason": trigger_reason,
            "status": "no_improvement",
            "adopted_components": [],
            "rlm_used": rlm_used,
        }
        if emitter:
            await emitter.emit_harness_compose(round_num, "no_improvement", None, [], {"propose": "no_valid_candidates"})
            await emitter.emit_node_end("harness_calibrate", {"status": "no_improvement"})
        return {
            "harness_calibration_rounds": round_num,
            "harness_last_failure_sig": failure_sig,
            "harness_report": report_dict,
        }

    probe_results, candidate_overlays = await harness_calibrator.probe(
        workspace_id=workspace_id,
        calibration_id=calibration_id,
        diffs=diffs,
        baseline_overlay=baseline_overlay,
        task_prompt=task_prompt,
        run_id=run_id,
        concurrency=concurrency,
        max_steps=probe_max_steps,
        timeout_s=probe_timeout_s,
        model_id=model_id,
    )
    if emitter:
        for p in probe_results:
            await emitter.emit_harness_probe(
                round_num=round_num,
                candidate_id=p.candidate_id,
                status=p.status,
                steps_taken=p.steps_taken,
                tool_error_count=p.tool_error_count,
                test_pass_rate=p.test_pass_rate,
                wall_clock_ms=p.wall_clock_ms,
                guardrail_violations=p.guardrail_violations,
            )

    total_obs = len(observations)
    ok_obs = sum(1 for o in observations if o.get("status") == "completed" and o.get("exit_code", 0) == 0)
    baseline_score = (ok_obs / total_obs) if total_obs > 0 else 0.0

    report, adopted_overlay = await harness_calibrator.compose(
        workspace_id=workspace_id,
        run_id=run_id,
        calibration_id=calibration_id,
        round_num=round_num,
        trigger_reason=trigger_reason,
        task_prompt=task_prompt,
        baseline_overlay=baseline_overlay,
        baseline_score=baseline_score,
        diffs=diffs,
        probe_results=probe_results,
        candidate_overlays=candidate_overlays,
        rlm_used=rlm_used,
        model_id=model_id,
    )
    if emitter:
        await emitter.emit_harness_compose(
            round_num=round_num,
            status=report.status,
            winning_candidate_id=report.winning_candidate_id,
            adopted_components=report.adopted_components,
            rejected_reasons=report.rejected_reasons,
        )
        await emitter.emit_node_end("harness_calibrate", {"status": report.status, "adopted": report.adopted_components})

    updates: dict[str, Any] = {
        "harness_calibration_rounds": round_num,
        "harness_last_failure_sig": failure_sig,
        "harness_report": report.model_dump(mode="json"),
    }
    if adopted_overlay is not None:
        updates["harness_overlay"] = adopted_overlay.model_dump(mode="json")
    if state.get("is_egm_mode"):
        artifacts = dict(state.get("egm_artifacts") or {})
        artifacts["harness_calibration_report"] = report.model_dump_json(indent=2)
        updates["egm_artifacts"] = artifacts
    return updates


async def harness_distill_node(state: AgentState, emitter: AgentEventEmitter | None = None) -> dict[str, Any]:
    """Level 2 cross-task EXPERIENCE distillation node on verified pass."""
    if emitter:
        await emitter.emit_node_start("harness_distill")

    from app.services.agent.harness.calibrator import harness_calibrator

    report = state.get("harness_report") or {}
    adopted_components = report.get("adopted_components") or []
    if report.get("status") != "adopted" or not adopted_components:
        if emitter:
            await emitter.emit_node_end("harness_distill", {"skipped": True})
        return {}

    workspace_id = state.get("workspace_id") or "default"
    run_id = state.get("run_id") or "run_unknown"
    model_id = state.get("model", settings.agent_default_model) if "model" in state else settings.agent_default_model
    user_messages = [m for m in state.get("messages", []) if getattr(m, "role", "") == "user"]
    task_prompt = str(user_messages[-1].content) if user_messages else "Completed coding task"

    entry = await harness_calibrator.distill(
        workspace_id=workspace_id,
        run_id=run_id,
        task_prompt=task_prompt,
        adopted_components=adopted_components,
        observations=state.get("observations") or [],
        model_id=model_id,
    )
    if emitter:
        await emitter.emit_harness_distill(
            entry_id=entry.entry_id,
            workspace_id=workspace_id,
            components_affected=entry.components_affected,
            lesson=entry.lesson,
        )
        await emitter.emit_node_end("harness_distill", {"entry_id": entry.entry_id})
    return {}
