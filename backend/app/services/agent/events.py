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
