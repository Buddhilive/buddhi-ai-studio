---
name: tasks
description: Break down an SDD implementation plan and specification into actionable, prioritized, and independently testable tasks organized by user story into tasks.md.
version: 1.0.0
requires_agents: terminal-runner
requires_skills: okf-context
artifact_outputs: tasks-list
---

# /tasks

$ARGUMENTS

Task breakdown phase in the Spec-Driven Development (SDD) lifecycle. Converts `spec.md`
and `plan.md` into an actionable, user-story-oriented task checklist in
`.buddhi/specs/<branch>/tasks.md`. No implementation code is written in this workflow.

## Steps

1. **Setup & validate prerequisites**: Run `buddhi sdd setup-tasks --json` via the
   `terminal-runner` agent. This verifies that `spec.md` and `plan.md` both exist, and
   resolves the tasks template. Parse `FEATURE_DIR` and `AVAILABLE_DOCS` from the returned JSON.
2. **Read design inputs**:
   - Read `spec.md` from the feature directory to extract user stories with their priorities (`P1`, `P2`...)
     and acceptance criteria.
   - Read `plan.md` to extract the architecture decisions, concrete file paths, and project structure.
   - Read any available supplementary documents listed in `AVAILABLE_DOCS` (`research.md`,
     `data-model.md`, `contracts/`, `quickstart.md`).
3. **Structure tasks by phase and user story**:
   Generate tasks using the standard SDD task format: `[ID] [P?] [Story] Description`
   - **Phase 1: Setup**: Project initialization, directory structure, tooling, dependencies.
   - **Phase 2: Foundational (Blocking)**: Core models, database schema, base routing, error handling
     that MUST be in place before any user story can begin.
   - **Phase 3+: User Story N (P1 🎯 MVP, P2, P3...)**: Grouped by story so each story can be
     developed and tested independently. Include tests (if specified) followed by implementation.
   - **Phase N: Polish & Cross-Cutting**: Documentation, cleanup, performance, hardening.
4. **Enforce task rules**:
   - Tag tasks that have no dependencies and touch different files with `[P]` for parallel execution.
   - Tag each user story task with its story identifier (e.g. `[US1]`, `[US2]`).
   - Include exact file paths in task descriptions (no placeholders).
5. **Write tasks file**: Write the generated task list to `.buddhi/specs/<branch>/tasks.md`.
6. **Next step**: Present the task breakdown and phase order to the user, and prompt them to
   run `/implement` to start executing the tasks.
