# Accessibility Decisions (A11Y-DECISIONS.md)

## Standard Profile (WCAG 2.2 AA / EN 301 549)

### 1. Terminal Output (`src/components/ai-elements/terminal.tsx`)
- **Keyboard Scrolling**: Added `tabindex="0"` with accessible `aria-label="Terminal output stream"` to ensure keyboard-only users can scroll long output.
- **Contrast Ratios Verified (check_contrast)**:
  - Text: `#f4f4f5` on `#09090b` = **18.10:1** (PASS >= 4.5:1)
  - Error text: `#fb7185` on `#09090b` = **7.39:1** (PASS >= 4.5:1)
  - Success text: `#34d399` on `#09090b` = **10.35:1** (PASS >= 4.5:1)
- **Status Non-Reliance on Color**: Exit code text ("exit: 0" / "exit: 1") is rendered explicitly alongside visual border tint.

### 2. Tool Card (`src/components/ai-elements/tool.tsx`)
- **Keyboard Operability**: Built on Base UI CollapsibleTrigger ensuring default button semantics, focus rings, and `aria-expanded` attribute synchrony.
- **Screen Reader Clarity**: Status badges include both visual icons and textual status names ("Running", "Completed", "Error").

### 3. Execution Plan (`src/components/ai-elements/plan.tsx`)
- **Semantic Structure**: Uses `<ol>` ordered list for step sequences.
- **Status Announcements**: Added `.sr-only` text ("- Completed", "- In progress", "- Failed") alongside each step so screen reader users receive status without visual interpretation.

### 4. Agent Progress Announcements (`src/components/chat/chat-interface.tsx`)
- **Live Region**: Added polite live region `<div aria-live="polite" className="sr-only">` announcing phase changes ("Agent initializing...", "Agent executing state machine...") without interrupting speech during streaming token output.

### 5. RLM Context Scaling Settings (`src/components/settings/rlm-settings.tsx`)
- **Slider Keyboard Operability**: Used semantic native `<input type="range">` with explicit `aria-valuemin="0"`, `aria-valuemax="3"`, `aria-valuenow`, and `aria-valuetext` describing the recursion depth level and reach. Visible high-contrast focus rings (`focus:ring-2 focus:ring-primary`) ensure keyboard navigation parity.
- **Dynamic Live Region**: Effective reach estimate container is configured with `aria-live="polite"` so screen readers are gently notified when context window or recursion depth sliders adjust the computed token capacity without interrupting active speech.
- **Form Controls & Labels**: All numeric inputs and mode selectors are bound via `useId()` and associated `<Label htmlFor={...}>`.
- **Non-Reliance on Color**: Hardware viability warnings and depth recommendations include explicit text, badge labels, and icons.
- **Confirmation Dialog**: Engine reload modal uses Radix `Dialog` with focus trapping, `Escape` key cancellation, and clear warning descriptions of memory reallocation.

### 6. Elephant-Goldfish Review Gate & Triage Panel (`src/components/ai-elements/egm-review-panel.tsx`, `src/components/ai-elements/egm-phase-badge.tsx`)
- **Focus Management (SC-007, FR-016)**: On gate entry / component mount, keyboard focus is automatically shifted to the triage panel heading via `tabIndex={-1}` and `ref.current?.focus()`, alerting keyboard/screen-reader users immediately that execution is paused at the human review gate.
- **Accessible `<fieldset>` Grouping**: Each finding item is wrapped in an accessible `<fieldset>` with an explicit `<legend className="sr-only">`, ensuring screen readers announce the context of the radio/button triage choices (`Accept`, `Reject`, `Defer`).
- **Non-Reliance on Color for Severity**:
  - Blocker: text prefix `[BLOCKER]`, OctagonAlertIcon, distinct border and non-color text.
  - Major: text prefix `[MAJOR]`, AlertTriangleIcon, distinct border and non-color text.
  - Nit: text prefix `[NIT]`, InfoIcon, distinct border and non-color text.
- **Contrast Ratios Verified (WCAG 2.2 AA Standard Profile)**:
  - Amber (Elephant): `#b45309` on `#ffffff` = **5.02:1** (PASS >= 4.5:1); `#fcd34d` on `#09090b` = **13.80:1** (PASS >= 4.5:1)
  - Sky (Goldfish): `#075985` on `#ffffff` = **7.56:1** (PASS >= 4.5:1); `#7dd3fc` on `#09090b` = **11.93:1** (PASS >= 4.5:1)
  - Blocker Badge: `#b91c1c` on `#ffffff` = **6.47:1** (PASS >= 4.5:1); `#f87171` on `#09090b` = **7.19:1** (PASS >= 4.5:1)
  - Major Badge: `#b45309` on `#ffffff` = **5.02:1** (PASS >= 4.5:1); `#fbbf24` on `#09090b` = **11.92:1** (PASS >= 4.5:1)
  - Nit Badge: `#15803d` on `#ffffff` = **5.02:1** (PASS >= 4.5:1); `#4ade80` on `#09090b` = **11.42:1** (PASS >= 4.5:1)
- **Live Status & Feedback**: Submit and quick-action buttons include `disabled={isSubmitting}` and live state announcements with `aria-live="polite"`.

### 7. Elephant-Goldfish Settings Configuration (`src/components/settings/egm-settings.tsx`)
- **Accessible Slider Controls**: Max sharpening rounds slider uses semantic `<input type="range">` with `aria-valuemin="1"`, `aria-valuemax="5"`, `aria-valuenow`, and `aria-valuetext="N sharpening rounds"`.
- **Accessible Select & Form Controls**: Reviewer concurrency selector and toggles use Radix UI primitives with full keyboard arrow navigation, `Escape` key close, and associated `<Label htmlFor={...}>`.
- **Estimate Telemetry**: Live readout container is configured with `aria-live="polite"` announcing latency and memory estimates as concurrency and round parameters adjust.

### 8. Harness² Recursive Scaffolding Controls & Calibration Card (`src/components/settings/harness-settings.tsx`, `src/components/ai-elements/harness-calibration-card.tsx`, `src/components/chat/chat-interface.tsx`)
- **Form Controls & Confirmation Modals**: Calibration toggles use Radix `Switch` bound via `useId()` and `<Label htmlFor={...}>`. Numeric bounds (`max_candidates`, `probe_max_steps`) use native `<Input type="number">` with `min`/`max` constraints. Destructive Reset/Rollback actions require confirmation via Radix `Dialog` with focus trapping and `Escape` dismissal.
- **Disclosures & Semantic Tables**: The 8-component overlay inspector uses native `<button aria-expanded aria-controls>` disclosures. Snapshot history and Level 2 `EXPERIENCE` entries use semantic `<table>`, `<caption>`, `<th scope="col">`, and `<th scope="row">` inside `tabIndex={0}` horizontal scroll containers.
- **Non-Reliance on Color & Live Status**: `HarnessCalibrationCard` pairs role icons (`aria-hidden="true"`) with explicit textual tags (`[PROPOSE]`, `[PROBE]`, `[COMPOSE]`, `[DISTILL]`, `[GUARDRAIL BLOCKED]`) and `aria-busy={isRunning}` without stealing focus. `Calibrate Harness` toggle in `ChatInterface` includes `aria-pressed={harnessCalibrate}`.
