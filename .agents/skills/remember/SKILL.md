---
name: remember
description: Explicitly capture a user-stated preference, project convention, technical decision, or piece of feedback into an OKF v0.2 concept node and sync the memory index. Use when preserving persistent context with /remember.
version: 2.0.0
requires_agents: none
artifact_outputs: memory-entry
---

# /remember

$ARGUMENTS

Explicit, user-invocable capture of durable project knowledge into an atomic Google Open Knowledge Format (OKF v0.2) concept node under `.agents/memory/`, with automatic indexing into `MEMORY.md`.

## Steps

1. Take the content to remember from `$ARGUMENTS`. If ambiguous, ask the user to clarify.
2. Classify into an OKF kind: `decision`, `convention`, `preference`, or `feedback`.
3. Identify any source code anchors (`path/file.py#L1-L20`) or path glob patterns (`src/api/**/*.py`) that ground this knowledge.
4. Execute `buddhi memory add` via CLI or call `buddhi_memory(action="remember", ...)`:
   - Sets YAML frontmatter (`id`, `kind`, `title`, `summary`, `status: stable`, `confidence: verified`, `paths`, `sources`).
   - Computes SHA-256 `content_hash` for cited sources.
   - Saves atomic Markdown file under `.agents/memory/<topic>/<slug>.md`.
   - Rebuilds `<topic>/index.md` and updates root `MEMORY.md` within the 200-line budget.
   - Logs mutation into `.agents/memory/log.md`.
5. Confirm back to the user the created concept ID, file path, and summary recorded.
