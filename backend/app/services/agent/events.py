from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator

from app.schemas.agent import AgentEvent, AgentEventType

logger = logging.getLogger(__name__)


class AgentEventEmitter:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()
        self._closed = False

    async def emit(
        self,
        event_type: AgentEventType,
        node: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        if self._closed:
            return
        event = AgentEvent(
            event=event_type,
            run_id=self.run_id,
            node=node,
            data=data or {},
        )
        await self._queue.put(event)

    async def emit_run_start(self, initial_data: dict[str, Any] | None = None) -> None:
        await self.emit("run.start", data=initial_data)

    async def emit_node_start(self, node_name: str) -> None:
        await self.emit("node.start", node=node_name)

    async def emit_node_end(self, node_name: str, result_summary: dict[str, Any] | None = None) -> None:
        await self.emit("node.end", node=node_name, data=result_summary)

    async def emit_reasoning_delta(self, node: str, delta: str) -> None:
        await self.emit("reasoning.delta", node=node, data={"delta": delta})

    async def emit_text_delta(self, node: str, delta: str) -> None:
        await self.emit("text.delta", node=node, data={"delta": delta})

    async def emit_plan_update(self, plan: list[dict[str, Any]]) -> None:
        await self.emit("plan.update", data={"plan": plan})

    async def emit_tool_call(self, tool_call_id: str, tool_name: str, arguments: dict[str, Any] | str) -> None:
        await self.emit(
            "tool.call",
            data={
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "arguments": arguments,
            },
        )

    async def emit_tool_result(
        self,
        tool_call_id: str,
        tool_name: str,
        status: str,
        output: str,
        exit_code: int = 0,
        truncated: bool = False,
    ) -> None:
        await self.emit(
            "tool.result",
            data={
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "status": status,
                "output": output,
                "exit_code": exit_code,
                "truncated": truncated,
            },
        )

    async def emit_error(self, message: str, code: str = "agent_error") -> None:
        await self.emit("error", data={"message": message, "code": code})

    async def emit_egm_phase(self, phase: str, round_num: int = 1, max_rounds: int = 3) -> None:
        await self.emit("egm.phase", data={"phase": phase, "round": round_num, "max_rounds": max_rounds})

    async def emit_egm_reviewer_status(
        self,
        stage: str,
        persona: str,
        status: str,
        round_num: int = 1,
        findings_count: int | None = None,
    ) -> None:
        await self.emit(
            "egm.reviewer.status",
            data={
                "stage": stage,
                "persona": persona,
                "status": status,
                "round": round_num,
                "findings_count": findings_count,
            },
        )

    async def emit_egm_artifact(
        self,
        artifact_type: str,
        path: str,
        round_num: int = 1,
        summary: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            "egm.artifact",
            data={
                "artifact_type": artifact_type,
                "path": path,
                "round": round_num,
                "summary": summary or {},
            },
        )

    async def emit_egm_gate_pause(
        self,
        round_num: int = 1,
        spec_path: str = "",
        blocker_count: int = 0,
        major_count: int = 0,
        nit_count: int = 0,
        review_report: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            "egm.gate.pause",
            data={
                "round": round_num,
                "spec_path": spec_path,
                "blocker_count": blocker_count,
                "major_count": major_count,
                "nit_count": nit_count,
                "review_report": review_report or {},
            },
        )

    async def emit_harness_propose(
        self,
        round_num: int,
        trigger_reason: str,
        rlm_used: bool,
        candidate_count: int,
        rejected_static: int = 0,
    ) -> None:
        await self.emit(
            "harness.propose",
            node="harness_calibrate",
            data={
                "round": round_num,
                "trigger_reason": trigger_reason,
                "rlm_used": rlm_used,
                "candidate_count": candidate_count,
                "rejected_static": rejected_static,
            },
        )

    async def emit_harness_probe(
        self,
        round_num: int,
        candidate_id: str,
        status: str,
        steps_taken: int,
        tool_error_count: int,
        test_pass_rate: float,
        wall_clock_ms: int,
        guardrail_violations: list[str] | None = None,
    ) -> None:
        await self.emit(
            "harness.probe",
            node="harness_calibrate",
            data={
                "round": round_num,
                "candidate_id": candidate_id,
                "status": status,
                "steps_taken": steps_taken,
                "tool_error_count": tool_error_count,
                "test_pass_rate": test_pass_rate,
                "wall_clock_ms": wall_clock_ms,
                "guardrail_violations": guardrail_violations or [],
            },
        )

    async def emit_harness_compose(
        self,
        round_num: int,
        status: str,
        winning_candidate_id: str | None,
        adopted_components: list[str],
        rejected_reasons: dict[str, str] | None = None,
    ) -> None:
        await self.emit(
            "harness.compose",
            node="harness_calibrate",
            data={
                "round": round_num,
                "status": status,
                "winning_candidate_id": winning_candidate_id,
                "adopted_components": adopted_components,
                "rejected_reasons": rejected_reasons or {},
            },
        )

    async def emit_harness_distill(
        self,
        entry_id: str,
        workspace_id: str,
        components_affected: list[str],
        lesson: str,
    ) -> None:
        await self.emit(
            "harness.distill",
            node="harness_distill",
            data={
                "entry_id": entry_id,
                "workspace_id": workspace_id,
                "components_affected": components_affected,
                "lesson": lesson,
            },
        )

    async def emit_run_end(self, status: str, final_output: str | None = None, steps: int = 0) -> None:
        await self.emit("run.end", data={"status": status, "final_output": final_output, "steps": steps})
        await self.close()

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            await self._queue.put(None)

    async def stream(self) -> AsyncGenerator[str, None]:
        while True:
            try:
                event = await self._queue.get()
                if event is None:
                    break
                yield f"data: {event.model_dump_json()}\n\n"
            except asyncio.CancelledError:
                break
        yield "data: [DONE]\n\n"
