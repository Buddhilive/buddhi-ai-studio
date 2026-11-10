---
name: implement
description: Execute the tasks defined in tasks.md sequentially by user story, respecting dependencies and parallelism markers, updating task progress, and grounding changes in codebase OKF docs. Use when implementing tasks with /implement.
version: 1.3.0
requires_agents: frontend-specialist, backend-specialist, database-specialist, testing-specialist, security-specialist, deployment-specialist, git-specialist, terminal-runner
requires_skills: okf-context
optional_skills: refactor-clean, code-review, audit-choices, handoff-spec, a11y, rtk, design-md
artifact_outputs: implementation
---

# /implement

$ARGUMENTS

Implementation phase in the Spec-Driven Development (SDD) lifecycle. Executes tasks from
`.buddhi/specs/<branch>/spec-tasks.md` in phased order, prioritizing user stories from MVP (P1)
onwards and keeping `tasks.md` progress up to date.

## Steps

1. **Verify prerequisites**: Run `buddhi sdd check --require-tasks --include-tasks --json` via
   the `terminal-runner` agent. This strictly ensures that `spec.md`, `plan.md`, and `tasks.md`
   all exist before proceeding. If any are missing, stop immediately and guide the user to run
   the missing skill (`/specify`, `/spec-plan`, or `/spec-tasks`).
2. **Load context**:
   - Read `tasks.md` for the execution plan and task IDs.
   - Read `plan.md` for architectural context, project structure, and file targets.
   - Read `spec.md` for user stories and acceptance criteria.
   - Consult `.buddhi/docs/` and query the code graph via Buddhi MCP tools (`buddhi_search`,
     `buddhi_read`, see the `okf-context` skill) for modules being modified. If OKF docs are absent,
     proceed directly with existing source files.
3. **Phased execution**:
   Execute tasks phase by phase:
   - **Phase 1: Setup**: Run project/tooling setup commands via `terminal-runner` (or `buddhi scripts rtk run --`) to keep context lean.
   - **Phase 2: Foundational**: Implement core blocking items (schemas, models, base routes, configs).
     *Checkpoint*: Verify foundation builds cleanly before proceeding to user stories.
   - **Phase 3+: User Story N (P1 MVP → P2 → P3...)**:
     - Implement story tasks in order (tests first if specified, then models, services, endpoints/UI).
     - Dispatch domain specialists (backend, frontend, database, etc.) for complex domain work.
     - For UI/frontend implementation: obey `.agents/rules/a11y.md` at all times. Use native HTML elements over ARIA recreation. For non-derivable pattern choices between equally conformant alternatives, record in `A11Y-DECISIONS.md`. Run `buddhi scripts verify-a11y` and `buddhi scripts contrast` after implementing frontend components.
     - For tasks marked `[P]`, parallel implementation across distinct files is permitted.
     - *Checkpoint*: After finishing each story, test it independently to confirm working state.
     - *Maintenance & Choices Checkpoint*:
       * Run `/refactor-clean` to ensure no temporary shims or dead wrappers linger.
       * If decisions were made where the spec was silent, record them in `.buddhi/specs/<branch>/choices.md`
         (following the `/audit-choices` format: `sound`, `unsound`, `needs-user`).
   - **Phase N: Polish**: Documentation, linting, formatting, cleanup, and A11Y static gate verification.
   - *Handoff Support*: If the implementation must pause or move to another agent/session mid-flight,
     run `/handoff-spec` to record active context directly into the spec folder.
4. **Update task progress**:
   After completing each task, edit `tasks.md` to mark the task completed (`- [x] TXXX`).
5. **Next step**: Once all tasks in `tasks.md` are completed, inform the user and suggest
   running `/verify` to execute full acceptance verification against the specification.
