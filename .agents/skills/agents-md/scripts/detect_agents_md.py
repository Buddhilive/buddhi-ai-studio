#!/usr/bin/env python3
"""Cross-platform repository facts detector and AGENTS.md updater.

Usage:
    python scripts/detect_agents_md.py [--root PATH] [--diff] [--apply] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Try importing from buddhi package; fall back to relative path if run inside repo
try:
    from buddhi.skills.agents_md import (
        detect_repo_facts,
        diff_agents_md,
        generate_agents_md,
        merge_agents_md,
    )
except ImportError:
    # If buddhi is not in sys.path, search upwards for src
    current = Path(__file__).resolve()
    for parent in current.parents:
        src_candidate = parent / "src"
        if (src_candidate / "buddhi").is_dir():
            sys.path.insert(0, str(src_candidate))
            break
    from buddhi.skills.agents_md import (
        detect_repo_facts,
        diff_agents_md,
        generate_agents_md,
        merge_agents_md,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect repository facts and create or update AGENTS.md."
    )
    parser.add_argument(
        "--root",
        "-r",
        type=Path,
        default=Path("."),
        help="Project root directory (default: current directory).",
    )
    parser.add_argument(
        "--diff",
        "-d",
        action="store_true",
        help="Display unified diff against existing AGENTS.md without modifying it.",
    )
    parser.add_argument(
        "--apply",
        "-a",
        action="store_true",
        help="Apply changes and write AGENTS.md directly.",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output detected facts and merge results as JSON.",
    )

    args = parser.parse_args()
    root = args.root.resolve()

    if not root.is_dir():
        print(f"Error: target root '{root}' is not a directory.", file=sys.stderr)
        return 1

    agents_md_path = root / "AGENTS.md"
    facts = detect_repo_facts(root)

    existing_content = ""
    is_new = not agents_md_path.is_file()
    if not is_new:
        try:
            existing_content = agents_md_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"Error reading {agents_md_path}: {exc}", file=sys.stderr)
            return 1

    if is_new:
        generated_content = generate_agents_md(facts)
        has_changes = True
        diff_output = diff_agents_md("", generated_content)
        updated_sections = [
            "# AGENTS.md",
            "## Commands",
            "## Agent Conventions & Skills",
        ]
        preserved_sections: list[str] = []
        final_content = generated_content
    else:
        merge_res = merge_agents_md(existing_content, facts)
        has_changes = merge_res.has_changes
        diff_output = merge_res.diff
        updated_sections = merge_res.updated_sections
        preserved_sections = merge_res.preserved_sections
        final_content = merge_res.content

    if args.json:
        payload = {
            "root": str(root),
            "is_new": is_new,
            "has_changes": has_changes,
            "facts": {
                "name": facts.name,
                "description": facts.description,
                "primary_language": facts.primary_language,
                "commands": facts.commands.as_dict(),
                "skills": facts.skills,
                "has_rules": facts.has_rules,
                "has_buddhi_docs": facts.has_buddhi_docs,
            },
            "updated_sections": updated_sections,
            "preserved_sections": preserved_sections,
            "diff": diff_output,
        }
        print(json.dumps(payload, indent=2))
        return 0

    if args.apply:
        try:
            agents_md_path.write_text(final_content, encoding="utf-8")
            status_str = "Created" if is_new else "Updated"
            print(f"{status_str} {agents_md_path} successfully.")
            return 0
        except OSError as exc:
            print(f"Error writing {agents_md_path}: {exc}", file=sys.stderr)
            return 1

    if args.diff:
        if is_new:
            print(f"--- /dev/null\n+++ {agents_md_path}\n")
            print(final_content)
        elif has_changes:
            print(diff_output)
        else:
            print("AGENTS.md is up-to-date. Zero changes needed.")
        return 0

    # Default summary mode
    print(f"Target: {root}")
    print(f"Primary Language: {facts.primary_language}")
    print("Commands Detected:")
    for k, v in facts.commands.as_dict().items():
        if v:
            print(f"  - {k.capitalize()}: {v}")
    if is_new:
        print(
            "\nAGENTS.md does not exist. Run with --apply to create it, or --diff to preview."
        )
    elif has_changes:
        print(
            "\nChanges detected in AGENTS.md. Run with --diff to inspect, or --apply to update."
        )
    else:
        print("\nAGENTS.md is up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
