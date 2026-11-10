---
name: a11y
description: "Persistent Context System for Accessibility: 19-Rule AI Behavioral Contract, Compliance Profiles (Standard AA, Shield AAA, Launchpad A), WAI-ARIA APG component references, static verification gate, and release evidence."
version: 2.5.0
---

# a11y

> Adapted from Project A11Y.md (MIT License, Copyright (c) 2026 Felipe A. Carriço).
> Version: 2.5.0 | Target Standard: WCAG 2.2 AA (Shield AAA, Launchpad A)

This skill establishes the persistent context required so that software can be certified under **WCAG 2.2 AA**, **ISO 9241-171**, **ADA**, **EAA**, and **ABNT NBR 17225**, depending on rigorous implementation and **mandatory human validation**.

Most agent context teaches a *capability* — how to do something, loaded when the task calls for it. This skill defines a **constraint**: what may never be done, whatever you are building. It belongs in context before generating any UI code.

---

## 0. Principle Zero: Accessibility as Pre-condition

- Accessibility is not a feature or an incremental improvement; it is a **pre-condition for use**.
- If a user cannot complete a task due to an accessibility barrier, the feature is considered **technically broken**.
- **Task Completion** success is the primary quality metric.

## 0.1. Compliance Profiles

Default profile: **Standard (AA)**. When generating or reviewing interface code, confirm the profile with the user if not specified:

| Profile | Target | Contrast (text / UI) | Min Font† | Min Target | Use Case |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **🛡️ Shield (AAA)** | WCAG AAA | 7:1 / 3:1 (SC 1.4.6, 1.4.11) | 14px† | 44×44px (SC 2.5.5) · 48×48px† advised | Regulated industries, healthcare, gov |
| **⚖️ Standard (AA)** | WCAG AA | 4.5:1 / 3:1 (SC 1.4.3, 1.4.11) | 12px† | 24×24px (SC 2.5.8) · 44×44px† advised | Default. Production apps, public web |
| **🚀 Launchpad (A)** | WCAG A | 3:1† (house floor) | 10px† | 24×24px† | MVPs, internal tools, prototypes |

*† = A11Y.md rule (ergonomic baseline beyond WCAG minimums). Skipping a WCAG SC at your target level MUST be logged in `EXCEPTIONS.md`; relaxing an A11Y.md rule is a product decision recorded in `A11Y-DECISIONS.md`.*

> ⚠️ The **Launchpad (A)** profile does NOT relax CRITICAL rules. Keyboard operability, focus management, and semantic HTML remain mandatory at ALL levels.

---

## 1. Severity & Impact Model

- 🔴 **CRITICAL**: Operation failures blocking task completion (broken keyboard nav, click on div/span, modal without focus management). **MUST FIX.**
- 🟠 **HIGH**: Perception and readability failures (insufficient contrast, font < 12px in critical text, missing dynamic feedback). **MUST FIX.**
- 🟡 **MEDIUM**: Reduces efficiency and satisfaction (missing keyboard shortcuts, lack of redundant labels). **SHOULD FIX.**
- 🔵 **LOW**: Cosmetic or polish impact (micro-interactions without aria-labels, focus indicators needing contrast polish). **MAY FIX.**

---

## 2. 19-Rule AI Behavioral Contract

