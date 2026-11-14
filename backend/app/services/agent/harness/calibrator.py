from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
import uuid
from typing import Any

from app.core import settings_store
from app.core.config import settings
from app.core.tool_parser import extract_tool_calls
from app.schemas.chat import ChatMessage
from app.schemas.sandbox import SandboxSessionCreateRequest
from app.services.agent.harness.models import (
    CalibrationReport,
    ExperienceEntry,
    HarnessComponents,
    HarnessOverlay,
    OverlayDiff,
    ProbeResult,
)
from app.services.agent.harness.storage import HarnessStorageService, harness_storage_service
from app.services.agent.harness.validator import HarnessStaticValidator, sanitize_experience_text
from app.services.agent.prompts import build_act_messages
from app.services.agent.tools import AGENT_TOOL_DEFINITIONS, ToolGuardrailContext, execute_tool
from app.services.inference_service import inference_engine_manager
from app.services.sandbox_service import SandboxService, sandbox_service

logger = logging.getLogger(__name__)


def compute_failure_signature(observations: list[dict[str, Any]], error: str | None = None) -> str:
    parts = [
        f"{o.get('name')}:{o.get('exit_code')}:{str(o.get('output', ''))[:120]}"
        for o in observations[-4:]
        if o.get("status") == "error" or o.get("exit_code", 0) != 0
    ]
    if error:
        parts.append(error[:120])
    raw = "|".join(parts) or "generic_failure"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _extract_json_payload(text: str) -> Any:
    """Extract first JSON object or array from model output."""
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", text or "").strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            return None
    return None


