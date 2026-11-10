---
name: spec-plan
description: Orchestrate an architectural implementation plan in the Spec-Driven Development (SDD) lifecycle by setting up plan.md, grounding design in OKF codebase docs and graph, dispatching specialist agents in parallel, and synthesizing a comprehensive technical plan. Use when creating an SDD technical plan with /spec-plan.
version: 2.2.0
requires_agents: frontend-specialist, backend-specialist, database-specialist, testing-specialist, security-specialist, deployment-specialist, git-specialist, terminal-runner
requires_skills: okf-context, system-design
optional_skills: a11y, agents-md, design-md
artifact_outputs: implementation-plan
---

# /spec-plan

$ARGUMENTS

Architecture and technical planning phase of Spec-Driven Development (SDD). Synthesizes
specialist agent findings and codebase context into `.buddhi/specs/<branch>/plan.md`.
No code writing in this skill — only plan generation.

## Steps

1. **Setup plan**: Run `buddhi sdd setup-plan --json` via the `terminal-runner` agent.
   This verifies `spec.md` exists and copies `plan-template.md` to `.buddhi/specs/<branch>/plan.md`
   if not already created. Parse `FEATURE_SPEC`, `IMPL_PLAN`, `SPECS_DIR`, and `BRANCH` from the output.
2. **Read specification & prior research**:
   - Read `spec.md` to understand all user stories, priorities (`P1`, `P2`...), functional requirements, and success criteria.
   - If available, read `.buddhi/specs/<branch>/research.md` (from `/auto-research` or `/explore-unknowns`) to ground decisions in parameter-effect maps or empirical baselines.
3. **Refresh codebase context & query memory**:
   - Run `buddhi docs plan` (via `terminal-runner`) so `.buddhi/docs-plan.json` reflects the current source tree. Read `.buddhi/docs/index.md` and use Buddhi MCP tools (`buddhi_search`, `buddhi_read`, see the `okf-context` skill).
   - Query project memory using `buddhi_memory(action="search", active_files=...)` or `buddhi memory search` to retrieve relevant conventions, decisions, and SDD rationales before planning. Verify that no relevant memory concepts are currently flagged as stale.
4. **Clarify technical ambiguities**: Ask clarifying questions one at a time regarding tech stack,
   dependencies, storage, performance goals, or constraints. Provide suggested answers grounded
   in the codebase context found in step 3. Stop and wait for the answer between questions.
5. **Dispatch specialist agents & evaluate multi-angle perspectives**:
   - Classify which domains the feature touches (frontend, backend, database, testing, security, deployment, git).
   - Dispatch **only** the relevant specialist agents in parallel with concrete context (file paths, relevant OKF docs, graph nodes).
   - When the feature touches UI/frontend, instruct `frontend-specialist` to review accessibility implications: check `A11Y-DECISIONS.md`, consult `.agents/skills/a11y/references/guide-*.md` for component patterns involved, and define static gate / contrast requirements in the plan.
   - Evaluate trade-offs across three distinct architectural lenses:
     * *Fewest-slices*: What is the minimal change that delivers end-to-end value?
     * *Risk-first*: What are the most volatile technical risks (e.g. data consistency, perf, security) that must be de-risked early?
     * *Seam-quality*: Are boundaries clean and decoupled with zero leaked internals or temporary shims?
6. **Synthesize implementation plan**:
   - Fill in each section of `plan.md`: **Summary**, **Technical Context**, **AGENTS.md & DESIGN.md Compliance Check** (gate: verify build/test commands and project constraints; if AGENTS.md is missing, run /agents-md; if UI/frontend surfaces are touched, verify DESIGN.md tokens and contrast or run /design-md),
     **Project Structure** (source tree layout with concrete paths), and **Complexity Tracking**.
   - For UI features, include an Accessibility Strategy section detailing keyboard operability, contrast floors (using `buddhi scripts contrast`), and governance artifact maintenance (`REPORT.md`, `A11Y-DECISIONS.md`).
   - If the request involves a nontrivial architecture/trade-off decision (new service boundary,
     storage choice, sync vs async, new pattern), apply the `system-design` skill to evaluate
     alternatives before finalizing that section.
7. **Write plan**: Write the completed plan to `IMPL_PLAN` (`.buddhi/specs/<branch>/plan.md`).
8. **Next step**: Present the plan to the user and prompt them to run `/spec-tasks` to break down the
   plan into actionable, testable tasks.
