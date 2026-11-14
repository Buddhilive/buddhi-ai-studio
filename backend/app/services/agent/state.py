from __future__ import annotations

from typing import Annotated, Any, Literal
from typing_extensions import TypedDict

from app.schemas.agent import AgentRunStatus, PlanStep
from app.schemas.chat import ChatMessage, ToolCall


def append_list(current: list[Any] | None, new: list[Any] | None) -> list[Any]:
    curr = current or []
    if not new:
        return curr
    return curr + new


def replace_or_update(current: Any, new: Any) -> Any:
    return new if new is not None else current


class Observation(TypedDict, total=False):
    tool_call_id: str
    name: str
    status: Literal["completed", "error", "timeout"]
    output: str
    exit_code: int
    truncated: bool


class AgentState(TypedDict, total=False):
    run_id: str
    messages: list[ChatMessage]
    plan: list[PlanStep]
    pending_tool_calls: list[ToolCall]
    observations: Annotated[list[Observation], append_list]
    verdict: Literal["pass", "retry", "continue"] | None
    step: int
    max_steps: int
    recent_actions: Annotated[list[str], append_list]
    status: AgentRunStatus
    session_id: str | None
    final_output: str | None
    error: str | None
    is_rlm_mode: bool
    rlm_telemetry: dict[str, Any] | None

    # EGM (Elephant-Goldfish Model) extensions
    is_egm_mode: bool
    egm_skill_mode: Literal["standard", "brainstorm", "bootstrap", "drift_report"]
    egm_phase: Literal["brainstorm", "draft", "goldfish_review", "resolve", "act", "goldfish_verify", "drift_report"] | None
    egm_round: int
    egm_max_rounds: int
    egm_approved: bool
    spec_contract: dict[str, Any] | None
    review_report: dict[str, Any] | None
    resolution_decisions: list[dict[str, Any]]
    allowed_write_paths: list[str]
    egm_artifacts: dict[str, str]
    concepts_brief: str | None
    drift_report: str | None
