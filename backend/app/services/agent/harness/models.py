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


class VibeStackConfig(BaseModel):
    """Canonical locked Next.js Vibe-Coding Stack configuration for an agent run."""

    framework: Literal["nextjs-16-app-router"] = "nextjs-16-app-router"
    styling: Literal["tailwindcss-v4"] = "tailwindcss-v4"
    components: Literal["shadcn-ui"] = "shadcn-ui"
    orm: Literal["drizzle-orm"] = "drizzle-orm"
    db_dialect: Literal["postgresql", "sqlite"] = "postgresql"
    database_url: str = ""
    auth_enabled: bool = True
    ai_sdk_enabled: bool = True
    local_llm_base_url: str = "http://backend:8000/v1"


class ProvisionedDatabase(BaseModel):
    """Metadata for a per-workspace provisioned Postgres or SQLite database."""

    workspace_id: str
    db_name: str
    role_name: str = ""
    dialect: Literal["postgresql", "sqlite"] = "postgresql"
    connection_env_key: str = "DATABASE_URL"
    masked_dsn: str = ""
    status: Literal["active", "fallback_sqlite", "error"] = "active"
    last_verified_at: str | None = None
    created_at: str = Field(default_factory=_utc_now_iso)


VIBE_STACK_SKILL_SUMMARIES: dict[str, str] = {
    "nextjs-app-router": "Next.js 16+ App Router, TypeScript strict mode, React 19 RSC, Server Actions, async params/cookies/headers, /_next/mcp diagnostics.",
    "tailwindcss-v4": "Tailwind CSS v4 CSS-first @import 'tailwindcss', @theme inline tokens, DESIGN.md OKLCH colors, dark mode, responsive mobile-first layout.",
    "shadcn-ui": "shadcn/ui registry components, accessible Radix/Base primitives, form/dialog/table patterns, npx shadcn@latest add.",
    "drizzle-orm": "Drizzle ORM pg-core & sqlite-core schemas, relations, prepared queries, drizzle.config.ts, and drizzle-kit push/generate/migrate.",
    "database-postgres-sqlite": "Per-workspace Postgres provisioning via provision_postgres_db, SQLite local.db fallback, and query_database verification.",
    "better-auth": "BetterAuth server config with drizzleAdapter(db, { provider }), /api/auth/[...all]/route.ts, and createAuthClient React hooks.",
    "vercel-ai-sdk": "Vercel AI SDK v7 streamText, generateText, Output.object with Zod, useChat, @ai-sdk/mcp, and local Buddhi LLM provider.",
}


def default_vibe_harness_components() -> HarnessComponents:
    """Return the default Harness2 scaffolding locked to the Next.js Vibe-Coding Stack."""
    return HarnessComponents(
        system_prompt=(
            "Locked Stack: Next.js 16+ App Router (TypeScript), Tailwind CSS v4 (@theme OKLCH), "
            "shadcn/ui, Drizzle ORM, PostgreSQL (default) or SQLite, BetterAuth, and Vercel AI SDK."
        ),
        guardrails=(
            "Never create pages/ or src/pages/ routes, tailwind.config.js v3 files, or install "
            "competing ORMs/auth/UI libs (prisma, typeorm, next-auth, mui, bootstrap)."
        ),
        tool_guidance=(
            "Use search_web and crawl_url for live docs; provision_postgres_db before Drizzle push; "
            "load_skill(skill_name) for detailed framework runbooks; nextjs_devtools for typecheck."
        ),
        skills=dict(VIBE_STACK_SKILL_SUMMARIES),
    )
