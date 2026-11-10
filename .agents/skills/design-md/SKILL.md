---
name: design-md
description: Inspect repository stylesheets, Tailwind configs, and design tokens to create or update a two-layer DESIGN.md file (machine-readable tokens in YAML frontmatter + vivid aesthetic direction prose across 8 canonical Markdown sections) and validate WCAG 2.2 AA contrast. Use when establishing, auditing, or updating the project design system.
---

# /design-md

Create or update the repository's `DESIGN.md` design system specification using real project stylesheets, Tailwind configs, and token files.

The `DESIGN.md` specification—introduced by Google in 2026—consists of two complementary layers:
1. **Machine-Readable Design Tokens (YAML Frontmatter)**: Deterministic tokens for `colors`, `typography`, `spacing`, `rounded`, and `elevation`.
2. **Human-Readable Design Rationale (Markdown Body)**: Natural language prose explaining the *why* and setting a vivid mental model for coding agents across the 8 canonical sections:
   - `## Overview`: Vivid aesthetic direction prose (e.g. *"A graduate-level computer science lecture handout in the tradition of an old established university"*) + Core visual principles.
   - `## Colors`: Semantic role definitions and contrast compliance.
   - `## Typography`: Type hierarchy, weights, and line-length limits (`65ch`).
   - `## Layout`: Grid scale and container boundaries.
   - `## Elevation & Depth`: Architectural layering and subtle borders over blurry shadows.
   - `## Shapes`: Consistent corner geometry.
   - `## Components`: Guidelines for Buttons, Cards, Inputs, and Modals with unbroken `:focus-visible` states.
   - `## Do's and Don'ts`: Actionable positive and negative rules stopping AI visual drift.

## Steps

1. **Inspect and Compute Diff**:
   Run the detection helper with `--diff` via the `terminal-runner` agent:
   ```bash
   python .agents/skills/design-md/scripts/detect_design_md.py --diff
   ```
   Or examine detected tokens and facts in JSON mode:
   ```bash
   python .agents/skills/design-md/scripts/detect_design_md.py --json
   ```

2. **Review Proposed Design Tokens & Aesthetic Prose**:
   - Verify that extracted tokens match actual stylesheets (`globals.css`, `tailwind.config.*`, `tokens.json`).
   - If setting a specific brand vibe or aesthetic metaphor, pass `--aesthetic`:
     ```bash
     python .agents/skills/design-md/scripts/detect_design_md.py --diff --aesthetic "A graduate-level computer science lecture handout in the tradition of an old established university: restrained, typographic, high-contrast, editorial."
     ```
   - If `DESIGN.md` already exists, confirm that all hand-crafted prose in `## Overview`, `## Components`, `## Do's and Don'ts`, and any custom sections (e.g. `## Brand Voice`) are preserved byte-for-byte.

3. **Apply Changes**:
   Once verified, apply changes to create or update `DESIGN.md`:
   ```bash
   python .agents/skills/design-md/scripts/detect_design_md.py --apply
   ```

4. **Validate WCAG 2.2 AA Contrast & Structure**:
   Run the built-in linter to verify canonical sections and test semantic foreground/background token pairs:
   ```bash
   python .agents/skills/design-md/scripts/detect_design_md.py --lint
   ```
   For deep reference on token schema and aesthetic archetypes, consult [references/design-md-spec.md](./references/design-md-spec.md).

