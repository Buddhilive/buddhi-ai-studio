---
name: nextjs-app-router
description: Canonical Next.js 16+ App Router runbook for BuddhiAI vibe-coding apps (RSC, Server Actions, async request APIs, and next-devtools-mcp diagnostics).
version: 1.0.0
---

# Next.js 16+ App Router Runbook

- **App Router Only**: Place all routes under `src/app/` (`page.tsx`, `layout.tsx`, `loading.tsx`, `error.tsx`, `route.ts`). Never create `pages/` or `src/pages/`.
- **Async Request APIs (Next.js 15/16+)**: Always `await params`, `await searchParams`, `await cookies()`, and `await headers()`.
- **Server vs. Client Boundaries**: Keep components as React Server Components (RSC) by default. Add `"use client"` only at leaf components requiring state, event handlers, `useChat`, or `authClient.useSession()`.
- **Mutations**: Prefer Server Actions (`"use server"`) with Zod validation and `revalidatePath()` / `revalidateTag()` for form/data mutations, or typed Route Handlers (`src/app/api/.../route.ts`) for streaming AI and BetterAuth endpoints.
- **Live MCP & Typecheck Diagnostics**: Run `nextjs_devtools(action="diagnostics")` (bridges `/_next/mcp` / `next-devtools-mcp` and falls back to `npx next typegen && npx tsc --noEmit`) before completing any task.
