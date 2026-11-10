---
name: autoharness
version: 1.0.0
priority: P0
trigger: always_on
---

# AutoHarness Self-Learning Protocol

- **Agent-Created Skill Recall**: At session start, an index of active agent-authored skills is injected into the context. Consult this index when facing recurring workflows or framework quirks.
- **Procedural Learning vs Architectural Memory**:
  - Distill repeatable tool runbooks, debugging steps, and command sequences into skills via `/learn` (or `stage_skill`).
  - Capture architectural decisions, trade-offs, and invariants into OKF concept notes via `/remember` (or `buddhi_memory`).
- **Immutable Native Skills**: Native skills shipped by Buddhi CLI and human instructions are strictly read-only to AutoHarness.
- **Reflection Reminders**: When the harness signals that reflection or curation thresholds have been reached, launch the `reflector` or `curator` subagent to refine skills.

