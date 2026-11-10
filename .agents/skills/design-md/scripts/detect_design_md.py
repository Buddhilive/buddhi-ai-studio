#!/usr/bin/env python3
"""Cross-platform repository design facts detector, DESIGN.md generator and linter.

Usage:
    python scripts/detect_design_md.py [--root PATH] [--diff] [--apply] [--lint] [--json] [--aesthetic PROSE]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Try importing from buddhi package; fall back to relative path if run inside repo
try:
    from buddhi.skills.design_md import (
        detect_design_facts,
        diff_design_md,
        generate_design_md,
        lint_design_md,
        merge_design_md,
    )
except ImportError:
    # If buddhi is not in sys.path, search upwards for src
    current = Path(__file__).resolve()
    for parent in current.parents:
        src_candidate = parent / "src"
        if (src_candidate / "buddhi").is_dir():
            sys.path.insert(0, str(src_candidate))
            break
    from buddhi.skills.design_md import (
        detect_design_facts,
        diff_design_md,
        generate_design_md,
        lint_design_md,
        merge_design_md,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect repository facts, create or update DESIGN.md, and run WCAG contrast linting."
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
        help="Display unified diff against existing DESIGN.md without modifying it.",
    )
    parser.add_argument(
        "--apply",
        "-a",
        action="store_true",
        help="Apply changes and write DESIGN.md directly to project root.",
    )
    parser.add_argument(
        "--lint",
        "-l",
        action="store_true",
        help="Validate DESIGN.md structure and run WCAG 2.2 AA color contrast checks.",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output detected facts, tokens, and lint results as structured JSON.",
    )
    parser.add_argument(
        "--aesthetic",
        "-e",
        type=str,
        default=None,
        help="Custom vivid aesthetic direction prose description for ## Overview.",
    )

    args = parser.parse_args()
    root = args.root.resolve()

    if not root.is_dir():
        print(f"Error: target root '{root}' is not a directory.", file=sys.stderr)
        return 1

    design_md_path = root / "DESIGN.md"
    facts = detect_design_facts(root)

    existing_content = ""
    is_new = not design_md_path.is_file()
    if not is_new:
        try:
            existing_content = design_md_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"Error reading {design_md_path}: {exc}", file=sys.stderr)
            return 1

    if is_new:
        generated_content = generate_design_md(facts, aesthetic=args.aesthetic)
        has_changes = True
        diff_output = diff_design_md("", generated_content)
        updated_sections = ["All sections (new file)"]
        preserved_sections: list[str] = []
        final_content = generated_content
    else:
        merge_res = merge_design_md(existing_content, facts, aesthetic=args.aesthetic)
        has_changes = merge_res.has_changes
        diff_output = merge_res.diff
        updated_sections = merge_res.updated_sections
        preserved_sections = merge_res.preserved_sections
        final_content = merge_res.content

    # If --lint is requested, validate final content (or existing file)
    lint_report = lint_design_md(
        existing_content
        if (args.lint and not args.apply and not is_new)
        else final_content
    )

    if args.json:
        payload = {
            "root": str(root),
            "is_new": is_new,
            "has_changes": has_changes,
            "has_ui_surface": facts.has_ui_surface,
            "framework": facts.framework,
            "source_files": facts.source_files,
            "tokens": facts.tokens.as_dict(),
            "updated_sections": updated_sections,
            "preserved_sections": preserved_sections,
            "diff": diff_output,
            "lint": {
                "is_valid": lint_report.is_valid,
                "errors": lint_report.errors,
                "warnings": lint_report.warnings,
                "missing_sections": lint_report.missing_sections,
                "contrast_findings": [
                    {
                        "fg": f"{f.fg_key} ({f.fg_hex})",
                        "bg": f"{f.bg_key} ({f.bg_hex})",
                        "ratio": f"{f.ratio}:1",
                        "status": f.status,
                        "notes": f.notes,
                    }
                    for f in lint_report.contrast_findings
                ],
            },
        }
        print(json.dumps(payload, indent=2))
        return 0 if (not args.lint or lint_report.is_valid) else 1

    if args.lint:
        print(f"Linting {design_md_path.name} in {root}:")
        if lint_report.warnings:
            for w in lint_report.warnings:
                print(f"  [WARN] {w}")
        for cf in lint_report.contrast_findings:
            mark = (
                "PASS"
                if cf.status == "PASS"
                else "FAIL"
                if cf.status == "FAIL"
                else "SKIP"
            )
            print(
                f"  [{mark}] {cf.fg_key} ({cf.fg_hex}) on {cf.bg_key} ({cf.bg_hex}) -> {cf.ratio}:1"
            )
        if not lint_report.is_valid:
            print("\nErrors:")
            for err in lint_report.errors:
                print(f"  [ERROR] {err}")
            return 1
        print("\nDESIGN.md passed all structural and WCAG 2.2 AA contrast checks.")
        return 0

    if args.apply:
        try:
            design_md_path.write_text(final_content, encoding="utf-8")
            status_str = "Created" if is_new else "Updated"
            print(f"{status_str} {design_md_path} successfully.")
            return 0
        except OSError as exc:
            print(f"Error writing {design_md_path}: {exc}", file=sys.stderr)
            return 1

    if args.diff:
        if is_new:
            print(f"--- /dev/null\n+++ {design_md_path}\n")
            print(final_content)
        elif has_changes:
            print(diff_output)
        else:
            print("DESIGN.md is up-to-date. Zero changes needed.")
        return 0

    # Default summary mode
    print(f"Target: {root}")
    print(
        f"UI Surface Detected: {facts.has_ui_surface} (framework: {facts.framework or 'generic'})"
    )
    print(
        f"Source Files Found: {', '.join(facts.source_files) if facts.source_files else 'None'}"
    )
    print(f"Color Tokens Extracted: {len(facts.tokens.colors)}")
    if is_new:
        print(
            "\nDESIGN.md does not exist. Run with --apply to create it, or --diff to preview."
        )
    elif has_changes:
        print(
            "\nChanges detected in design system tokens. Run with --diff to inspect, or --apply to update."
        )
    else:
        print("\nDESIGN.md is up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
