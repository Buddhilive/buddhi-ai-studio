---
colors:
  background:
    light: "oklch(0.9383 0.0042 236.4993)"
    dark: "oklch(0.2598 0.0306 262.6666)"
  foreground:
    light: "oklch(0.3211 0 0)"
    dark: "oklch(0.9219 0 0)"
  card:
    light: "oklch(1.0000 0 0)"
    dark: "oklch(0.3106 0.0301 268.6365)"
  card-foreground:
    light: "oklch(0.3211 0 0)"
    dark: "oklch(0.9219 0 0)"
  primary:
    light: "oklch(0.6397 0.1720 36.4421)"
    dark: "oklch(0.6397 0.1720 36.4421)"
  primary-foreground:
    light: "oklch(1.0000 0 0)"
    dark: "oklch(1.0000 0 0)"
  secondary:
    light: "oklch(0.9670 0.0029 264.5419)"
    dark: "oklch(0.3541 0.0280 267.1200)"
  secondary-foreground:
    light: "oklch(0.4461 0.0263 256.8018)"
    dark: "oklch(0.8800 0.0100 260.0000)"
  muted:
    light: "oklch(0.9846 0.0017 247.8389)"
    dark: "oklch(0.2800 0.0250 265.0000)"
  muted-foreground:
    light: "oklch(0.5510 0.0234 264.3637)"
    dark: "oklch(0.7000 0.0200 264.0000)"
  accent:
    light: "oklch(0.9119 0.0222 243.8174)"
    dark: "oklch(0.3400 0.0350 260.0000)"
  accent-foreground:
    light: "oklch(0.3791 0.1378 265.5222)"
    dark: "oklch(0.9500 0.0100 260.0000)"
  destructive:
    light: "oklch(0.6368 0.2078 25.3313)"
    dark: "oklch(0.6368 0.2078 25.3313)"
  destructive-foreground:
    light: "oklch(1.0000 0 0)"
    dark: "oklch(1.0000 0 0)"
  border:
    light: "oklch(0.9022 0.0052 247.8822)"
    dark: "oklch(0.3500 0.0200 265.0000)"
  ring:
    light: "oklch(0.6397 0.1720 36.4421)"
    dark: "oklch(0.6397 0.1720 36.4421)"
typography:
  font-sans: "Inter, sans-serif"
  font-mono: "JetBrains Mono, monospace"
  font-serif: "Source Serif 4, serif"
  max-line-length: "65ch"
spacing:
  base: "0.25rem"
  scale: [1, 2, 3, 4, 6, 8, 12, 16]
rounded:
  sm: "calc(0.75rem * 0.6)"
  md: "calc(0.75rem * 0.8)"
  lg: "0.75rem"
  xl: "calc(0.75rem * 1.4)"
elevation:
  subtle-border: "1px solid var(--border)"
  shadow-sm: "0px 1px 3px 0px hsl(0 0% 0% / 0.10)"
---

# Design System Specification (DESIGN.md)

## Overview

Buddhi AI Studio's visual identity embodies **an industrial-grade flight deck for autonomous software engineering**. The interface balances precision, clarity, and operational density without cognitive clutter. Inspired by mission-critical IDEs and observatory workstations, every pane—the cognitive trajectory stream, interactive OpenSandbox terminal, code diff editor, and live browser viewport—conveys state with calm authority.

### Core Visual Principles
1. **Instrument-Grade Precision**: Information density is prioritized over decorative fluff. Clean hairline borders separate operational zones.
2. **Transparent Cognitive Telemetry**: Internal agent reasoning (Elephant planning, Goldfish audits, RLM slice queries) is distinguished with semantic color coding rather than hidden in black-box spinners.
3. **Calm, High-Contrast Readability**: Typography uses Inter for metadata and JetBrains Mono for code and trajectory execution streams, guaranteeing WCAG 2.2 AA readability under both dark and light modes.
4. **Physicality of Action**: Interactive controls (Pause, Step, Override, Diff Revert) provide immediate, tactile visual feedback.

---

## Colors

All colors are defined via semantic tokens in OKLCH space, ensuring uniform perceived luminance and effortless theme switching:

- **Surface & Foundation (`--background`, `--card`, `--popover`)**: Deep slate obsidian in dark mode, crisp architectural paper in light mode.
- **Brand Primary (`--primary`)**: High-energy amber-crimson (`oklch(0.6397 0.1720 36.4421)`), reserved for primary actions, active execution states, and focus rings. Contrast ratio against dark background exceeds **5.8:1** (WCAG AA compliant).
- **Secondary & Muted (`--secondary`, `--muted`, `--muted-foreground`)**: Cool neutral tones for scaffolding, inactive panels, and auxiliary timestamps. Contrast ratio exceeds **4.8:1**.
- **Cognitive Roles**:
  - *Elephant (Deep Context / Planning)*: Warm amber accent badges (`oklch(0.7875 0.0917 35.9616)`).
  - *Goldfish (Adversarial Audit)*: Crisp azure badge (`oklch(0.7156 0.0605 248.6845)`).
  - *Sandbox Execution (Shell / Docker)*: Emerald terminal indicator (`oklch(0.70 0.15 145.0)`).
  - *Destructive / Error*: Vivid crimson (`oklch(0.6368 0.2078 25.3313)`).

