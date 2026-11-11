<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# Buddhi AI Studio: Self-Hosted Autonomous Software Engineer & Factory

## Project Identity & Mission
Buddhi AI Studio is a **self-hosted, Docker-native Autonomous Software Engineer and Software Factory**. It is designed to run 100% on top of user-owned infrastructure without external API dependencies or data leakage:
- **Local Models**: CPU-targeted inference via Google LiteRT (`ai-edge-litert`), local GGUF/quantized weights, or local OpenAI-compatible endpoints (Ollama, vLLM).
- **Local Execution**: Isolated code and command execution inside containerized `OpenSandbox` sessions with full filesystem isolation.
- **Local Research & Docs**: Integrated self-hosted `SearXNG` metasearch and `Crawl4AI` headless browser crawling for live documentation.
- **Local Persistence**: S3-compatible `RustFS` object storage and DuckDB for project workspaces, traces, and metrics.

---

## Core Harness Architecture

### 1. LangGraph State Machine
The core execution harness is orchestrated via **LangGraph**:
- Replaces simple chat completion with an autonomous, cyclic state machine: `Analyze -> Plan -> Decompose -> Edit -> Sandbox Test -> Review -> Self-Correct -> Commit`.
- Employs typed state checkpoints, interruptible human-in-the-loop gates (Pause, Resume, Step), and deterministic branch routing.

### 2. Dual-Agent Cognitive Perspective (Google Elephant-Goldfish Model)
To eliminate self-confirmation bias and context rot:
- **Elephant Agent (Architect & Builder)**: Stateful, deep-context worker loaded with the repository's AST graph, project specification, and execution history. Decomposes goals and writes code.
- **Goldfish Agent (Zero-Context Reviewer & Verifier)**: Stateless, clean-slate worker spawned with zero prior chat memory. Inspects the isolated `[Spec Contract + Git Diff + Test Output]` to catch blind spots, unstated assumptions, and regressions with completely fresh eyes.

### 3. Adaptive Scaffolding (Google Harness²)
The harness dynamically adapts to unfamiliar codebases and languages by managing the **8 Editable Components** around frozen local foundation models:
1. `System Prompt` (Context construction)
2. `Guardrails` (Safety constraints & tool permissions)
3. `Memory` (Persistent OKF v0.2 knowledge & decisions)
4. `Skills` (Target language/framework specialized runbooks)
5. `Tool Guidance` (Parameter formatting and usage hints)
6. `Scripts` (Executable deterministic automation)
7. `Subagents` (Domain delegation)
8. `Plugins` (Middleware and service integrations)
Uses the **Propose-Probe-Compose** loop to calibrate the harness against repository test suites before full autonomous execution.

### 4. Recursive Language Modeling (RLM) for Context Scaling
Local 7B-14B models on CPU/consumer hardware suffer severe latency and context rot beyond 8k-16k tokens.
- **RLM Paradigm (MIT/CSAIL, arXiv:2512.24601)**: The prompt/repository is treated as an external environment variable inside an OpenSandbox Python REPL session rather than being stuffed raw into the LLM context window.
- The model writes code to programmatically inspect, slice, and search the repository structure, invoking small recursive LLM sub-calls on targeted 2k-token snippets and aggregating findings back to the root model.
- Enables effective context scaling over **two orders of magnitude (100x)** on limited local hardware.

---

## Guidelines for AI Coding Assistants Working on this Repo

1. **Grounded in Local Infrastructure**: Never introduce dependencies on external cloud APIs for core features. All services must spin up via `docker-compose.yml`.
2. **OpenSandbox as Ground Truth**: All code execution, testing, and file system mutations conducted by the autonomous agent must execute inside `OpenSandbox` container sessions, never on the host directly.
3. **Keep Context Lean**: When working with large files or test outputs, prefer RTK filtering or RLM programmatic slicing. Do not paste massive raw terminal logs into conversation context.
4. **Adhere to OKF & SDD**:
   - Specifications live under `.buddhi/specs/<branch>/`.
   - Architectural decisions and conventions are recorded in `.agents/memory/` using Google OKF v0.2 concept nodes.
   - Code changes must preserve documentation integrity and pass WCAG 2.2 AA accessibility in UI components.
