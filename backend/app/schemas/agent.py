from __future__ import annotations

import time
import uuid
from typing import Any, Literal
from pydantic import BaseModel, Field

from app.schemas.chat import ChatMessage, ToolCall


class PlanStep(BaseModel):
    id: str = Field(default_factory=lambda: f"step_{uuid.uuid4().hex[:8]}")
    title: str
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    details: str | None = None


AgentRunStatus = Literal["running", "completed", "max_steps_reached", "failed", "cancelled"]


class AgentRunRequest(BaseModel):
    messages: list[ChatMessage]
    model: str = "gemma-4-e4b"
    max_steps: int | None = None
    enable_thinking: bool = True
    temperature: float = 0.7
    session_id: str | None = None
    stream: bool = True


AgentEventType = Literal[
    "run.start",
    "node.start",
    "node.end",
    "reasoning.delta",
    "text.delta",
    "plan.update",
    "tool.call",
    "tool.result",
    "error",
    "run.end",
]


class AgentEvent(BaseModel):
    event: AgentEventType
    run_id: str
    node: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)

    def to_sse(self) -> str:
        return f"event: {self.event}\ndata: {self.model_dump_json()}\n\n"


class AgentRunResponse(BaseModel):
    run_id: str
    status: AgentRunStatus
    steps_taken: int
    plan: list[PlanStep] = Field(default_factory=list)
    final_output: str | None = None
    error: str | None = None