---

## Typography

- **Primary Sans (`--font-sans`)**: `Inter, sans-serif` for navigation, settings, metadata, and task descriptions.
- **Code & Stream Mono (`--font-mono`)**: `JetBrains Mono, monospace` with tabular numbers enabled for code snippets, sandbox stdout/stderr, git diffs, and trajectory logs.
- **Line Length Constraint**: Prose, task specifications, and audit reports must respect a strict maximum line length of `65ch` to preserve comfortable reading flow.
- **Hierarchy**:
  - `Display / H1`: 1.75rem (28px), font-semibold, letter-spacing -0.025em.
  - `H2 Section`: 1.25rem (20px), font-medium, letter-spacing -0.015em.
  - `Body`: 0.875rem (14px), font-normal, line-height 1.5.
  - `Code / Meta`: 0.8125rem (13px), font-mono, line-height 1.45.

---

## Layout

The autonomous engineering interface is anchored by an **ergonomic 3-pane responsive flight deck**:

1. **Left Rail / Trajectory Stream (35% width / min 360px)**:
   - Chronological, color-coded trajectory stream showing model thought tokens, tool invocations, RLM memory slices, and Goldfish review decisions.
   - Pinned control header: Task status badge, Pause/Resume, Step, and token burn rate.
2. **Center Stage / Workspace & Diffs (40% width)**:
   - Tabbed workspace containing:
     - Side-by-side or inline unified Git Diff Viewer.
     - AST Symbol Dependency Explorer (powered by Buddhi tree-sitter graph).
     - Live Markdown Spec Viewer.
3. **Right Stage / Sandbox Runtime & Browser (25% width / collapsible)**:
   - Interactive OpenSandbox terminal running bash/zsh inside Docker.
   - Headless browser preview (Crawl4AI / VNC view).
   - System resource telemetry (CPU % / RAM / LiteRT inference latency).

Container boundaries use CSS flex/grid with `gap-3` and persistent boundary borders (`border-border`).

---

## Elevation & Depth

- **Zero Blurry Shadows**: Avoid heavy dropped shadows or floating cards with ambiguous bounds.
- **Hairline Architectural Borders**: Depth is established through subtle 1px solid hairline borders (`1px solid var(--border)`).
- **Z-Index Layering**:
  - `Base`: 0 (Background grid)
  - `Panes / Cards`: 10 (Terminal, Editor, Stream)
  - `Sticky Controls`: 20 (Header controls, timeline scrubbers)
  - `Modals & Confirmations`: 50 (Destructive git confirmation, human-in-the-loop overrides)

---

## Shapes

- **Corner Radius**:
  - `sm` (`calc(var(--radius) * 0.6)` ~ 4.5px): Badges, tool pills, status chips.
  - `md` (`calc(var(--radius) * 0.8)` ~ 6px): Buttons, form inputs, terminal line blocks.
  - `lg` (`var(--radius)` = 12px): Outer panels, modal windows, split containers.
- **Geometry Invariant**: Sharp inner corners nested within rounded outer frames must follow concentric radius math (`inner_radius = outer_radius - padding`).

---

## Components

### Trajectory Item
- Displays timestamp, role chip (`Elephant` | `Goldfish` | `Sandbox` | `RLM`), collapsible thinking block, and output payload.
- Unbroken `:focus-visible` ring (`2px solid var(--ring)` with `offset-2`).

### Sandbox Terminal Pane
- Monospace output with ANSI 256-color support, auto-scrolling lock toggle, and clear execution status badges (exit code `0` in green, non-zero in crimson).

### Git Diff Block
- Added lines in emerald tint (`oklch(0.92 0.05 145.0 / 0.15)`), deleted lines in crimson tint (`oklch(0.92 0.05 25.0 / 0.15)`), line numbers strictly aligned with tabular figures.

### Action Controls
- Buttons have minimum tap targets of 44x44px or 36px with 8px margin for keyboard navigation.
- Accessible ARIA labels (`aria-label`, `aria-live="polite"` for streaming updates).

---

## Do's and Don'ts

### Do:
- **Do** stream all agent thoughts, tool arguments, and sandbox stdout directly to the trajectory pane in real time.
- **Do** use JetBrains Mono with tabular figures for any metrics, tokens, line counts, or timestamps.
- **Do** verify all text contrast pairs against WCAG 2.2 AA (minimum 4.5:1 for body, 3:1 for large text).
- **Do** provide keyboard shortcuts (`Space` to pause, `Ctrl+Enter` to submit human guidance, `Escape` to close modals).

### Don't:
- **Don't** hide agent failures or sandbox command timeouts behind a generic spinner.
- **Don't** use decorative purple/pink gradient text or "AI sparkles" slop.
- **Don't** nest scrollbars inside scrollbars without clear container constraints.
- **Don't** let lines of prose exceed 65 characters in specs or audit cards.
