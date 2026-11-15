---
name: shadcn-ui
description: Official shadcn/ui component library and MCP registry runbook for accessible, typed UI primitives.
version: 1.0.0
---

# shadcn/ui Runbook

- **Pre-Installed Core Primitives**: `src/components/ui/` includes `button`, `input`, `label`, `card`, `dialog`, `table`, `badge`, `alert`, `textarea`, and `tabs` configured via `components.json` (`style: "base-nova"`).
- **Adding Components via MCP/CLI**: Use `shadcn_registry(action="add", components=["..."])` (which runs `npx shadcn@latest add ... --yes`) or `shadcn_registry(action="view", components=["..."])` to inspect props before using unfamiliar components.
- **Accessibility Contract (WCAG 2.2 AA)**:
  - Pair every `<Input>` / `<Textarea>` with a visible `<Label htmlFor={id}>` bound via `useId()`.
  - Use `aria-invalid` + `aria-errormessage` for form validation errors.
  - Give icon-only `<Button size="icon">` controls an explicit `aria-label`.
  - Never use competing UI libraries (`@mui/material`, `@chakra-ui/react`, `bootstrap`).
