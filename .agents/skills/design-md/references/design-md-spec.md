# DESIGN.md Specification & Archetype Reference Guide

> Adapted from Google Labs `DESIGN.md` specification (`https://github.com/google-labs-code/design.md` and `https://stitch.withgoogle.com/docs/design-md/specification`).

## The Two-Layer Architecture

`DESIGN.md` bridges machine-readable design tokens with human-readable rationale:

$$\text{DESIGN.md} = \langle \mathcal{T}_{\text{machine}}, \mathcal{R}_{\text{human}} \rangle$$

1. **$\mathcal{T}_{\text{machine}}$ (YAML Frontmatter)**: Programmatic tokens for compilation toolchains, Tailwind CSS configs, or DTCG parsers.
2. **$\mathcal{R}_{\text{human}}$ (Markdown Body)**: Prose explaining the *why* and semantic rules preventing AI coding agents from stateless visual drift.

---

## The 8 Canonical Markdown Sections

1. **`## Overview`**: The single most important section. Paints a vivid picture so coding agents understand document styling intent.
2. **`## Colors`**: Semantic role mapping (`primary`, `secondary`, `surface`, `background`, `text`, `border`) with WCAG 2.2 AA contrast ratios.
3. **`## Typography`**: Font families, modular scale, font weights, and maximum reading width (`65ch`).
4. **`## Layout`**: Grid multiples (`4px`/`8px`), container boundaries (`sm` to `xl`).
5. **`## Elevation & Depth`**: Subtle border layering over heavy blurry drop shadows.
6. **`## Shapes`**: Corner radius discipline (`rounded.md` for cards/buttons, full pills banned for everything except tags/avatars).
7. **`## Components`**: Guardrails for Buttons, Cards, Inputs, Navigation, and Modals with visible `:focus-visible` rings.
8. **`## Do's and Don'ts`**: Explicit guardrails stopping generic AI slop.

---

## Vivid Aesthetic Direction Archetypes

When crafting the `## Overview` prose, use vivid, evocative metaphors rather than generic descriptions:

- **Academic Monograph**: *"A graduate-level computer science lecture handout in the tradition of an old established university: restrained, typographic, high-contrast, editorial."*
- **Swiss Modernist Terminal**: *"A high-density Swiss design poster combined with an aerospace telemetry terminal: strict modular grid, monochromatic foundation, singular phosphor accent."*
- **Contemporary Digital Broadsheet**: *"An architectural broadsheet newspaper: matte limestone surfaces, deep ink typography, crisp 1px borders, zero floating drop shadows."*
- **Minimalist Studio Ledger**: *"An architect's sketchbook: warm stone canvas, fine hairline dividers, precise monospace numerals, deliberate whitespace."*

