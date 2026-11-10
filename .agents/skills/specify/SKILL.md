---
name: specify
description: Initialize and refine a feature specification in the Spec-Driven Development (SDD) lifecycle by creating a feature branch, scaffolding spec.md from the template, grounding requirements in codebase OKF docs, and defining prioritized, independently testable user stories. Use when starting a new feature specification with /specify.
version: 1.2.0
requires_agents: terminal-runner
requires_skills: okf-context
optional_skills: explore-unknowns, auto-research, a11y, design-md
artifact_outputs: feature-spec
---

# /specify

$ARGUMENTS

Start the Spec-Driven Development (SDD) cycle for a new feature request. Scaffolds a
structured `spec.md` under `.buddhi/specs/<branch>/` and refines it interactively with
prioritized, independently testable user stories. No code writing in this skill.

## Steps

0. **Pre-spec discovery (when needed)**:
   - If the task has major unknowns or design ambiguity, suggest running `/explore-unknowns` to complete a 4-quadrant unknown walk (known knowns, known unknowns, unknown knowns, unknown unknowns) before codifying the spec.
   - If the feature depends on empirical heuristics, rankings, or algorithm tuning, suggest running `/auto-research` to produce a parameter-effect map and verified incumbent in `.buddhi/specs/<branch>/research.md`.
1. **Update code graph**: Run `buddhi generate` via the `terminal-runner` agent to ensure
   the code graph (`.buddhi/graphs/tree-graph.db` and `tree-graph.json`) is up to date before
   inspecting or scaffolding.
2. **Scaffold feature**: Run `buddhi sdd create $ARGUMENTS --json` via the `terminal-runner`
   agent. This computes the feature number, branch name, creates `.buddhi/specs/<branch>/`,
   and initializes `spec.md` from the spec template. Parse the returned JSON to obtain
   `BRANCH_NAME` and `SPEC_FILE`.
3. **Codebase grounding**: Consult `.buddhi/docs/index.md` and use Buddhi MCP tools (`buddhi_search`,
   `buddhi_read`, see the `okf-context` skill) or query `.buddhi/graphs/tree-graph.db` / `tree-graph.json`
   for any subsystems the request touches. If OKF docs are missing or not generated yet, proceed
   gracefully without failing.
4. **Clarify requirements**: Ask clarifying questions one at a time — purpose, target users,
   constraints, and scope boundaries. Propose concrete answers grounded in what step 3's docs
   found so the user can confirm with minimal friction. Stop and wait for the user's answer
   between questions; do not batch them.
5. **Define user stories & priorities**:
   - Organize functionality into prioritized user stories (`P1`, `P2`, `P3`...).
   - Ensure `P1` represents a standalone, viable MVP slice.
   - For each story, provide plain-language journey, priority rationale, independent test
     description, and concrete **Given / When / Then** acceptance scenarios.
6. **Detail requirements & success criteria**:
   - List functional requirements (`FR-001`, `FR-002`...). Mark any ambiguities with `[NEEDS CLARIFICATION]`.
   - List key entities if data/state is involved.
   - If the feature involves UI, web surfaces, or interactive frontend components, verify against DESIGN.md design tokens (or suggest /design-md) and include an explicit Accessibility (A11Y) requirement (WCAG 2.2 AA / EN 301 549, keyboard operability, contrast compliance, and screen-reader semantics) referencing the `a11y` skill.
   - Define measurable, technology-agnostic success criteria (`SC-001`...).
   - Capture edge cases and boundary conditions.
7. **Write specification**: Write the refined specification to the `SPEC_FILE` path (`.buddhi/specs/<branch>/spec.md`).
8. **Next step**: Present the completed `spec.md` summary to the user and prompt them to run
   `/spec-plan` to proceed to the architecture and implementation planning phase.
