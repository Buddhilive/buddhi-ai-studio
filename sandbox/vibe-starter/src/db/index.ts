import Database from "better-sqlite3";
import { drizzle as drizzlePg } from "drizzle-orm/node-postgres";
import { drizzle as drizzleSqlite } from "drizzle-orm/better-sqlite3";
import { Pool } from "pg";
import * as pgSchema from "./schema.pg";
import * as sqliteSchema from "./schema.sqlite";

const dialect = process.env.DB_DIALECT === "sqlite" ? "sqlite" : "postgresql";
const globalForDb = globalThis as unknown as {
  pgPool?: Pool;
  sqliteDb?: Database.Database;
};

function createDb() {
  if (dialect === "sqlite") {
    const dbFile = (process.env.DATABASE_URL ?? "file:./local.db").replace(/^file:/, "");
    const sqlite = globalForDb.sqliteDb ?? new Database(dbFile);
    sqlite.pragma("journal_mode = WAL");
    sqlite.pragma("foreign_keys = ON");
    if (process.env.NODE_ENV !== "production") {
      globalForDb.sqliteDb = sqlite;
    }
    return drizzleSqlite(sqlite, { schema: sqliteSchema });
  }

  const pool =
    globalForDb.pgPool ??
    new Pool({
      connectionString: process.env.DATABASE_URL,
      max: 10,
    });
  if (process.env.NODE_ENV !== "production") {
    globalForDb.pgPool = pool;
  }
  return drizzlePg(pool, { schema: pgSchema });
}

export const db = createDb();
