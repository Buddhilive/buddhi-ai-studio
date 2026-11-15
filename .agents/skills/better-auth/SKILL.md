---
name: better-auth
description: Official BetterAuth runbook for Drizzle ORM integration, App Router catch-all handler, and React authClient hooks.
version: 1.0.0
---

# BetterAuth Runbook

- **Server Instance (`src/lib/auth.ts`)**: Configure `betterAuth({ database: drizzleAdapter(db, { provider: isSqlite ? "sqlite" : "pg", schema }), emailAndPassword: { enabled: true } })`.
- **Route Handler (`src/app/api/auth/[...all]/route.ts`)**: Export `export const { GET, POST } = toNextJsHandler(auth);`.
- **Client SDK (`src/lib/auth-client.ts`)**: Export `createAuthClient({ baseURL: process.env.NEXT_PUBLIC_APP_URL })` and hooks (`useSession`, `signIn`, `signUp`, `signOut`).
- **Server Session Protection**: In Server Components / Server Actions / Route Handlers, call `await auth.api.getSession({ headers: await headers() })` and redirect or return `401` when `session` is null.
- **Schema Sync**: Core tables (`user`, `session`, `account`, `verification`) are pre-wired in `src/db/schema.*.ts`. If you add BetterAuth plugins (e.g. organization, twoFactor), run `better_auth_cli(action="generate")` then `drizzle_kit(action="push")`.
