---
id: mem-decision-2026-10-06-spec-006-user-generated-tool-output-e-g
kind: decision
title: '2026-10-06 (spec 006): User-generated tool output (e.g'
summary: '2026-10-06 (spec 006): User-generated tool output (e.g. Site Crawler projects)
  is stored in a RustFS (S3-compatible) container integrated li'
status: stable
confidence: verified
scope: project
tags:
- migrated-legacy
generated:
  by: buddhi-cli/migrate
  at: '2026-11-10T23:16:00.450367+00:00'
---

# Context & Rationale

2026-10-06 (spec 006): User-generated tool output (e.g. Site Crawler projects) is stored in a RustFS (S3-compatible) container integrated like Crawl4AI/OpenSandbox (compose + config + service client + health). Fixed docker volume only; files reach the user's PC via zip download from the UI, not host bind-mounts.
