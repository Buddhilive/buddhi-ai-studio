from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.core.config import BACKEND_ROOT, settings
from app.schemas.chat import FunctionDefinition, ToolDefinition

logger = logging.getLogger(__name__)

_SKILLS_ROOT = BACKEND_ROOT.parent / ".agents" / "skills"

VIBE_SKILL_NAMES: tuple[str, ...] = (
    "nextjs-app-router",
    "tailwindcss-v4",
    "shadcn-ui",
    "drizzle-orm",
    "database-postgres-sqlite",
    "better-auth",
    "vercel-ai-sdk",
)

_SKILL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "better-auth": ("auth", "login", "signup", "sign-in", "session", "password", "oauth", "user"),
    "drizzle-orm": ("db", "database", "schema", "table", "drizzle", "migration", "sql", "crud", "record"),
    "database-postgres-sqlite": ("postgres", "postgresql", "sqlite", "database", "db", "provision", "query"),
    "vercel-ai-sdk": ("ai", "chat", "llm", "stream", "agent", "copilot", "completion", "rag", "mcp"),
    "shadcn-ui": ("ui", "component", "form", "dialog", "modal", "table", "button", "card", "dashboard", "tabs"),
    "tailwindcss-v4": ("style", "css", "tailwind", "theme", "dark", "responsive", "layout", "color"),
    "nextjs-app-router": ("next", "route", "page", "app", "server action", "api"),
}

LOAD_SKILL_TOOL_DEFINITION = ToolDefinition(
    type="function",
    function=FunctionDefinition(
        name="load_skill",
        description=(
            "Load the full official runbook for one of the 7 locked Next.js Vibe-Stack skills: "
            + ", ".join(VIBE_SKILL_NAMES)
            + "."
        ),
        parameters={
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "enum": list(VIBE_SKILL_NAMES),
                    "description": "Name of the stack skill to load.",
                }
            },
            "required": ["skill_name"],
        },
    ),
)


def read_skill_markdown(skill_name: str) -> str | None:
    """Read a canonical Vibe-Stack SKILL.md from .agents/skills/<skill_name>/SKILL.md."""
    if skill_name not in VIBE_SKILL_NAMES:
        return None
    path = _SKILLS_ROOT / skill_name / "SKILL.md"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()


def select_skills_for_task(
    task_text: str,
    token_budget: int | None = None,
) -> str:
    """Select and pack task-relevant Vibe-Stack skills within the token budget."""
    budget_tokens = token_budget if token_budget is not None else settings.harness_experience_token_budget
    max_chars = max(1000, budget_tokens * 4)
    lowered = task_text.lower()

    scored: list[tuple[int, str]] = []
    for name in VIBE_SKILL_NAMES:
        hits = sum(1 for kw in _SKILL_KEYWORDS.get(name, ()) if kw in lowered)
        if hits > 0:
            scored.append((hits, name))

    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    chosen = [name for _, name in scored]
    if "nextjs-app-router" not in chosen:
        chosen.insert(0, "nextjs-app-router")

    blocks: list[str] = []
    used_chars = 0
    for name in chosen:
        content = read_skill_markdown(name)
        if not content:
            continue
        block = f"#### SKILL: {name}\n{content}"
        if used_chars + len(block) > max_chars and blocks:
            break
        blocks.append(block)
        used_chars += len(block)

    if not blocks:
        return ""
    return (
        "### LOADED STACK RUNBOOKS (Call `load_skill(skill_name)` for other skills on demand)\n"
        + "\n\n".join(blocks)
    )


async def execute_load_skill(args: dict[str, Any]) -> tuple[str, str, int, bool]:
    """Tool handler for load_skill(skill_name)."""
    skill_name = str(args.get("skill_name") or "").strip()
    if skill_name not in VIBE_SKILL_NAMES:
        return (
            "error",
            f"Unknown skill '{skill_name}'. Valid skills: {', '.join(VIBE_SKILL_NAMES)}.",
            1,
            False,
        )
    content = read_skill_markdown(skill_name)
    if not content:
        return "error", f"Skill file for '{skill_name}' not found under .agents/skills/.", 1, False
    return "completed", content, 0, False
