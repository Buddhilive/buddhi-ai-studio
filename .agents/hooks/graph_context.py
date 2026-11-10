#!/usr/bin/env python3
"""Mechanical PreToolUse & SessionStart hook: graph_context.py

Provides fast (<50ms, stdlib only, fail-open) context injection:
- SessionStart: detects git staleness between tree-graph.db built_at_commit and HEAD.
- PreToolUse: injects file symbol summary, community label, caller/callee counts, and active OKF memory nodes.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


def _resolve_db_path(root: Path) -> Path | None:
    candidate = root / ".buddhi" / "graphs" / "tree-graph.db"
    return candidate if candidate.is_file() else None


def _handle_session_start(root: Path, db_path: Path | None) -> dict:
    if not db_path:
        return {}

    built_commit: str | None = None
    try:
        conn = sqlite3.connect(
            f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=0.03
        )
        try:
            cur = conn.cursor()
            cur.execute("SELECT value FROM meta WHERE key = 'built_at_commit'")
            row = cur.fetchone()
            if row and row[0]:
                built_commit = row[0]
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        return {}

    if not built_commit:
        return {}

    # Check git HEAD
    git_head: str | None = None
    git_head_file = root / ".git" / "HEAD"
    if git_head_file.is_file():
        try:
            head_content = git_head_file.read_text(encoding="utf-8").strip()
            if not head_content.startswith("ref:"):
                git_head = head_content
            else:
                ref_file = root / ".git" / head_content[4:].strip()
                if ref_file.is_file():
                    git_head = ref_file.read_text(encoding="utf-8").strip()
        except OSError:
            pass

    if git_head and built_commit != git_head:
        return {
            "additionalContext": f"[Buddhi Graph] tree-graph.db was built at commit {built_commit[:8]} (HEAD is {git_head[:8]}). Consider running `buddhi generate` to refresh."
        }

    return {}


def _extract_target_file(payload: dict, root: Path) -> str | None:
    candidates: list[str] = []
    for key in (
        "file_path",
        "filepath",
        "AbsolutePath",
        "TargetFile",
        "path",
        "SearchPath",
    ):
        val = payload.get(key)
        if isinstance(val, str):
            candidates.append(val)

    for outer in ("input", "tool_input", "parameters"):
        inner_obj = payload.get(outer)
        if isinstance(inner_obj, dict):
            for key in (
                "file_path",
                "filepath",
                "AbsolutePath",
                "TargetFile",
                "path",
                "SearchPath",
            ):
                val = inner_obj.get(key)
                if isinstance(val, str):
                    candidates.append(val)

    for raw in candidates:
        norm = raw.replace("\\", "/").strip()
        try:
            cand_p = (root / norm).resolve()
            if cand_p.is_relative_to(root):
                rel = cand_p.relative_to(root).as_posix()
                if not any(
                    rel.startswith(ex)
                    for ex in (".git/", ".buddhi/", ".venv/", "node_modules/", "temp/")
                ):
                    return rel
        except (ValueError, OSError):
            continue
    return None


def _handle_pre_tool_use(root: Path, db_path: Path | None, payload: dict) -> dict:
    target_rel = _extract_target_file(payload, root)
    if not target_rel or not db_path:
        return {"decision": "allow"}

    try:
        conn = sqlite3.connect(
            f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=0.03
        )
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    n.name, n.kind, n.community_id, c.label, c.cohesion,
                    (SELECT COUNT(*) FROM edges e WHERE e.target_id = n.id AND e.kind IN ('calls', 'inherits')) AS in_deg,
                    (SELECT COUNT(*) FROM edges e WHERE e.source_id = n.id AND e.kind IN ('calls', 'inherits')) AS out_deg
                FROM nodes n
                LEFT JOIN communities c ON c.id = n.community_id
                WHERE n.file_path = ? AND n.kind IN ('class', 'function', 'method')
                ORDER BY in_deg DESC, n.start_line ASC
                LIMIT 8
                """,
                (target_rel,),
            )
            rows = cur.fetchall()
            if not rows:
                return {"decision": "allow"}

            comm_label = (
                rows[0][3] or f"Community {rows[0][2]}"
                if rows[0][2] is not None
                else "unclustered"
            )
            cohesion = rows[0][4] if rows[0][4] is not None else 0.0
            top_symbols = [f"{r[0]} ({r[1]}, in:{r[5]}, out:{r[6]})" for r in rows[:4]]

            hint = f"[Buddhi Graph] {target_rel}: {len(rows)} symbols | Community: '{comm_label}' (cohesion {cohesion}) | Symbols: {', '.join(top_symbols)}"
            return {"decision": "allow", "additionalContext": hint}
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        return {"decision": "allow"}


def main() -> None:
    try:
        raw = sys.stdin.read(262144)
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError, ValueError):
        payload = {}

    root = Path.cwd().resolve()
    db_path = _resolve_db_path(root)

    # Detect if SessionStart or PreToolUse
    event_name = payload.get("hook_event_name", "")
    if (
        event_name == "SessionStart"
        or "session_id" in payload
        and "tool_name" not in payload
    ):
        res = _handle_session_start(root, db_path)
    else:
        res = _handle_pre_tool_use(root, db_path, payload)

    print(json.dumps(res))


if __name__ == "__main__":
    main()
