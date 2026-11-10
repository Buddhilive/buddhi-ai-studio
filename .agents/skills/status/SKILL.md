---
name: status
description: Report a quick, point-in-time dashboard of this harness's own state — docs/graph staleness, open plans, memory budget & staleness, and git status — rather than live agent sessions or a preview server. Use when checking harness health and status with /status.
version: 2.0.0
requires_agents: terminal-runner
artifact_outputs: status-report
---

# /status

$ARGUMENTS

A quick dashboard of the harness's own generated state, not the project it
documents. Nothing here is written to disk.

## Steps

1. Run `buddhi docs plan` (via `terminal-runner`) — the same command
   `/document-codebase` and `/spec-plan` already run first — then read
   `.buddhi/docs-plan.json` and report its total entries and how many have
   `needs_generation: true`, i.e. how many docs are stale relative to source.
2. Check `.buddhi/graphs/` for `tree-graph.json` / `tree-graph.db`: report
   whether they exist and, if `tree-graph.json` is present, its node and edge
   counts.
3. List active feature specifications under `.buddhi/specs/`.
4. Run `buddhi memory status` (or `buddhi_memory(action="status")`) to report:
   - Total OKF concepts by kind.
   - `MEMORY.md` line count and byte size vs. the strict 200-line / 25KB cap.
   - Any stale concepts (`sources[].content_hash` mismatch).
5. Run `git branch --show-current` and `git status` (via `terminal-runner`)
   and report the current branch plus a short working-tree summary.
6. Present all of the above as one concise status report in the
   conversation.
