from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from app.core.config import settings
from app.schemas.agent import AgentRunRequest, AgentRunStatus
from app.services.agent.events import AgentEventEmitter
from app.services.agent.graph import agent_graph
from app.services.agent.state import AgentState
from app.services.sandbox_service import sandbox_service

logger = logging.getLogger(__name__)


class AgentConcurrencyLimitError(Exception):
    pass


class ActiveRun:
    def __init__(self, run_id: str, emitter: AgentEventEmitter, task: asyncio.Task[Any]) -> None:
        self.run_id = run_id
        self.emitter = emitter
        self.task = task
        self.session_id: str | None = None
        self.status: AgentRunStatus = "running"


class AgentRunManager:
    def __init__(self) -> None:
        self._active_runs: dict[str, ActiveRun] = {}
        self._lock = asyncio.Lock()

    async def start_run(self, request: AgentRunRequest) -> tuple[str, AgentEventEmitter]:
        async with self._lock:
            if len(self._active_runs) >= settings.agent_max_active_runs:
                raise AgentConcurrencyLimitError(
                    f"Concurrency limit reached ({settings.agent_max_active_runs} active runs). Please retry later."
                )

            run_id = f"run_{uuid.uuid4().hex[:12]}"
            emitter = AgentEventEmitter(run_id)

            task = asyncio.create_task(self._run_loop(run_id, request, emitter))
            active_run = ActiveRun(run_id, emitter, task)
            self._active_runs[run_id] = active_run

            return run_id, emitter

    async def cancel_run(self, run_id: str) -> bool:
        async with self._lock:
            active_run = self._active_runs.get(run_id)
            if not active_run:
                return False

            active_run.status = "cancelled"
            if not active_run.task.done():
                active_run.task.cancel()

            return True

    def get_active_run(self, run_id: str) -> ActiveRun | None:
        return self._active_runs.get(run_id)

    async def _run_loop(self, run_id: str, request: AgentRunRequest, emitter: AgentEventEmitter) -> None:
        session_id = request.session_id
        final_status: AgentRunStatus = "completed"
        final_output: str | None = None
        steps_taken = 0

        is_egm = request.egm_mode
        if is_egm is None:
            from app.core.settings_store import get_egm_settings
            is_egm = bool(get_egm_settings().get("enabled", False))

        from app.core.settings_store import get_harness_settings
        harness_conf = get_harness_settings()
        harness_mode = request.harness_mode
        if harness_mode is None:
            harness_mode = "auto" if harness_conf.get("enabled", True) else "off"

        initial_state: AgentState = {
            "run_id": run_id,
            "messages": request.messages,
            "plan": [],
            "pending_tool_calls": [],
            "observations": [],
            "verdict": None,
            "step": 0,
            "max_steps": request.max_steps or settings.agent_max_steps,
            "recent_actions": [],
            "status": "running",
            "session_id": session_id,
            "final_output": None,
            "error": None,
            "is_egm_mode": is_egm,
            "egm_skill_mode": request.egm_skill_mode,
            "egm_phase": None,
            "egm_round": 1,
            "egm_max_rounds": request.egm_max_rounds or 3,
            "egm_approved": False,
            "spec_contract": None,
            "review_report": None,
            "resolution_decisions": [],
            "allowed_write_paths": [],
            "egm_artifacts": {},
            "concepts_brief": None,
            "drift_report": None,
            "workspace_id": request.workspace_id or "default",
            "harness_mode": harness_mode,
            "harness_overlay": None,
            "harness_experiences": [],
            "harness_calibration_rounds": 0,
            "harness_max_calibration_rounds": int(harness_conf.get("max_calibration_rounds", 1)),
            "harness_last_failure_sig": None,
            "harness_report": None,
        }

        await emitter.emit_run_start({
            "model": request.model,
            "max_steps": initial_state["max_steps"],
            "is_egm_mode": is_egm,
        })

        try:
            config = {"configurable": {"emitter": emitter, "thread_id": run_id, "checkpoint_ns": ""}}
            result_state = await agent_graph.ainvoke(initial_state, config=config)

            final_status = result_state.get("status", "completed")
            final_output = result_state.get("final_output")
            steps_taken = result_state.get("step", 0)
            session_id = result_state.get("session_id")

            # Check if paused at interrupt gate (e.g. resolve)
            state_snapshot = await agent_graph.aget_state(config)
            if state_snapshot and state_snapshot.next and "resolve" in state_snapshot.next:
                final_status = "awaiting_approval"
                active_run = self.get_active_run(run_id)
                if active_run:
                    active_run.status = "awaiting_approval"
                    active_run.session_id = session_id

                rr = result_state.get("review_report") or {}
                findings = rr.get("findings") or []
                blockers = sum(1 for f in findings if (isinstance(f, dict) and f.get("severity") == "blocker"))
                majors = sum(1 for f in findings if (isinstance(f, dict) and f.get("severity") == "major"))
                nits = sum(1 for f in findings if (isinstance(f, dict) and f.get("severity") == "nit"))

                await emitter.emit_egm_gate_pause(
                    round_num=result_state.get("egm_round", 1),
                    spec_path=(result_state.get("spec_contract") or {}).get("path", ""),
                    blocker_count=blockers,
                    major_count=majors,
                    nit_count=nits,
                    review_report=rr,
                )

        except asyncio.CancelledError:
            logger.info("Agent run %s cancelled by user or client disconnect", run_id)
            final_status = "cancelled"
            await emitter.emit_error("Agent run cancelled", code="cancelled")

        except Exception as exc:
            logger.exception("Error during execution of agent run %s: %s", run_id, exc)
            final_status = "failed"
            await emitter.emit_error(f"Agent execution failure: {str(exc)}", code="execution_error")

        finally:
            # Terminate sandbox session to prevent resource leaks EXCEPT when awaiting human approval
            if session_id and final_status != "awaiting_approval":
                try:
                    await sandbox_service.terminate_session(session_id)
                except Exception as exc:
                    logger.warning("Error terminating sandbox session %s: %s", session_id, exc)

            await emitter.emit_run_end(
                status=final_status,
                final_output=final_output,
                steps=steps_taken,
            )

            # Keep active run entry if awaiting approval for resolution
            if final_status != "awaiting_approval":
                async with self._lock:
                    self._active_runs.pop(run_id, None)


agent_run_manager = AgentRunManager()
