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


AgentRunStatus = Literal[
    "running",
    "awaiting_approval",
    "needs_human",
    "completed",
    "max_steps_reached",
    "failed",
    "cancelled",
]


class SpecContract(BaseModel):
    path: str
    content: str
    feature_range: tuple[int, int] = (0, 0)
    detailed_range: tuple[int, int] = (0, 0)
    target_scope_files: list[str] = Field(default_factory=list)
    approved: bool = False


class Finding(BaseModel):
    id: str = Field(default_factory=lambda: f"F-{uuid.uuid4().hex[:6].upper()}")
    lens: str
    severity: Literal["blocker", "major", "nit"]
    scope: str
    description: str
    recommendation: str
    decision: Literal["accept", "reject", "defer"] | None = None
    rationale: str | None = None


class ReviewReport(BaseModel):
    round: int = 1
    artifact_path: str = ""
    reviewer_statuses: dict[str, Literal["running", "retrying", "completed", "not run"]] = Field(
        default_factory=dict
    )
    findings: list[Finding] = Field(default_factory=list)


class ResolutionDecision(BaseModel):
    finding_id: str
    decision: Literal["accept", "reject", "defer"]
    rationale: str | None = None
    approve_plan: bool = False


class EgmResolveRequest(BaseModel):
    decisions: list[ResolutionDecision] = Field(default_factory=list)
    edited_spec_content: str | None = None
    approve_for_implementation: bool = False


class EgmArtifactsResponse(BaseModel):
    run_id: str
    status: AgentRunStatus
    egm_phase: str | None = None
    egm_round: int = 1
    spec_contract: SpecContract | None = None
    review_report: ReviewReport | None = None
    concepts_brief: str | None = None
    drift_report: str | None = None


class AgentRunRequest(BaseModel):
    messages: list[ChatMessage]
    model: str = "gemma-4-e4b"
    max_steps: int | None = None
    enable_thinking: bool = True
    temperature: float = 0.7
    session_id: str | None = None
    stream: bool = True
    egm_mode: bool | None = None
    egm_skill_mode: Literal["standard", "brainstorm", "bootstrap", "drift_report"] = "standard"
    egm_max_rounds: int | None = None
    spec_path: str | None = None


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
    "egm.phase",
    "egm.reviewer.status",
    "egm.artifact",
    "egm.gate.pause",
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
