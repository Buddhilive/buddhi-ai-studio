# AGENTS.md

> Project instructions and conventions for AI coding agents.

## Overview
- **Project**: [PROJECT_NAME]
- **Type**: [e.g., CLI / Web Service / Library]
- **Primary Language/Runtime**: [e.g., Python >= 3.10 / TypeScript / Rust]

## Commands
- **Install**: [e.g., `uv sync` / `npm install`]
- **Build**: [e.g., `uv build` / `npm run build`]
- **Test**: [e.g., `uv run pytest` / `npm test`]
- **Lint & Format**: [e.g., `uv run ruff check .` / `npm run lint`]
- **Typecheck**: [e.g., `uv run mypy src/` / `npx tsc --noEmit`]

- **Knowledge Base & Code Graph**: Consult `.buddhi/docs/` (OKF concept documentation) and use Buddhi MCP tools (`buddhi_search`, `buddhi_read`) before grepping raw source files.
- **Spec-Driven Development (SDD)**: Features follow the SDD lifecycle:
  1. `/specify` — create feature branch and refine `spec.md`
  2. `/plan` — synthesize technical architecture into `plan.md`
  3. `/tasks` — break down tasks by user story in `tasks.md`
  4. `/implement` — execute tasks story by story
  5. `/verify` — prove working behavior with real test evidence
- **Lightweight Planning**: Use `/quick-plan` for quick, non-SDD changes.

## Engineering Principles & Non-Negotiables
1. **Grounded Changes**: Ground all edits in real file paths and existing codebase conventions.
2. **Evidence-Based Verification**: Always run verification commands through `terminal-runner` and report actual exit codes and stdout/stderr output.
3. **Clean Code & Typings**: Preserve type annotations, docstrings, and existing comments.
