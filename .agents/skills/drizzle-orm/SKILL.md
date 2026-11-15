---
name: drizzle-orm
description: Official Drizzle ORM runbook for pg-core and sqlite-core schemas, relations, queries, and drizzle-kit migrations.
version: 1.0.0
---

# Drizzle ORM Runbook

- **Dual-Dialect Schema**: Define PostgreSQL tables in `src/db/schema.pg.ts` (`drizzle-orm/pg-core`) and SQLite tables in `src/db/schema.sqlite.ts` (`drizzle-orm/sqlite-core`), re-exported from `src/db/schema.ts`.
- **Canonical Client (`src/db/index.ts`)**: Import `db` from `@/db`. It automatically selects `drizzle-orm/node-postgres` (`DB_DIALECT=postgresql`) or `drizzle-orm/better-sqlite3` (`DB_DIALECT=sqlite`) with global singleton pooling.
- **Indexes & Foreign Keys**: Always add explicit `.references(() => parent.id, { onDelete: "cascade" })` and `index(...)` on foreign-key and lookup columns.
- **Schema Workflows**: Use `drizzle_kit(action="push")` during rapid workspace prototyping, or `drizzle_kit(action="generate")` + `drizzle_kit(action="migrate")` for versioned migrations. Run `drizzle_kit(action="check")` to catch destructive drops.
- **No Competing ORMs**: Never install or import `prisma`, `typeorm`, `sequelize`, or `mongoose`.
