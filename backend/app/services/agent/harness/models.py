from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field

HARNESS_COMPONENT_KEYS: tuple[str, ...] = (
    "system_prompt",
    "guardrails",
    "memory",
    "tool_guidance",
    "subagents",
    "skills",
    "scripts",
    "plugins",
)

HarnessComponentName = Literal[
    "system_prompt",
    "guardrails",
    "memory",
    "tool_guidance",
    "subagents",
    "skills",
    "scripts",
    "plugins",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class HarnessComponents(BaseModel):
    """The 8 editable Harness2 scaffolding components around the frozen model."""

    system_prompt: str = ""
    guardrails: str = ""
    memory: str = ""
    tool_guidance: str = ""
    subagents: str = ""
    skills: dict[str, str] = Field(default_factory=dict)
    scripts: dict[str, str] = Field(default_factory=dict)
    plugins: list[dict[str, Any]] = Field(default_factory=list)

    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class HarnessOverlay(BaseModel):
    """Versioned Harness2 overlay snapshot for a workspace."""

    version_id: str
    workspace_id: str
    parent_version_id: str | None = None
    components: HarnessComponents = Field(default_factory=HarnessComponents)
    is_active: bool = True
    is_pinned: bool = False
    source_run_id: str | None = None
    created_at: str = Field(default_factory=_utc_now_iso)

    @property
    def content_hash(self) -> str:
        return self.components.content_hash()


class OverlayDiff(BaseModel):
    """Candidate edits proposed by Propose for one or more of the 8 components."""

    candidate_id: str
    rationale: str = ""
    updates: dict[HarnessComponentName, Any] = Field(default_factory=dict)


class ProbeResult(BaseModel):
    """Outcome and telemetry of executing a single candidate harness probe."""

    probe_id: str
    calibration_id: str = ""
    workspace_id: str = ""
    candidate_id: str
    target_components: list[str] = Field(default_factory=list)
    status: Literal["passed", "failed", "timed_out", "guardrail_blocked"]
    steps_taken: int = 0
    tool_error_count: int = 0
    test_pass_rate: float = 0.0
    wall_clock_ms: int = 0
    trajectory_summary: str = ""
    guardrail_violations: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_utc_now_iso)


class ExperienceEntry(BaseModel):
    """Level 2 cross-task improvement lesson distilled from verified runs."""

    entry_id: str
    workspace_id: str
    task_signature: str
    lesson: str
    evidence_run_id: str
    components_affected: list[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.7, ge=0.0, le=1.0)
    hit_count: int = 0
    is_pinned: bool = False
    is_active: bool = True
    created_at: str = Field(default_factory=_utc_now_iso)
    last_used_at: str | None = None


class CalibrationReport(BaseModel):
    """Summary of a Level 1 Propose -> Probe -> Compose cycle."""

    calibration_id: str
    workspace_id: str
    run_id: str
    round: int = 1
    trigger_reason: str
    baseline_overlay_id: str | None = None
    baseline_score: float = 0.0
    winning_candidate_id: str | None = None
    adopted_overlay_id: str | None = None
    status: Literal["adopted", "no_improvement", "rejected", "error"]
    adopted_components: list[str] = Field(default_factory=list)
    rejected_reasons: dict[str, str] = Field(default_factory=dict)
    rlm_used: bool = False
    probes: list[ProbeResult] = Field(default_factory=list)
    created_at: str = Field(default_factory=_utc_now_iso)
