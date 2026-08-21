# Buddhi AI Studio

Buddhi AI Studio is a self-hosted personal AI agent studio: a Next.js frontend paired with a FastAPI backend for running local LLMs (via LiteRT), managing embedding models, chatting with your models, downloading/managing model files, and tracking usage through an analytics dashboard. Everything runs on your own machine — no external API keys required, though you can optionally supply a Hugging Face token to pull gated/private models.

## Tech Stack

**Frontend**
- Next.js 16 (App Router), React 19
- Tailwind CSS v4, shadcn/ui components
- pnpm as the package manager

**Backend**
- FastAPI (Python 3.12+)
- `uv` for dependency management
- Local LLM inference via LiteRT, local embeddings via `sentence-transformers`
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

Create `.env.local` in the project root and point it at the backend:

```
BACKEND_API_URL=http://localhost:8000
```

Then start the dev server:

```bash
pnpm dev
```

The frontend runs at [http://localhost:54321](http://localhost:54321).

## Running with Docker Compose

```bash
docker compose up
```

This starts both services:
- Frontend on host port `54321`
- Backend on host port `87654`

Optionally set `HF_TOKEN` in your environment before running to let the backend download gated/private Hugging Face models. You can also configure this token later at runtime from the Settings page instead of an env var.

## Environment Variables

| Variable | Used by | Purpose |
| --- | --- | --- |
| `BACKEND_API_URL` | Frontend | Base URL of the FastAPI backend that Next.js API routes proxy to |
| `HF_TOKEN` | Backend (optional) | Hugging Face token for downloading gated/private models. Can also be set via the in-app Settings page instead. |

## Scripts

```bash
pnpm dev     # start the Next.js dev server (port 54321)
pnpm build   # production build
pnpm start   # run the production build
pnpm lint    # run ESLint
```

## A Note on the Next.js Version

This project pins a modified version of Next.js with breaking API changes relative to the standard release. Before relying on documentation or training knowledge for Next.js APIs, check `node_modules/next/dist/docs/` and heed any deprecation notices there.
