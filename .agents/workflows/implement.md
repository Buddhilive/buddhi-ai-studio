---
name: implement
description: Execute the tasks defined in tasks.md sequentially by user story, respecting dependencies and parallelism markers, updating task progress, and grounding changes in codebase OKF docs.
version: 1.0.0
requires_agents: frontend-specialist, backend-specialist, database-specialist, testing-specialist, security-specialist, deployment-specialist, git-specialist, terminal-runner
requires_skills: okf-context
artifact_outputs: implementation
---

# /implement

$ARGUMENTS

Implementation phase in the Spec-Driven Development (SDD) lifecycle. Executes tasks from
`.buddhi/specs/<branch>/tasks.md` in phased order, prioritizing user stories from MVP (P1)
onwards and keeping `tasks.md` progress up to date.

## Steps

1. **Verify prerequisites**: Run `buddhi sdd check --require-tasks --include-tasks --json` via
   the `terminal-runner` agent. This strictly ensures that `spec.md`, `plan.md`, and `tasks.md`
   all exist before proceeding. If any are missing, stop immediately and guide the user to run
   the missing workflow (`/specify`, `/plan`, or `/tasks`).
2. **Load context**:
   - Read `tasks.md` for the execution plan and task IDs.
   - Read `plan.md` for architectural context, project structure, and file targets.
   - Read `spec.md` for user stories and acceptance criteria.
   - Consult `.buddhi/docs/` and query the code graph via Buddhi MCP tools (`buddhi_search`,
     `buddhi_read`, see the `okf-context` skill) for modules being modified. If OKF docs are absent,
     proceed directly with existing source files.
3. **Phased execution**:
   Execute tasks phase by phase:
   - **Phase 1: Setup**: Run project/tooling setup commands via `terminal-runner` or create initial files.
   - **Phase 2: Foundational**: Implement core blocking items (schemas, models, base routes, configs).
     *Checkpoint*: Verify foundation builds cleanly before proceeding to user stories.
   - **Phase 3+: User Story N (P1 MVP → P2 → P3...)**:
     - Implement story tasks in order (tests first if specified, then models, services, endpoints/UI).
     - Dispatch domain specialists (backend, frontend, database, etc.) for complex domain work.
     - For tasks marked `[P]`, parallel implementation across distinct files is permitted.
     - *Checkpoint*: After finishing each story, test it independently to confirm working state.
   - **Phase N: Polish**: Documentation, linting, formatting, cleanup.
4. **Update task progress**:
   After completing each task, edit `tasks.md` to mark the task completed (`- [x] TXXX`).
5. **Next step**: Once all tasks in `tasks.md` are completed, inform the user and suggest
   running `/verify` to execute full acceptance verification against the specification.
