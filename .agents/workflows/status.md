---
name: status
description: Report a quick, point-in-time dashboard of this harness's own state — docs/graph staleness, open plans, memory size, and git status — rather than live agent sessions or a preview server.
version: 1.0.0
requires_agents: terminal-runner
artifact_outputs: status-report
---

# /status

$ARGUMENTS

A quick dashboard of the harness's own generated state, not the project it
documents. Nothing here is written to disk.

## Steps

1. Run `buddhi docs plan` (via `terminal-runner`) — the same command
   `/document-codebase` and `/plan` already run first — then read
   `.buddhi/docs-plan.json` and report its total entries and how many have
   `needs_generation: true`, i.e. how many docs are stale relative to source.
2. Check `.buddhi/graphs/` for `tree-graph.json` / `tree-graph.db`: report
   whether they exist and, if `tree-graph.json` is present, its node and edge
   counts. Buddhi has no separate staleness flag for the graph, so report
   presence and size only — don't invent a heuristic that doesn't exist
   elsewhere in this codebase.
3. List filenames under `.buddhi/plans/` (created by `/plan`'s final step),
   if the directory exists.
4. Report `.agents/memory/MEMORY.md`'s size in lines and its most recent few
   index entries, so the user can see how close it is to the ~200-line cap
   from this harness's memory conventions.
5. Run `git branch --show-current` and `git status` (via `terminal-runner`)
   and report the current branch plus a short working-tree summary.
6. Present all of the above as one concise status report in the
   conversation — unlike `/plan`'s artifact, nothing is written to a file.
