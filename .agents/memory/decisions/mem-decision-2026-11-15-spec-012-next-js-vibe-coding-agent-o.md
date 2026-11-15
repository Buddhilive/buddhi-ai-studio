---
id: mem-decision-2026-11-15-spec-012-next-js-vibe-coding-agent-optimization-s
kind: decision
title: '2026-11-15 (spec 012): Next.js Vibe-Coding Agent Optimization & Service Tooling
  Architecture'
summary: '2026-11-15 (spec 012): Modular Vibe-Stack Agent Tools, Per-Workspace Postgres
  Provisioning, and Two-Tier Skill Loading Architecture'
status: stable
confidence: verified
scope: project
tags:
- agent
- vibe-stack
- nextjs
- postgres
- mcp
- skills
generated:
  by: buddhi-cli
  at: '2026-11-14T18:51:39.968148+00:00'
sources:
- id: src-1
  resource: backend/app/services/agent/tools.py
  content_hash: fac706215dcfd655e22479abf5d98a6c06a2f953f8c37d25a5af67adb1265150
- id: src-2
  resource: backend/app/services/agent/prompts.py
  content_hash: 431e2e8d49f62d41fb1a2b44b8b5a0e748a2fabbcae8e519fde87c61987ceb2b
- id: src-3
  resource: docker-compose.yml
  content_hash: 47032206dc46ea71ac776f7ed4e9bfcca8646f3f2c084ad8bb1d206d7a37eb73
---

# Summary

2026-11-15 (spec 012): Modular Vibe-Stack Agent Tools, Per-Workspace Postgres Provisioning, and Two-Tier Skill Loading Architecture

# Context & Rationale

For feature 012-optimize-buddhiai-coding:
1. Decouple `backend/app/services/agent/tools.py` (flagged at 0.0347 cohesion) into `vibe_tools.py` (SearXNG, Crawl4AI, Postgres/SQLite provisioning & querying, Next.js/Shadcn/Drizzle/BetterAuth CLI/MCP bridges), `skill_loader.py` (two-tier selective skill injection + `load_skill` tool bounded by `harness_experience_token_budget`), and `vibe_starter.py` (Golden Starter workspace hydrator).
2. Provision isolated per-workspace PostgreSQL databases (`buddhi_app_<workspace_id>`) with least-privilege roles (`role_<workspace_id>`) using `psycopg.sql.Identifier` and track them in `harness.duckdb` (`provisioned_databases` table), injecting credentials out-of-band into `/workspace/.env` and redacting `postgresql://` URIs and `BETTER_AUTH_SECRET` in `redaction.py`.
3. Enforce the locked Next.js 16+ Vibe-Coding Stack (Next.js App Router, Tailwind CSS v4 with DESIGN.md OKLCH tokens, shadcn/ui, Drizzle ORM, Postgres/SQLite, BetterAuth, Vercel AI SDK with local Buddhi LLM default) via both `SYSTEM_HARNESS_PROMPT` and deterministic `check_vibe_stack_guardrail` checks in `execute_tool()`.
