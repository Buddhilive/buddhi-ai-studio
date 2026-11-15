---
name: tailwindcss-v4
description: Tailwind CSS v4 CSS-first styling runbook with @theme inline and DESIGN.md OKLCH semantic tokens.
version: 1.0.0
---

# Tailwind CSS v4 Runbook

- **CSS-First Configuration**: Import Tailwind via `@import "tailwindcss";` in `src/app/globals.css`. Never create `tailwind.config.js` or `tailwind.config.ts`.
- **Semantic OKLCH Tokens**: Map `DESIGN.md` tokens inside `@theme inline` (`--color-background`, `--color-foreground`, `--color-card`, `--color-primary`, `--color-secondary`, `--color-muted`, `--color-accent`, `--color-destructive`, `--color-border`, `--color-ring`).
- **Dark Mode**: Use `@custom-variant dark (&:is(.dark *));` and semantic color classes (`bg-background text-foreground`, `bg-card`, `text-muted-foreground`) rather than hardcoded hex/slate values.
- **Accessibility & Motion**: Preserve `:focus-visible` outlines (`outline-2 outline-offset-2 outline-ring`) and include `@media (prefers-reduced-motion: reduce)` guards.
- **Responsive Layout**: Build mobile-first (`flex-col`, `grid-cols-1 md:grid-cols-2 lg:grid-cols-3`) and avoid fixed pixel widths that overflow 375px viewports.
