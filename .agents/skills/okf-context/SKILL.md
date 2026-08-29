---
name: okf-context
description: Use the codebase's generated OKF documentation under .buddhi/docs/ and Buddhi MCP code-graph tools as the first source of truth for understanding code, before reading raw source files.
when_to_use: "Whenever you need to explain, navigate, search, or reason about how this codebase works — before grepping or reading raw source files for context."
allowed-tools: view_file, grep_search
version: 1.1.0
---

# Prefer OKF docs and Buddhi MCP tools over re-reading raw source

This codebase has (or can have) machine-generated, dependency-aware documentation
under `.buddhi/docs/`, written as Open Knowledge Format (OKF) markdown, along with a
connected Buddhi MCP server providing graph-aware code search and reading. Reading these
first is cheaper and more reliable than re-deriving understanding from raw source every time.

## How to use it

1. **Check OKF documentation**: Start at `.buddhi/docs/index.md` (bundle root) to see what's
   documented, then descend into the relevant subdirectory's own `index.md`.
   Open concept `.md` files to inspect module summaries, entities, and call relationships.
2. **Query the code graph via MCP tools**:
   - **`buddhi_search(query, mode="full"|"signatures"|"map")`**:
     Use this for structural questions ("what calls this", "what depends on this", finding
     symbols or architectural components). It performs community-aware, topology-driven
     retrieval across the code graph.
   - **`buddhi_read(filepath, mode="auto"|"signatures"|"map", budget=4000)`**:
     Use this to inspect source files with AST pruning and entropy filtering to stay within
     token budget while preserving critical structure and type signatures.
3. **Graceful fallback**: If the Buddhi MCP server is not active or docs are missing/stale,
   fall back to querying `.buddhi/graphs/tree-graph.db` / `tree-graph.json` directly or
   reading raw source files.
4. **Maintain freshness**: If you generate or substantially change code such that existing OKF
   docs go stale, suggest running the `/document-codebase` workflow (see
   `repoagent-doc-generation` skill) to refresh the documentation and graph.

Never treat an OKF doc as authoritative over the actual source code — it's a cache of
understanding, not the ground truth. When the two conflict, the source wins and the
doc needs regenerating.

