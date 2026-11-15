import { defineConfig } from "drizzle-kit";

const dialect = (process.env.DB_DIALECT as "postgresql" | "sqlite") || "postgresql";

export default defineConfig({
  schema: dialect === "sqlite" ? "./src/db/schema.sqlite.ts" : "./src/db/schema.pg.ts",
  out: "./drizzle",
  dialect,
  dbCredentials: {
    url:
      process.env.DATABASE_URL ??
      (dialect === "sqlite"
        ? "file:./local.db"
        : "postgresql://buddhi:changeme-postgres-password@postgres:5432/buddhi_app_default"),
  },
  strict: true,
  verbose: true,
});
