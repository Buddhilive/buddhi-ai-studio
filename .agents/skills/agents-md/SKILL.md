---
name: agents-md
description: Inspect repository manifests, build tools, and agent workflows to generate or update a concise AGENTS.md (~12 lines) without overwriting custom sections. Use when creating or updating AGENTS.md, or when project build/test commands have changed.
---

# /agents-md

Create or update the repository's `AGENTS.md` file using real project manifests and evidence.

The `AGENTS.md` file gives coding agents operational context on dev environment setup, build, test, and lint commands, and points to granular skills and docs. Research by the Agentic AI Foundation (July 2026) showed that including a concise `AGENTS.md` eliminates worst-case command failure loops, reducing diff sizes by 26%, wall clock time by 27%, and tokens by 25%.

The core principle is **brevity**: keep the top-level `AGENTS.md` concise (~12 lines). Granular runbooks belong in `.agents/skills/` and codebase architecture in `.buddhi/docs/`.

## Steps

1. **Inspect and Compute Diff**:
   Run the detection helper with `--diff` via the `terminal-runner` agent:
   ```bash
   python .agents/skills/agents-md/scripts/detect_agents_md.py --diff
   ```
   Or examine detected facts in JSON mode:
   ```bash
   python .agents/skills/agents-md/scripts/detect_agents_md.py --json
   ```

2. **Review Proposed Changes**:
   - Verify that all detected commands (`install`, `build`, `test`, `lint`, `typecheck`) trace to actual manifests (`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `Makefile`, etc.).
   - Verify that the core block stays within ~12-15 lines.
   - If `AGENTS.md` already exists, confirm that all hand-crafted custom sections (e.g. `## Engineering Principles & Non-Negotiables`) are preserved byte-for-byte in the diff.

3. **Apply Changes**:
   Once confirmed by the user, apply the changes:
   ```bash
   python .agents/skills/agents-md/scripts/detect_agents_md.py --apply
   ```

4. **Principles Audit (Optional)**:
   If the user wants to audit principles in an existing `AGENTS.md` for 100-year endurance, hand off to `/audit-agents`.
