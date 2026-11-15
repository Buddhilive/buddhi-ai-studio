import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { db } from "@/db";
import * as pgSchema from "@/db/schema.pg";
import * as sqliteSchema from "@/db/schema.sqlite";

const isSqlite = process.env.DB_DIALECT === "sqlite";

export const auth = betterAuth({
  database: drizzleAdapter(db, {
    provider: isSqlite ? "sqlite" : "pg",
    schema: isSqlite ? sqliteSchema : pgSchema,
  }),
  emailAndPassword: {
    enabled: true,
  },
});
