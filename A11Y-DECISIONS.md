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
