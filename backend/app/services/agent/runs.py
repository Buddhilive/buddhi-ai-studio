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
        }

        await emitter.emit_run_start({
            "model": request.model,
            "max_steps": initial_state["max_steps"],
        })

        try:
            config = {"configurable": {"emitter": emitter, "thread_id": run_id}}
            result_state = await agent_graph.ainvoke(initial_state, config=config)

            final_status = result_state.get("status", "completed")
            final_output = result_state.get("final_output")
            steps_taken = result_state.get("step", 0)
            session_id = result_state.get("session_id")

        except asyncio.CancelledError:
            logger.info("Agent run %s cancelled by user or client disconnect", run_id)
            final_status = "cancelled"
            await emitter.emit_error("Agent run cancelled", code="cancelled")

        except Exception as exc:
            logger.exception("Error during execution of agent run %s: %s", run_id, exc)
            final_status = "failed"
            await emitter.emit_error(f"Agent execution failure: {str(exc)}", code="execution_error")

        finally:
            # Terminate sandbox session to prevent resource leaks (SC-005, SC-006)
            if session_id:
                try:
                    await sandbox_service.terminate_session(session_id)
                except Exception as exc:
                    logger.warning("Error terminating sandbox session %s: %s", session_id, exc)

            await emitter.emit_run_end(
                status=final_status,
                final_output=final_output,
                steps=steps_taken,
            )

            async with self._lock:
                self._active_runs.pop(run_id, None)


agent_run_manager = AgentRunManager()