1. **No Inference**: Never infer accessibility without direct evidence in the code or specification.
2. **Lazy Context Loading**: Reference files in `references/` **MUST NOT** be preloaded — consult only the row of each component the interface contains per §2.1.
3. **Reference APG**: Prioritize patterns from the [WAI-ARIA Authoring Practices Guide (APG)](https://www.w3.org/WAI/ARIA/apg/).
4. **Protocol for Ambiguity**: Follow the Complex Component Protocol when a component lacks an established APG pattern.
5. **Explain Trade-offs**: Explicitly state impacts on Accessibility vs UX vs Business when proposing changes.
6. **UI Component Interrogation**: Propose replacing click-handled non-semantic elements with native buttons or full APG patterns.
7. **Image Evidence**: Resolve text alternatives with the developer before images enter code. Fabricating `alt` from filenames or defaulting to `alt=""` without confirmation is forbidden.
8. **Media Evidence**: Resolve captions, transcripts, and audio control before media enters code. Autoplay without pause or volume controls is 🔴 CRITICAL.
9. **Framework Adaptation**: Transpose patterns to the project's active framework (React, Vue, Svelte, HTML) while preserving semantic equivalence.
10. **Platform Awareness**: Identify target platform before loading references (web ARIA intent translates to native accessibility APIs on iOS, Android, Flutter).
11. **Cognitive Load**: Multi-step flows, auth, or time limits must enforce: nothing remembered across screens (SC 3.3.8), nothing re-typed (SC 3.3.7), consistent help location (SC 3.2.6). Never block paste on password fields.
12. **Conflicting Access Needs**: When needs collide (e.g. motion vs vestibular), implement user preferences (`prefers-reduced-motion`) or document trade-offs in `A11Y-DECISIONS.md`.
13. **Component Reuse**: Check existing components via `buddhi_search` or project design systems before creating new ones.
14. **Decision Memory**: Record choices between equally conformant alternatives in `A11Y-DECISIONS.md` indexed by pattern.
15. **Exception Memory**: Record knowingly accepted WCAG deviations in `EXCEPTIONS.md` with owner, approver, issue link, and expiry.
16. **Release Evidence**: Ensure `REPORT.md` exists and is newer than the last interface change before any delivery to an end user.
17. **Static Gate**: Run `buddhi scripts verify-a11y` via `terminal-runner` (or MCP tool `verify_a11y`) before delivery and record findings in `REPORT.md`.
18. **Independent Verification**: Reproduce Section 7 automated checkpoints with a verifier that did not generate the code (dispatch an unprimed subagent via `invoke_subagent` to achieve `fresh-context` verification).
19. **Mode Awareness**: Apply rules proactively when generating new code; prioritize targeted fixes by severity when reviewing existing code.

---

## 2.1. Lazy Loading Map (Component → Guide)

Load only the guide matching the component you are currently building or reviewing:

| Component Type | Reference Guide |
| :--- | :--- |
| button, CTA, clickable action, icon button | `references/guide-buttons.md` |
| form, field, validation, error message | `references/guide-forms.md` |
| checkbox, radio group, switch, toggle, slider, select | `references/guide-form-controls.md` |
| login, signup, multi-step flow, wizard, checkout | `references/guide-cognitive.md` |
| modal, dialog, drawer, confirmation | `references/guide-modals.md` |
| cookie banner, consent notice, privacy overlay | `references/guide-consent-banners.md` |
| menu, header, skip link, landmark, SPA routing | `references/guide-navigation.md` |
| table, data grid | `references/guide-tables.md` |
| tabs, accordion, disclosure, collapsible panel | `references/guide-tabs-accordion.md` |
| tooltip, popover, hover card | `references/guide-tooltips-popovers.md` |
| toast, snackbar, alert, status message | `references/guide-toasts-notifications.md` |
| skeleton, spinner, loading state, aria-busy | `references/guide-loading-skeleton.md` |
| autocomplete, combobox, searchable select | `references/guide-autocomplete.md` |
| carousel, slider, rotating banner | `references/guide-carousels-sliders.md` |
| drag and drop, list reordering, kanban | `references/guide-drag-drop.md` |
| infinite scroll, feed, pagination | `references/guide-infinite-scroll.md` |
| image, icon, SVG, avatar, illustration | `references/guide-images.md` |
| video, audio, player, background video | `references/guide-media.md` |
| chart, graph, dashboard, data visualization | `references/guide-charts.md` |
| date picker, calendar, date range | `references/guide-datepicker.md` |
| tree view, file explorer, nested picker | `references/guide-treeview.md` |
| chat, streaming AI assistant, generative UI | `references/guide-generative-ui.md` |
| map, store locator, route display | `references/guide-maps.md` |
| design tokens, color palette, theme config | `references/guide-visual-perception.md` |
| responsive layout, breakpoint, touch target | `references/guide-responsive-mobile.md` |
| iOS, Android, React Native, Flutter | `references/guide-platform-native.md` |
| non-React web frameworks (Vue, Svelte, Angular) | `references/guide-framework-mapping.md` |
| AI agents navigating product, llms.txt | `references/guide-agentic-web.md` |
| audit, VPAT, accessibility statement, CI gate | `references/guide-governance.md` |

**Lifecycle Templates (Loaded by Event)**:
- Delivery / QA: `templates/REPORT.md`
- Accepted WCAG deviation: `templates/EXCEPTIONS.md`
- Pattern choice: `templates/A11Y-DECISIONS.md`
- Public statement (GitHub Accessibility tab): `templates/ACCESSIBILITY.md`

---

## 3. Technical Standards (POUR Summary)

- **Perceivable**: Text contrast >= 4.5:1 (3:1 large, 3:1 UI components). Compute with `buddhi scripts contrast` or MCP `check_contrast`. Every `<img>` has `alt` (empty `alt=""` only for confirmed decorative images). Prerecorded media has captions. Sound > 3s has pause/mute controls.
- **Operable**: 100% keyboard operable (`Tab`, `Enter`, `Space`, `Escape`). Focus indicator visible (>= 2px, 3:1 contrast against background). Touch target >= 24x24px (AA), 44x44px recommended. Moving content > 5s has pause mechanism. Flashing <= 3 times/sec.
- **Understandable**: Language declared on `<html lang="...">`. Inputs have explicit `<label for="...">`. Error feedback uses Color + Icon + Text with `aria-live` or role alerts.
- **Robust**: Valid semantic HTML5 elements before custom ARIA.

---

## 4. Anti-patterns to Prevent (Section 6)

1. **Clickable Divs**: No `div` or `span` with click handlers without native `<button>` or complete keyboard replication (`role`, `tabindex="0"`, Enter/Space).
2. **Leaked Focus Traps**: Modals must trap focus, close on Escape, and restore focus to trigger.
3. **Placeholder as Only Label**: `<input>` must have a visible `<label>`.
4. **ARIA Soup**: No redundant roles (e.g. `role="button"` on `<button>`), no hardcoded static `aria-expanded` that script never toggles.
5. **Half-Climbed ARIA**: `role="tablist"` without `role="tab"` is strictly forbidden.
6. **Nullified Alt**: Never combine `aria-hidden="true"` or `role="presentation"` with a non-empty `alt`.
7. **Overlays**: Never propose third-party accessibility toolbar scripts as a fix.
8. **Positive Tabindex**: `tabindex > 0` is forbidden.
9. **Outline None**: Never set `outline: none` without a visible high-contrast replacement.
10. **Redundant Alert**: Never combine `role="alert"` with `aria-live`.
11. **Media Autoplay**: Unmuted autoplaying audio/video is forbidden.

---

## 5. Verification Commands

Run static gate and contrast verification through `terminal-runner` or MCP tools:

```bash
# Static gate check against project source and artifacts
buddhi scripts verify-a11y [project_dir] [--src subdir] [--warn-only]

# Contrast verification
buddhi scripts contrast <hex1> <hex2>
buddhi scripts contrast --bg "#ffffff" --fg "#1c1b19" "#767676" --profile standard
buddhi scripts contrast --css styles.css --page-bg "#ffffff"
```

