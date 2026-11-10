---
name: memory
description: "Inspect, validate, compact, search, and manage project and subagent OKF v0.2 memory concepts. Use when viewing memory status or auditing staleness with /memory."
version: 1.0.0
requires_agents: none
artifact_outputs: memory-status
---

# /memory

$ARGUMENTS

Inspect and manage the project's Google Open Knowledge Format (OKF v0.2) and Claude Code memory bundle.

## Steps

1. Parse any subcommands or filters from `$ARGUMENTS` (`status`, `search <query>`, `validate`, `compact`, `sync`, `sdd-promote`).
2. Default to status: run `buddhi memory status` (or call `buddhi_memory(action="status")`) to report:
   - Total OKF concept nodes by kind and scope.
   - `MEMORY.md` line count and byte size vs. the strict 200-line / 25KB hard cap.
   - Any stale concepts where referenced source code has changed (`content_hash` mismatch).
3. If `--validate` or `validate` was requested: run `buddhi memory validate`.
4. If `--compact` or `compact` was requested: run `buddhi memory compact` to demote superseded/deprecated pointers to `<topic>/index.md`.
5. If `search` was requested: execute `buddhi memory search <query> [--active-file <files>]`.
6. Present findings concisely to the user.
