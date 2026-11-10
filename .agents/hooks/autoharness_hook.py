#!/usr/bin/env python3
"""Antigravity lifecycle hook: autoharness_hook.py

Handles SessionStart, PreToolUse, and Stop events in Google Antigravity:
- SessionStart: evaluates lifecycle graduation/eviction, consumes last_run.json, injects recall index via injectSteps.
- PreToolUse: tracks skill use and views; blocks child reflection/curation subagents from writing directly.
- Stop: drains interactive intent queue and provides threshold notifications.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _resolve_project_root() -> Path:
    curr = Path.cwd().resolve()
    while curr != curr.parent:
        if (curr / ".agents").is_dir() or (curr / ".git").is_dir():
            return curr
        curr = curr.parent
    return Path.cwd().resolve()


def handle_session_start(root: Path, payload: dict) -> dict:
    """Handle SessionStart event: run lifecycle evaluation and inject skill recall index."""
    from buddhi.scripts.autoharness.layer import (
        resolve_autoharness_dir,
        resolve_skills_dir,
    )
    from buddhi.scripts.autoharness.lifecycle import evaluate_lifecycle
    from buddhi.scripts.autoharness.sidecar import is_agent_created, read_sidecar
    from buddhi.scripts.autoharness.skill_store import archive_skill
    from buddhi.scripts.autoharness.validate import parse_frontmatter

    skills_dir = resolve_skills_dir("project", root)
    if not skills_dir.is_dir():
        return {}

    # Read active agent skills
    agent_skills = {}
    for item in skills_dir.iterdir():
        if item.is_dir() and is_agent_created(item):
            sc = read_sidecar(item)
            if sc:
                agent_skills[item.name] = sc

    # Evaluate lifecycle
    decision = evaluate_lifecycle(
        agent_skills, current_request_count=100, layer="project"
    )
    for arch in decision.archive:
        try:
            archive_skill(skills_dir, arch)
        except OSError:
            pass

    # Build recall index
    categories: dict[str, list[str]] = {}
    for name in decision.keep:
        s_file = skills_dir / name / "SKILL.md"
        if s_file.is_file():
            try:
                fm, _ = parse_frontmatter(s_file.read_text(encoding="utf-8"))
                cat = fm.get("category", "general")
                desc = fm.get("description", "")[:60]
                categories.setdefault(cat, []).append(f"- {name} [project]: {desc}")
            except (OSError, ValueError):
                pass

    index_lines = ["[AutoHarness] Active Self-Learned Skills:"]
    for cat, items in sorted(categories.items()):
        index_lines.append(f"## {cat}")
        index_lines.extend(items)

    index_text = "\n".join(index_lines)

    # Consume last_run.json if present
    autoharness_dir = resolve_autoharness_dir("project", root)
    last_run_file = autoharness_dir / "last_run.json"
    last_run_summary = ""
    if last_run_file.is_file():
        try:
            data = json.loads(last_run_file.read_text(encoding="utf-8"))
            landed = len(data.get("landed", []))
            rejected = len(data.get("rejected", []))
            last_run_summary = f"[AutoHarness] Last promotion: landed {landed}, rejected {rejected} skills."
        except (OSError, json.JSONDecodeError):
            pass

    messages = []
    if last_run_summary:
        messages.append(last_run_summary)
    if len(categories) > 0:
        messages.append(index_text)

    if messages:
        return {
            "injectSteps": [{"systemMessage": {"systemMessage": "\n\n".join(messages)}}]
        }
    return {}


def handle_pre_tool_use(root: Path, payload: dict) -> dict:
    """Handle PreToolUse: block child subagent direct writes and bump usage counters."""
    tool_call = payload.get("toolCall", {})
    tool_name = tool_call.get("name", "")

    # Child session write guard
    is_child = os.environ.get("AUTOHARNESS_CHILD_SESSION") == "1" or payload.get(
        "subagent"
    ) in ("reflector", "curator")
    if is_child and tool_name in ("write_file", "edit_file", "Write", "Edit"):
        return {
            "decision": "deny",
            "reason": "AutoHarness reflection/curation subagents are read-only and must propose mutations via stage_skill.",
        }

    # Usage tracking
    args = tool_call.get("args", {})
    file_path = args.get("Path", args.get("filepath", args.get("file_path", "")))
    if file_path and ".agents/skills/" in str(file_path).replace("\\", "/"):
        from buddhi.scripts.autoharness.layer import resolve_skills_dir
        from buddhi.scripts.autoharness.sidecar import (
            bump_sidecar_counter,
            is_agent_created,
        )

        skills_dir = resolve_skills_dir("project", root)
        norm_p = Path(file_path)
        try:
            rel = norm_p.relative_to(skills_dir)
            skill_name = rel.parts[0]
            target_skill_dir = skills_dir / skill_name
            if target_skill_dir.is_dir() and is_agent_created(target_skill_dir):
                counter = "use" if rel.name == "SKILL.md" else "view"
                bump_sidecar_counter(target_skill_dir, counter)
        except (OSError, ValueError):
            pass

    return {"decision": "allow"}


def handle_stop(root: Path, payload: dict) -> dict:
    """Handle Stop event: drain interactive intents and notify if thresholds reached."""
    from buddhi.scripts.autoharness.promoter import drain_and_promote

    try:
        drain_and_promote(layer="project", run_id="interactive", project_root=root)
    except (OSError, ValueError):
        pass

    return {}


def main() -> None:
    try:
        raw = sys.stdin.read(262144)
        payload = json.loads(raw) if raw.strip() else {}
    except (OSError, json.JSONDecodeError):
        payload = {}

    root = _resolve_project_root()
    res: dict = {}

    try:
        # Detect event type
        if (
            "conversationId" in payload
            and "toolCall" not in payload
            and "terminationReason" not in payload
        ):
            res = handle_session_start(root, payload)
        elif "toolCall" in payload:
            res = handle_pre_tool_use(root, payload)
        elif "terminationReason" in payload or "executionNum" in payload:
            res = handle_stop(root, payload)
        else:
            # Fallback
            res = {"decision": "allow"}
    except (OSError, ValueError):
        # Fail open
        res = {"decision": "allow"}

    print(json.dumps(res))


if __name__ == "__main__":
    main()
