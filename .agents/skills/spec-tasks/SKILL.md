---
name: spec-tasks
description: Break down an SDD implementation plan and specification into actionable, prioritized, and independently testable tasks organized by user story into tasks.md. Use when creating task lists with /spec-tasks.
version: 1.2.0
requires_agents: terminal-runner
requires_skills: okf-context
optional_skills: a11y
artifact_outputs: tasks-list
---

# /spec-tasks

$ARGUMENTS

Task breakdown phase in the Spec-Driven Development (SDD) lifecycle. Converts `spec.md`
and `plan.md` into an actionable, user-story-oriented task checklist in
`.buddhi/specs/<branch>/tasks.md`. No implementation code is written in this skill.

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
3. **Structure tasks by phase and user story (Fog-of-War Slicing)**:
   Generate tasks using the standard SDD task format: `[ID] [P?] [Story] Description`
   - **Phase 1: Setup**: Project initialization, directory structure, tooling, dependencies.
   - **Phase 2: Foundational (Blocking)**: Core models, database schema, base routing, error handling
     that MUST be in place before any user story can begin.
   - **Phase 3+: User Story N (P1 🎯 MVP, P2, P3...)**: Grouped by story so each story forms an
     independently verifiable slice. For each story, structure tasks:
     1. Test specification / verification task (matching acceptance criteria).
     2. Core entities/services implementation.
     3. Integration checkpoint proving the slice works in isolation.
     4. For UI stories: keyboard navigation, contrast check (`buddhi scripts contrast`), and A11Y static gate (`buddhi scripts verify-a11y`).
   - **Phase N: Polish & Cross-Cutting**: Documentation updates, cleanup, performance, hardening, and A11Y governance verification (`REPORT.md` / `A11Y-DECISIONS.md`).
4. **Enforce task rules**:
   - Tag tasks that have no dependencies and touch different files with `[P]` for parallel execution.
   - Tag each user story task with its story identifier (e.g. `[US1]`, `[US2]`).
   - Include exact file paths in task descriptions (no placeholders or ambiguous references).
   - Ensure every slice is small enough to be reviewed and verified without cognitive overload.
5. **Write tasks file**: Write the generated task list to `.buddhi/specs/<branch>/tasks.md`.
6. **Next step**: Present the task breakdown and phase order to the user, and prompt them to
   run `/implement` to start executing the tasks.
