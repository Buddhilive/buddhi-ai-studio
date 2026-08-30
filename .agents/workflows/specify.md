---
name: specify
description: Initialize and refine a feature specification in the Spec-Driven Development (SDD) lifecycle by creating a feature branch, scaffolding spec.md from the template, grounding requirements in codebase OKF docs, and defining prioritized, independently testable user stories.
version: 1.0.0
requires_agents: terminal-runner
requires_skills: okf-context
artifact_outputs: feature-spec
---

# /specify

$ARGUMENTS

Start the Spec-Driven Development (SDD) cycle for a new feature request. Scaffolds a
structured `spec.md` under `.buddhi/specs/<branch>/` and refines it interactively with
prioritized, independently testable user stories. No code writing in this workflow.

## Steps

1. **Scaffold feature**: Run `buddhi sdd create $ARGUMENTS --json` via the `terminal-runner`
   agent. This computes the feature number, branch name, creates `.buddhi/specs/<branch>/`,
   and initializes `spec.md` from the spec template. Parse the returned JSON to obtain
   `BRANCH_NAME` and `SPEC_FILE`.
2. **Codebase grounding**: Consult `.buddhi/docs/index.md` and use Buddhi MCP tools (`buddhi_search`,
   `buddhi_read`, see the `okf-context` skill) or query `.buddhi/graphs/tree-graph.db` / `tree-graph.json`
   for any subsystems the request touches. If OKF docs are missing or not generated yet, proceed
   gracefully without failing.
3. **Clarify requirements**: Ask clarifying questions one at a time — purpose, target users,
   constraints, and scope boundaries. Propose concrete answers grounded in what step 2's docs
   found so the user can confirm with minimal friction. Stop and wait for the user's answer
   between questions; do not batch them.
4. **Define user stories & priorities**:
   - Organize functionality into prioritized user stories (`P1`, `P2`, `P3`...).
   - Ensure `P1` represents a standalone, viable MVP slice.
   - For each story, provide plain-language journey, priority rationale, independent test
     description, and concrete **Given / When / Then** acceptance scenarios.
5. **Detail requirements & success criteria**:
   - List functional requirements (`FR-001`, `FR-002`...). Mark any ambiguities with `[NEEDS CLARIFICATION]`.
   - List key entities if data/state is involved.
   - Define measurable, technology-agnostic success criteria (`SC-001`...).
   - Capture edge cases and boundary conditions.
6. **Write specification**: Write the refined specification to the `SPEC_FILE` path (`.buddhi/specs/<branch>/spec.md`).
7. **Next step**: Present the completed `spec.md` summary to the user and prompt them to run
   `/plan` to proceed to the architecture and implementation planning phase.
