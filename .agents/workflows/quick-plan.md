---
name: quick-plan
description: Orchestrate a lightweight implementation plan for a full-stack request by classifying which domains it touches, dispatching only the relevant specialist agents in parallel, and synthesizing their findings into one plan grounded in the actual codebase.
version: 1.0.0
requires_agents: frontend-specialist, backend-specialist, database-specialist, testing-specialist, security-specialist, deployment-specialist, git-specialist, terminal-runner
requires_skills: okf-context, system-design
artifact_outputs: implementation-plan
---

# /quick-plan

$ARGUMENTS

No code writing in this workflow — only plan generation. Produce a single
implementation plan grounded in this codebase's actual structure, not generic
advice.

## Steps

1. Refresh context: run `buddhi docs plan` (via the `terminal-runner` agent) so
   `.buddhi/docs-plan.json` and the code graph reflect the current source tree.
2. Read `.buddhi/docs/index.md` and query the code graph using Buddhi MCP tools
   (`buddhi_search`, `buddhi_read`, see the `okf-context` skill) or `.buddhi/graphs/tree-graph.db` /
   `tree-graph.json` for the subsystem(s) the request touches. Do not start from raw source.
3. Ask clarifying questions one at a time — purpose, constraints, success
   criteria — until the request is well-scoped. For each question, propose a
   concrete suggested answer grounded in what step 2's docs/graph lookup
   found (e.g. "Looks like this touches the `auth` module via
   `src/auth/session.py` — assuming session-based auth, not JWT. Correct?")
   so the user can confirm with one word instead of answering from a blank
   page. If nothing in the codebase supports a specific guess, ask openly
   rather than inventing one. Stop and wait for the answer between
   questions; do not batch them.
4. Classify which domains the request actually touches: frontend, backend,
   database, testing, security, deployment, git. Dispatch **only** the
   specialist agents for those domains, in parallel. Give each one concrete
   context (file paths, relevant OKF docs, relevant graph nodes) — never
   "based on the request, figure it out yourself."
5. Each dispatched specialist returns a plan section grounded in real
   file:line references from the graph/docs it was given, not boilerplate
   checklist advice.
6. Synthesize the specialists' sections into one implementation plan: ordered
   steps, files to be touched, and a testing/verification section (always
   include this even if `testing-specialist` wasn't dispatched, using
   whatever specialists were involved). If the request involves a nontrivial
   architecture/trade-off decision (a new service/module boundary, a storage
   choice, sync-vs-async, introducing a new dependency or pattern — see the
   `system-design` skill's `when_to_use`), apply the `system-design` skill
   before finalizing that section, rather than picking an approach silently.
7. Write the synthesized plan to `.buddhi/plans/{slug}.md` — lowercase,
   hyphen-separated, at most 30 characters, derived from the request (e.g.
   "add dark mode feature" -> `.buddhi/plans/dark-mode.md`), creating
   `.buddhi/plans/` if it doesn't exist yet. This keeps plan artifacts out of
   the project root and grouped with buddhi's other generated state
   (`.buddhi/docs/`, `.buddhi/graphs/`), durable and reviewable outside chat.
   Present the plan and its file path, and wait for explicit approval before
   any implementation begins.
