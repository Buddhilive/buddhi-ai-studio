---
name: learn
description: Distill lessons, debug workarounds, or user corrections into reusable skills. Use when users /learn or want to save a procedural lesson.
category: general
---

# /learn

Distill procedural lessons and workarounds from the current conversation into durable, self-contained skills via `stage_skill`.

## Compare-First Workflow

1. **Review Session**: Identify the concrete problem, root cause, and reproducible fix.
2. **Compare Against Existing Skills**:
   - Inspect `.agents/skills/` (and global skills if active).
   - If a skill for this concept exists: propose `patch` or `update` to extend it rather than duplicating.
   - If this supersedes a previous rule: rewrite the old rule so the skill stays coherent.
3. **Draft Mutation**:
   - Keep `SKILL.md` under 25 lines (see [format_spec](./references/format_spec.md)).
   - Put detailed checklists or scripts in subfiles.
   - Front-load triggers in `description` (<= 60 chars, with `when`).
4. **Stage via `stage_skill`**:
   - Call the `stage_skill` MCP tool with `action`, `name`, `body`, `reason`, and `evidence`.
   - Never write directly to `.agents/skills/` manually; the promoter will validate through all 6 gates on turn completion.

