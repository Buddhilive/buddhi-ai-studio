---
name: plan
description: Orchestrate an architectural implementation plan in the Spec-Driven Development (SDD) lifecycle by setting up plan.md, grounding design in OKF codebase docs and graph, dispatching specialist agents in parallel, and synthesizing a comprehensive technical plan.
version: 2.0.0
requires_agents: frontend-specialist, backend-specialist, database-specialist, testing-specialist, security-specialist, deployment-specialist, git-specialist, terminal-runner
requires_skills: okf-context, system-design
artifact_outputs: implementation-plan
---

# /plan

$ARGUMENTS

Architecture and technical planning phase of Spec-Driven Development (SDD). Synthesizes
specialist agent findings and codebase context into `.buddhi/specs/<branch>/plan.md`.
No code writing in this workflow — only plan generation.

## Steps

1. **Setup plan**: Run `buddhi sdd setup-plan --json` via the `terminal-runner` agent.
   This verifies `spec.md` exists and copies `plan-template.md` to `.buddhi/specs/<branch>/plan.md`
   if not already created. Parse `FEATURE_SPEC`, `IMPL_PLAN`, `SPECS_DIR`, and `BRANCH` from the output.
2. **Read specification**: Read `spec.md` to understand all user stories, priorities (`P1`, `P2`...),
   functional requirements, and success criteria.
3. **Refresh codebase context**: Run `buddhi docs plan` (via `terminal-runner`) so `.buddhi/docs-plan.json`
   reflects the current source tree. Read `.buddhi/docs/index.md` and use Buddhi MCP tools (`buddhi_search`,
   `buddhi_read`, see the `okf-context` skill) or query `.buddhi/graphs/tree-graph.db` / `tree-graph.json`
   for touched subsystems. If OKF docs are absent, proceed directly with existing source files.
4. **Clarify technical ambiguities**: Ask clarifying questions one at a time regarding tech stack,
   dependencies, storage, performance goals, or constraints. Provide suggested answers grounded
   in the codebase context found in step 3. Stop and wait for the answer between questions.
5. **Dispatch specialist agents**: Classify which domains the feature touches (frontend, backend,
   database, testing, security, deployment, git). Dispatch **only** the relevant specialist agents
   in parallel with concrete context (file paths, relevant OKF docs, graph nodes).
6. **Synthesize implementation plan**:
   - Fill in each section of `plan.md`: **Summary**, **Technical Context**, **Constitution Check**,
     **Project Structure** (source tree layout with concrete paths), and **Complexity Tracking**.
   - If the request involves a nontrivial architecture/trade-off decision (new service boundary,
     storage choice, sync vs async, new pattern), apply the `system-design` skill to evaluate
     alternatives before finalizing that section.
7. **Write plan**: Write the completed plan to `IMPL_PLAN` (`.buddhi/specs/<branch>/plan.md`).
8. **Next step**: Present the plan to the user and prompt them to run `/tasks` to break down the
   plan into actionable, testable tasks.
