# Buddhi AI Studio

Buddhi AI Studio is primarily an LLM inferencing service for desktops, targeting CPU-based inference — no GPU required. A Next.js frontend pairs with a FastAPI backend to run local LLMs (via LiteRT) directly on your machine's CPU, alongside local embedding models, a chat UI, model download/management, and a usage analytics dashboard. No external API keys required, though you can optionally supply a Hugging Face token to pull gated/private models.

## Tech Stack

**Frontend**
- Next.js 16 (App Router), React 19
- Tailwind CSS v4, shadcn/ui components
- pnpm as the package manager

**Backend**
- FastAPI (Python 3.12+)
- `uv` for dependency management
- Local LLM inference via LiteRT (CPU-targeted), local embeddings via `sentence-transformers`
- DuckDB-backed usage metrics/analytics

## Project Structure

```
src/
  app/            App Router pages: dashboard (analytics), chat, downloads, settings
  app/api/        Route handlers that proxy requests to the FastAPI backend
  components/     UI components (ui/ shadcn primitives, ai-elements/, chat/, analytics/, custom/, nav)
  lib/            Utilities, including the backend proxy fetch helpers (lib/backend.ts)
  hooks/          Data-fetching hooks for models, embeddings, analytics

backend/
  app/            FastAPI application (entry point: app/main.py -> app.main:app)
```

The frontend never talks to the backend directly from the browser — Next.js API routes under `src/app/api/*` proxy requests server-side to the FastAPI backend using `BACKEND_API_URL`.

## Prerequisites

- Node.js (LTS) with `pnpm` (enable via `corepack enable`)
- Python 3.12+ with [`uv`](https://docs.astral.sh/uv/)

## Getting Started (local dev)

Run the backend and frontend as two separate processes.

**1. Backend**

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

**2. Frontend**

```bash
pnpm install
```

Copy `.env.example` to `.env` in the project root (adjust `BACKEND_API_URL` if your backend runs on a different port):

```bash
cp .env.example .env
```

Then start the dev server:

```bash
pnpm dev
```

The frontend runs at [http://localhost:54321](http://localhost:54321).

## Running with Docker Compose

Buddhi AI Studio can be run with Docker Compose either directly using pre-built images from Docker Hub or built locally from source.

### Quick Start (Pre-built Images)

Users can run Buddhi AI Studio without installing Node.js or Python:

```bash
# Start all services in the background
docker compose up -d
```

- Frontend: [http://localhost:54321](http://localhost:54321)
- Backend: [http://localhost:8765](http://localhost:8765) (docs at `/docs`)
- SearXNG: [http://localhost:8080](http://localhost:8080)

### Updating to the Latest Version

When a new version is released on Docker Hub, update your installation with:

```bash
docker compose pull
docker compose up -d
```

All persistent data (models, chat history, settings) is preserved in mounted volumes across updates.

### Pinning a Specific Version

To lock your deployment to a specific version instead of `:latest`, set `AI_STUDIO_VERSION` in your `.env` file or environment:

```env
AI_STUDIO_VERSION=0.2.0
```

### Publishing Images (Maintainers)

To build and publish new versioned images to Docker Hub (`buddhilive/ai-studio-service` and `buddhilive/ai-studio-ui`):

- **Linux / macOS / WSL / Git Bash**:
  ```bash
  ./scripts/publish-docker.sh 0.2.0
  ```
- **Windows (Command Prompt / PowerShell)**:
  ```cmd
  .\scripts\publish-docker.bat 0.2.0
  ```

If no version argument is passed, the script prompts for a version tag or automatically detects it from `package.json`. Both `<version>` and `latest` tags are built and pushed.

Optionally set `HF_TOKEN` in your environment (or in a root `.env`) before running to let the backend download gated/private Hugging Face models. You can also configure this token later at runtime from the Settings page instead of an env var.

## Environment Variables

Copy [`.env.example`](.env.example) to `.env` at the project root — it's used by the Next.js frontend, the FastAPI backend (via pydantic-settings), and `docker-compose.yml`.

| Variable | Used by | Purpose |
| --- | --- | --- |
| `BACKEND_API_URL` | Frontend | Base URL of the FastAPI backend that Next.js API routes proxy to |
| `HF_TOKEN` | Backend (optional) | Hugging Face token for downloading gated/private models. Can also be set via the in-app Settings page instead. |
| `CORS_ORIGINS` | Backend | JSON array of allowed CORS origins |
| `LITERT_BACKEND` | Backend | LiteRT inference backend (`cpu`) |
| `CHAT_MAX_TOKENS_DEFAULT` | Backend | Default max tokens for chat completions |
| `CHAT_REQUEST_TIMEOUT_S` | Backend | Chat request timeout, in seconds |
| `EMBEDDING_DEVICE` | Backend | Device used for local embedding models (`cpu`) |
| `EMBEDDING_MAX_BATCH_SIZE` | Backend | Max batch size for embedding requests |
| `ENABLE_TRACE_LOGGING` | Backend | Persist real prompt/response text per trace in Analytics > Traces |
| `TRACE_RETENTION_DAYS` | Backend | Days before trace prompt/response text is purged |
| `ENABLE_PROMETHEUS_METRICS` | Backend | Expose the `/metrics` Prometheus endpoint |

## Scripts

```bash
pnpm dev     # start the Next.js dev server (port 54321)
pnpm build   # production build
pnpm start   # run the production build
pnpm lint    # run ESLint
```

## A Note on the Next.js Version

This project pins a modified version of Next.js with breaking API changes relative to the standard release. Before relying on documentation or training knowledge for Next.js APIs, check `node_modules/next/dist/docs/` and heed any deprecation notices there.