class HarnessCalibrator:
    """Level 1 (Propose -> Probe -> Compose) & Level 2 (Distill) Harness2 engine."""

    def __init__(
        self,
        storage: HarnessStorageService = harness_storage_service,
        sandbox_svc: SandboxService = sandbox_service,
    ) -> None:
        self.storage = storage
        self.sandbox_svc = sandbox_svc

    async def _generate_text(self, messages: list[ChatMessage], model_id: str) -> str:
        parts: list[str] = []
        async for delta in inference_engine_manager.generate_stream(
            messages=messages,
            max_tokens=settings.chat_max_tokens_default,
            enable_thinking=False,
            model_id=model_id,
            tools=None,
        ):
            if delta.content:
                parts.append(delta.content)
        return "".join(parts)

    async def _slice_trace_with_rlm(
        self,
        trace_text: str,
        task_prompt: str,
        model_id: str,
    ) -> str:
        """Delegate oversized trace analysis to RlmTaskRunner inside OpenSandbox."""
        from app.services.rlm.runner import RlmTaskRunner

        runner = RlmTaskRunner(sandbox_svc=self.sandbox_svc)
        sub_prompt = (
            "Analyze the following execution failure trace and summarize the root cause, "
            "failing tool calls, and concrete scaffolding/tool_guidance fixes needed.\n"
            f"Task Objective: {task_prompt[:500]}\n\n"
            f"Trace:\n{trace_text}"
        )
        result = await runner.run(
            task_prompt=sub_prompt,
        )
        return result.final_answer or trace_text[:4000]

    async def propose(
        self,
        workspace_id: str,
        task_prompt: str,
        observations: list[dict[str, Any]],
        baseline_overlay: HarnessOverlay | None = None,
        max_candidates: int = 2,
        model_id: str = settings.agent_default_model,
        trace_text: str = "",
    ) -> tuple[list[OverlayDiff], int, bool]:
        """Generate statically validated candidate OverlayDiffs."""
        baseline_comp = baseline_overlay.components if baseline_overlay else HarnessComponents()

        raw_trace = trace_text or "\n".join(
            f"[{o.get('name')} exit={o.get('exit_code')}] {o.get('output', '')}"
            for o in observations[-8:]
        )
        inf_settings = settings_store.get_inference_settings()
        rlm_settings = settings_store.get_rlm_settings()
        max_num = int(inf_settings.get("max_num_token", settings.chat_max_num_tokens))
        reserve = int(rlm_settings.get("prompt_reserve_tokens", 2048))
        prompt_budget_chars = max(2048, (max_num - reserve)) * 4

        rlm_used = False
        diagnosis_context = raw_trace
        if len(raw_trace) > prompt_budget_chars:
            rlm_used = True
            diagnosis_context = await self._slice_trace_with_rlm(raw_trace, task_prompt, model_id)

        sys_msg = ChatMessage(
            role="system",
            content=(
                "You are the Harness2 Propose Editor.\n"
                "Analyze the failure trace and propose up to "
                f"{max_candidates} candidate edits to the 8 editable harness components "
                "(system_prompt, guardrails, memory, tool_guidance, subagents, skills, scripts, plugins).\n"
                "Do NOT weaken guardrails or file boundaries.\n"
                'Output JSON array: [{"candidate_id": "cand_1", "rationale": "...", "updates": {"tool_guidance": "..."}}]'
            ),
        )
        usr_msg = ChatMessage(
            role="user",
            content=(
                f"Workspace: {workspace_id}\n"
                f"Task: {task_prompt[:1000]}\n"
                f"Failure Diagnosis:\n{diagnosis_context[:6000]}"
            ),
        )
        raw_out = await self._generate_text([sys_msg, usr_msg], model_id)
        parsed = _extract_json_payload(raw_out)
        items = parsed if isinstance(parsed, list) else ([parsed] if isinstance(parsed, dict) else [])

        valid_diffs: list[OverlayDiff] = []
        rejected_static = 0
        for idx, item in enumerate(items[:max_candidates]):
            if not isinstance(item, dict):
                continue
            cand_id = str(item.get("candidate_id") or f"cand_{idx + 1}")
            updates = item.get("updates") or {}
            if not isinstance(updates, dict) or not updates:
                continue
            diff = OverlayDiff(
                candidate_id=cand_id,
                rationale=str(item.get("rationale") or ""),
                updates=updates,
            )
            check = HarnessStaticValidator.validate_diff(diff, baseline=baseline_comp)
            if check.valid:
                valid_diffs.append(diff)
            else:
                rejected_static += 1
                logger.warning("Harness2 Propose rejected candidate %s: %s", cand_id, check.violations)

        return valid_diffs, rejected_static, rlm_used

    @staticmethod
    def apply_diff(baseline: HarnessOverlay | None, diff: OverlayDiff, workspace_id: str, run_id: str) -> HarnessOverlay:
        base_data = baseline.components.model_dump() if baseline else HarnessComponents().model_dump()
        for k, v in diff.updates.items():
            if k in base_data:
                if isinstance(base_data[k], dict) and isinstance(v, dict):
                    base_data[k] = {**base_data[k], **v}
                else:
                    base_data[k] = v
        return HarnessOverlay(
            version_id=f"hov_{uuid.uuid4().hex[:10]}",
            workspace_id=workspace_id,
            parent_version_id=baseline.version_id if baseline else None,
            components=HarnessComponents.model_validate(base_data),
            is_active=True,
            source_run_id=run_id,
        )

    async def _run_single_probe(
        self,
        workspace_id: str,
        calibration_id: str,
        diff: OverlayDiff,
        candidate_overlay: HarnessOverlay,
        task_prompt: str,
        max_steps: int,
        timeout_s: int,
        model_id: str,
    ) -> ProbeResult:
        probe_id = f"probe_{uuid.uuid4().hex[:10]}"
        t0 = time.perf_counter()
        session_id: str | None = None
        steps_taken = 0
        tool_errors = 0
        tool_successes = 0
        observations: list[dict[str, Any]] = []
        status: str = "passed"

        async def _execute_probe_body() -> None:
            nonlocal session_id, steps_taken, tool_errors, tool_successes, status
            req = SandboxSessionCreateRequest(
                runtime_image=settings.sandbox_default_image,
                timeout_s=max(60, timeout_s),
                allow_network=False,
                memory_limit_mb=settings.sandbox_rlm_memory_mb,
                purpose="harness_probe",
            )
            sess = await self.sandbox_svc.create_session(req)
            session_id = sess.session_id

            # Mount candidate scripts into probe sandbox (one-way)
            for sname, sbody in candidate_overlay.components.scripts.items():
                await self.sandbox_svc.write_session_file(session_id, f".buddhi/harness/scripts/{sname}", sbody)

            overlay_dict = candidate_overlay.model_dump(mode="json")
            guardrail_ctx = ToolGuardrailContext(is_egm_mode=False)

            for _ in range(max_steps):
                steps_taken += 1
                msgs = build_act_messages(
                    [ChatMessage(role="user", content=task_prompt)],
                    plan=[],
                    observations=observations,
                    harness_overlay=overlay_dict,
                )
                out_parts: list[str] = []
                async for delta in inference_engine_manager.generate_stream(
                    messages=msgs,
                    max_tokens=settings.chat_max_tokens_default,
                    enable_thinking=False,
                    model_id=model_id,
                    tools=AGENT_TOOL_DEFINITIONS,
                ):
                    if delta.content:
                        out_parts.append(delta.content)
                text = "".join(out_parts)
                _, tool_calls = extract_tool_calls(text)
                if not tool_calls:
                    break
                for tc in tool_calls:
                    t_status, t_out, t_code, _ = await execute_tool(
                        tc.function.name or "",
                        tc.function.arguments or {},
                        session_id,
                        guardrail_ctx=guardrail_ctx,
                    )
                    if t_status == "error" or t_code != 0:
                        tool_errors += 1
                    else:
                        tool_successes += 1
                    observations.append(
                        {
                            "tool_call_id": tc.id,
                            "name": tc.function.name,
                            "status": t_status,
                            "output": t_out[:600],
                            "exit_code": t_code,
                        }
                    )

        try:
            await asyncio.wait_for(_execute_probe_body(), timeout=timeout_s)
            if tool_errors > 0 and tool_successes == 0:
                status = "failed"
        except asyncio.TimeoutError:
            status = "timed_out"
        except Exception as exc:
            logger.warning("Probe %s failed: %s", probe_id, exc)
            status = "failed"
        finally:
            if session_id:
                try:
                    await asyncio.wait_for(self.sandbox_svc.terminate_session(session_id), timeout=5.0)
                except Exception as term_exc:
                    logger.warning("Failed to terminate probe sandbox %s: %s", session_id, term_exc)

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        total_calls = tool_errors + tool_successes
        pass_rate = (tool_successes / total_calls) if total_calls > 0 else (1.0 if status == "passed" else 0.0)
        summary = (
            f"status={status}, steps={steps_taken}, tool_errors={tool_errors}, "
            f"pass_rate={pass_rate:.2f}, wall_ms={elapsed_ms}"
        )
        return ProbeResult(
            probe_id=probe_id,
            calibration_id=calibration_id,
            workspace_id=workspace_id,
            candidate_id=diff.candidate_id,
            target_components=list(diff.updates.keys()),
            status=status,  # type: ignore[arg-type]
            steps_taken=steps_taken,
            tool_error_count=tool_errors,
            test_pass_rate=pass_rate,
            wall_clock_ms=elapsed_ms,
            trajectory_summary=summary,
        )

    async def probe(
        self,
        workspace_id: str,
        calibration_id: str,
        diffs: list[OverlayDiff],
        baseline_overlay: HarnessOverlay | None,
        task_prompt: str,
        run_id: str,
        concurrency: int = 1,
        max_steps: int = 6,
        timeout_s: int = 60,
        model_id: str = settings.agent_default_model,
    ) -> tuple[list[ProbeResult], dict[str, HarnessOverlay]]:
        sem = asyncio.Semaphore(max(1, concurrency))
        candidate_overlays: dict[str, HarnessOverlay] = {}

        async def _guarded(diff: OverlayDiff) -> ProbeResult:
            async with sem:
                cand_overlay = self.apply_diff(baseline_overlay, diff, workspace_id, run_id)
                candidate_overlays[diff.candidate_id] = cand_overlay
                return await self._run_single_probe(
                    workspace_id=workspace_id,
                    calibration_id=calibration_id,
                    diff=diff,
                    candidate_overlay=cand_overlay,
                    task_prompt=task_prompt,
                    max_steps=max_steps,
                    timeout_s=timeout_s,
                    model_id=model_id,
                )

        results = await asyncio.gather(*[_guarded(d) for d in diffs])
        return list(results), candidate_overlays

    async def compose(
        self,
        workspace_id: str,
        run_id: str,
        calibration_id: str,
        round_num: int,
        trigger_reason: str,
        task_prompt: str,
        baseline_overlay: HarnessOverlay | None,
        baseline_score: float,
        diffs: list[OverlayDiff],
        probe_results: list[ProbeResult],
        candidate_overlays: dict[str, HarnessOverlay],
        rlm_used: bool = False,
        model_id: str = settings.agent_default_model,
    ) -> tuple[CalibrationReport, HarnessOverlay | None]:
        """Stateless zero-context Goldfish-style contrastive evaluator."""
        eligible = [p for p in probe_results if p.status == "passed" and not p.guardrail_violations]
        rejected_reasons: dict[str, str] = {}
        for p in probe_results:
            if p.status != "passed":
                rejected_reasons[p.candidate_id] = f"probe_{p.status}"

        if not eligible:
            report = CalibrationReport(
                calibration_id=calibration_id,
                workspace_id=workspace_id,
                run_id=run_id,
                round=round_num,
                trigger_reason=trigger_reason,
                baseline_overlay_id=baseline_overlay.version_id if baseline_overlay else None,
                baseline_score=baseline_score,
                status="no_improvement",
                rejected_reasons=rejected_reasons,
                rlm_used=rlm_used,
                probes=probe_results,
            )
            self.storage.record_calibration(report, probe_results)
            return report, None

        # Stateless zero-context contrastive evaluation (never receives Elephant chat history)
        cand_summaries = "\n".join(
            f"- {p.candidate_id}: {p.trajectory_summary}" for p in eligible
        )
        eval_messages = [
            ChatMessage(
                role="system",
                content=(
                    "You are the zero-context Harness2 Compose Contrastive Evaluator.\n"
                    "Compare candidate probe trajectories against the baseline score.\n"
                    "Select a winner ONLY if it strictly improves verifiable execution signals "
                    "without weakening guardrails or boundaries.\n"
                    'Respond with JSON: {"winner_id": "<id or null>", "reason": "..."}'
                ),
            ),
            ChatMessage(
                role="user",
                content=(
                    f"Task Objective: {task_prompt[:800]}\n"
                    f"Baseline Score: {baseline_score:.2f}\n"
                    f"Candidate Probes:\n{cand_summaries}"
                ),
            ),
        ]
        raw_eval = await self._generate_text(eval_messages, model_id)
        parsed_eval = _extract_json_payload(raw_eval)
        winner_id = parsed_eval.get("winner_id") if isinstance(parsed_eval, dict) else None

        # Deterministic score fallback if LLM didn't return structured JSON
        best_probe = max(eligible, key=lambda p: (p.test_pass_rate, -p.tool_error_count, -p.steps_taken))
        if winner_id and any(p.candidate_id == winner_id for p in eligible):
            chosen_probe = next(p for p in eligible if p.candidate_id == winner_id)
        elif best_probe.test_pass_rate > baseline_score:
            chosen_probe = best_probe
        else:
            chosen_probe = None

        if not chosen_probe or chosen_probe.test_pass_rate <= baseline_score:
            report = CalibrationReport(
                calibration_id=calibration_id,
                workspace_id=workspace_id,
                run_id=run_id,
                round=round_num,
                trigger_reason=trigger_reason,
                baseline_overlay_id=baseline_overlay.version_id if baseline_overlay else None,
                baseline_score=baseline_score,
                status="no_improvement",
                rejected_reasons={**rejected_reasons, "contrastive": "did_not_beat_baseline"},
                rlm_used=rlm_used,
                probes=probe_results,
            )
            self.storage.record_calibration(report, probe_results)
            return report, None

        winning_diff = next(d for d in diffs if d.candidate_id == chosen_probe.candidate_id)
        baseline_comp = baseline_overlay.components if baseline_overlay else HarnessComponents()
        recheck = HarnessStaticValidator.validate_diff(winning_diff, baseline=baseline_comp)
        if not recheck.valid:
            rejected_reasons[chosen_probe.candidate_id] = "; ".join(recheck.violations)
            report = CalibrationReport(
                calibration_id=calibration_id,
                workspace_id=workspace_id,
                run_id=run_id,
                round=round_num,
                trigger_reason=trigger_reason,
                baseline_overlay_id=baseline_overlay.version_id if baseline_overlay else None,
                baseline_score=baseline_score,
                status="rejected",
                rejected_reasons=rejected_reasons,
                rlm_used=rlm_used,
                probes=probe_results,
            )
            self.storage.record_calibration(report, probe_results)
            return report, None

        winning_overlay = candidate_overlays[chosen_probe.candidate_id]
        saved_overlay = self.storage.save_overlay_snapshot(winning_overlay, activate=True)

        report = CalibrationReport(
            calibration_id=calibration_id,
            workspace_id=workspace_id,
            run_id=run_id,
            round=round_num,
            trigger_reason=trigger_reason,
            baseline_overlay_id=baseline_overlay.version_id if baseline_overlay else None,
            baseline_score=baseline_score,
            winning_candidate_id=chosen_probe.candidate_id,
            adopted_overlay_id=saved_overlay.version_id,
            status="adopted",
            adopted_components=list(winning_diff.updates.keys()),
            rejected_reasons=rejected_reasons,
            rlm_used=rlm_used,
            probes=probe_results,
        )
        self.storage.record_calibration(report, probe_results)
        return report, saved_overlay

    async def distill(
        self,
        workspace_id: str,
        run_id: str,
        task_prompt: str,
        adopted_components: list[str],
        observations: list[dict[str, Any]],
        model_id: str = settings.agent_default_model,
    ) -> ExperienceEntry:
        """Level 2 distillation: persist concise, sanitized cross-task lesson."""
        obs_brief = "\n".join(
            f"- {o.get('name')}: {o.get('status')} (exit={o.get('exit_code')})"
            for o in observations[-4:]
        )
        messages = [
            ChatMessage(
                role="system",
                content=(
                    "Summarize a single, concise (< 250 chars) reusable lesson from this verified run "
                    "for future tasks in this repository. Output plain text only."
                ),
            ),
            ChatMessage(
                role="user",
                content=f"Task: {task_prompt[:400]}\nAdopted Components: {adopted_components}\nObservations:\n{obs_brief}",
            ),
        ]
        raw_lesson = await self._generate_text(messages, model_id)
        lesson = sanitize_experience_text(raw_lesson, max_chars=400) or (
            f"Calibrated {', '.join(adopted_components)} for task pattern."
        )
        sig = hashlib.sha256(task_prompt[:200].encode("utf-8")).hexdigest()[:12]
        entry = ExperienceEntry(
            entry_id=f"exp_{uuid.uuid4().hex[:10]}",
            workspace_id=workspace_id,
            task_signature=f"task_{sig}",
            lesson=lesson,
            evidence_run_id=run_id,
            components_affected=adopted_components,
            confidence_score=0.85,
        )
        return self.storage.upsert_experience(entry)


harness_calibrator = HarnessCalibrator()
