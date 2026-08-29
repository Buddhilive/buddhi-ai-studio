---
name: debug
description: Systematically investigate a bug, error, or unexpected-behavior report, grounded in this codebase's actual docs and code graph, and produce a confirmed root-cause explanation with a fix plan without applying the fix.
version: 1.0.0
requires_agents: terminal-runner
requires_skills: okf-context
artifact_outputs: root-cause-plan
---

# /debug

$ARGUMENTS

No code writing in this workflow — only investigation and a fix plan. Find the
real root cause in this codebase, not a plausible-sounding guess.

## Steps

1. Gather the symptom from `$ARGUMENTS`. If any of the following is missing,
   ask one question at a time — the error/symptom, reproduction steps,
   expected vs. actual behavior, and what changed recently (check via
   `git log`, run through the `terminal-runner` agent) — stopping and waiting
   for the answer before asking the next. Do not batch questions.
2. Before reading raw source, consult `.buddhi/docs/` and use Buddhi MCP tools
   (`buddhi_search`, `buddhi_read`, see the `okf-context` skill) or query
   `.buddhi/graphs/tree-graph.db` / `tree-graph.json` for the subsystem the symptom
   points to, per the harness's docs/graph-before-source convention.
3. Form a ranked list of candidate root causes, most likely first, based on
   what step 2 turned up. If the failing area spans domains ambiguously
   enough that a `/plan`-style breakdown would help, optionally dispatch the
   relevant specialist agent(s) under `agents/` to narrow the candidates —
   this is a judgment call, not a required step.
4. Investigate systematically rather than jumping at the first plausible
   hypothesis: reproduce the failure via `terminal-runner` where possible,
   inspect real logs/output, and eliminate candidates one at a time using
   that evidence.
5. Once the root cause is confirmed, report it with file:line references
   drawn from the graph/docs (not vague descriptions), plus a concrete fix
   plan — what needs to change and where. Do not write or apply the fix.
   Suggest running `/verify` once the fix has actually been applied, to
   prove it worked.
