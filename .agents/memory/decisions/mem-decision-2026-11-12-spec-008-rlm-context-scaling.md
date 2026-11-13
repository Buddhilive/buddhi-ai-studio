---
okf_version: "0.2"
type: decision
date: 2026-11-12
title: "RLM Context Scaling Architecture with Ephemeral OpenSandbox Sessions"
---

# Decision: RLM Context Scaling Architecture

## Context
Running Gemma 4 E2B/E4B on CPU/consumer PCs with large repositories (200k+ tokens) causes context rot or out-of-memory errors due to KV-cache memory limits.

## Decision
1. **Existing OpenSandbox Container Reuse**: No dedicated container or long-lived daemon was introduced. We reuse the existing `opensandbox` container, creating ephemeral sandbox sessions with 256MB memory cap and read-only volume mounting.
2. **Network-Isolated Spool Bridge**: To execute `llm_query(snippet, subtask)` without granting internet or host network access to the untrusted sandbox, a file-spool protocol (`.rlm_spool/req-*.json` -> `.rlm_spool/res-*.json`) was implemented, serviced asynchronously by the harness.
3. **Stateless v1**: Chunk summaries are not persisted in DuckDB/RustFS in v1 to keep memory and complexity bounded, while strictly enforcing recursion depth (default 2) and subcall count budgets (default 32).
4. **Hardware-Calibrated Limits**: The settings UI context slider max is derived from actual free RAM vs active model weights (E2B 2.59GB vs E4B 3.66GB). Engine reloads trigger an accessible confirmation modal.
