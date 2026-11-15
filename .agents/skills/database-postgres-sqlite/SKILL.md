---
name: database-postgres-sqlite
description: Runbook for provisioning isolated Postgres databases on the studio Postgres service or configuring workspace SQLite databases.
version: 1.0.0
---

# PostgreSQL & SQLite Provisioning Runbook

- **Postgres Default**: For any app needing persistence or authentication, call `provision_postgres_db(dialect="postgresql")` FIRST. This idempotently creates an isolated database and least-privilege role on the Postgres service and injects `DATABASE_URL`, `DB_DIALECT=postgresql`, and `BETTER_AUTH_SECRET` into `/workspace/.env`.
- **SQLite Mode**: When the user explicitly requests SQLite or lightweight local file storage, call `provision_postgres_db(dialect="sqlite")` to configure `DB_DIALECT=sqlite` and `DATABASE_URL=file:./local.db`.
- **Verification**: After pushing your Drizzle schema with `drizzle_kit(action="push")`, verify tables and seed data using `query_database(sql="SELECT ...", dialect="postgresql" | "sqlite")`.
- **Security**: Never hardcode credentials in source files; always read `process.env.DATABASE_URL` and `process.env.DB_DIALECT`.
