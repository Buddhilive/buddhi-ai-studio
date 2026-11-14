---
id: mem-decision-2026-11-13-spec-009-elephant-goldfish-model-egm-langgraph-ar
kind: decision
title: '2026-11-13 (spec 009): Elephant-Goldfish Model (EGM) LangGraph Architecture'
summary: Opt-in EGM spec-first LangGraph workflow with zero-context GoldfishRunner,
  DuckDB BLOB checkpointer + sandbox dual storage, and fail-closed verification.
status: stable
confidence: verified
scope: project
tags:
- egm
- langgraph
- goldfish
- checkpointer
- spec-009
generated:
  by: buddhi-cli
  at: '2026-11-13T13:20:12.940972+00:00'
sources:
- id: src-1
  resource: backend/app/services/agent/graph.py
  content_hash: b5ebe0f60760a8019950409bf303b28de90a5af23de76650ad1a49ecc166c2d3
- id: src-2
  resource: backend/app/services/agent/checkpointer.py
  content_hash: 6da35d698008b49200e75edde1a9f867e76226cf5064964d9f1d377bda448bb4
- id: src-3
  resource: backend/app/services/agent/tools.py
  content_hash: 65ea56eeeca0dde68ceb9f10e009539fd2299c65cb7843daa38ee2077565a9cb
---

# Summary

Opt-in EGM spec-first LangGraph workflow with zero-context GoldfishRunner, DuckDB BLOB checkpointer + sandbox dual storage, and fail-closed verification.

# Context & Rationale

## Context
Spec 009 (`009-elephant-goldfish-coding`) adapts Google's Elephant-Goldfish Model (EGM) to the LangGraph coding agent (`backend/app/services/agent/`).

## Decisions
1. **Opt-In Unified StateGraph**: EGM runs as an opt-in mode (`is_egm_mode=True`) inside the existing `StateGraph(AgentState)` with `interrupt_before=["resolve"]`, keeping default mode (`is_egm_mode=False`) 100% unchanged.
2. **Type-Isolated GoldfishRunner & RLM Token Slicing**: `GoldfishRunner` accepts only frozen value objects (`GoldfishReviewInput`, `GoldfishVerifyInput`), never `AgentState` or `messages`. Reviewer token budget is computed dynamically from `settings_store.get_inference_settings()['max_num_token'] - 2048` and sliced into 2048-token chunks with line anchors.
3. **Dual Artifact Persistence & DuckDB Checkpointer**: `DuckDBCheckpointSaver` persists `Checkpoint` and pending writes as BLOBs in `agent_checkpoints.duckdb`, while EGM markdown artifacts (`spec.md`, `goldfish_review_report.md`, `concepts_brief.md`, `drift_report.md`) are stored in both `AgentState["egm_artifacts"]` and `/workspace/.buddhi/specs/<run_id>/` inside OpenSandbox (with automatic re-hydration if the sandbox expires during human triage).
4. **Hard Tool Write Guardrails & Fail-Closed Verifier**: Phases 1-4 lock `write_file` to `.buddhi/specs/<run_id>/`; Phase 5 locks writes to `SpecContract.target_scope_files`; `goldfish_verify` fails closed (`verdict="retry"`) when evidence or verdict parsing fails.
