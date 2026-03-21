# AGENTS.md - Instructions for AI Coding Agents

This file provides specific technical context and instructions for AI coding agents (like Gemini CLI, Cursor, Aider, etc.) to operate effectively within this repository.

<!-- BEGIN:project-overview -->
## Project Overview
Buddhi AI Studio is an AI Agent Development Environment.
- **Backend:** FastAPI (Python 3.12+) using `uv` for dependency management.
- **Frontend:** Next.js 16 (App Router), React 19, and Tailwind CSS 4 using `pnpm`.
- **Database:** SQLite with SQLAlchemy 2.0 and Alembic for migrations.
- **Inference:** `llama-cpp-python` for running GGUF models locally.
<!-- END:project-overview -->

<!-- BEGIN:setup-commands -->
## Setup & Build Commands
Use these commands to prepare the environment and run the application:

- **Full Setup:** `pnpm run setup:project` (installs Node and Python dependencies).
- **Development:** `pnpm run dev` (starts both FastAPI and Next.js).
- **Backend Only:** `pnpm run dev:api` (port 8484).
- **Frontend Only:** `pnpm run dev:ui` (port 3434).
- **Linting:** `pnpm run lint`.
<!-- END:setup-commands -->

<!-- BEGIN:codebase-patterns -->
## Code Style & Conventions

### Backend (Python)
- **Pathing:** All backend code resides in the `core/` directory.
- **Schemas:** Always use Pydantic models in `core/schemas/` for request/response validation.
- **Services:** Business logic should be encapsulated in `core/services/`.
- **Database:** Use the `get_session` dependency from `core/database/deps.py` for database access in routers.
- **Migrations:** When modifying models in `core/models/`, always generate a new migration using `uv run alembic revision --autogenerate -m "..."`.

### Frontend (TypeScript/Next.js)
- **Framework:** Next.js 16 (App Router).
- **Styling:** Tailwind CSS 4.
- **Components:** UI components are located in `src/components/ui/` (Shadcn UI).
- **State Management:** Use Zustand for state management.
<!-- END:codebase-patterns -->

<!-- BEGIN:testing-instructions -->
## Testing Instructions
- **Backend Tests:** (To be implemented - check `tests/` directory if it exists).
- **Frontend Tests:** (To be implemented - use standard `vitest` or `jest` patterns).
<!-- END:testing-instructions -->

<!-- BEGIN:nextjs-agent-rules -->
## Next.js 16 Special Rules
This version of Next.js has breaking changes from previous versions.
- APIs, conventions, and file structures may differ from your training data.
- Read the documentation in `node_modules/next/dist/docs/` if you encounter unexpected behavior.
- Heed all deprecation notices in the console.
<!-- END:nextjs-agent-rules -->

<!-- BEGIN:pr-guidelines -->
## PR & Commit Guidelines
- **Commit Messages:** Use descriptive, imperative-style commit messages (e.g., "Add inference service for GGUF models").
- **Branching:** Use descriptive branch names like `feature/` or `fix/`.
- **Validation:** Always run `pnpm run lint` before finalizing changes.
<!-- END:pr-guidelines -->
