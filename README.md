# Buddhi AI Studio

An AI Agent Development Environment consisting of a Next.js frontend and a FastAPI backend.

## Project Structure

The project is structured as a monorepo-style application, where the root directory orchestrates both the frontend and backend components.

- `core/`: Contains the FastAPI backend source code.
    - `database/`: SQLAlchemy engine, session management, and base models.
    - `migrations/`: Alembic configuration and version scripts.
    - `models/`: SQLAlchemy database models.
    - `routers/`: FastAPI route handlers (Chat, Downloads, etc.).
    - `schemas/`: Pydantic models for request/response validation.
    - `services/`: Core logic for model downloads, inference, and caching.
- `src/`: Contains the Next.js frontend code using the App Router.
- `data/`: Default directory for SQLite database and downloaded AI models.
- `package.json`: Manages scripts and Node.js dependencies.
- `pyproject.toml`: Manages Python dependencies using `uv`.

## Technologies

- **Frontend**: [Next.js 16](https://nextjs.org/), [React 19](https://react.dev/), [Tailwind CSS 4](https://tailwindcss.com/).
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/), [SQLAlchemy 2.0](https://www.sqlalchemy.org/), [Alembic](https://alembic.sqlalchemy.org/).
- **Model Inference**: [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) for running GGUF models.
- **Package Management**: [pnpm](https://pnpm.io/) for Node.js and [uv](https://github.com/astral-sh/uv) for Python.

## Prerequisites

Ensure you have the following installed on your machine:

- **Node.js**: Version 20 or higher.
- **pnpm**: Version 9 or higher.
- **Python**: Version 3.12 or higher.
- **uv**: A high-performance Python package installer and resolver.

## Development Setup

1.  **Clone the Repository**:
    ```bash
    git clone <repository-url>
    cd buddhi-ai-studio
    ```

2.  **Run Initial Setup**:
    The project uses a unified setup script to install all dependencies for both the frontend and the backend.
    ```bash
    pnpm run setup:project
    ```
    This command will:
    - Install Node.js dependencies via `pnpm install`.
    - Create a Python virtual environment and install dependencies via `uv sync`.

## Running the Application

You can start both the frontend and backend development servers simultaneously using a single command:

```bash
pnpm run dev
```

- **Frontend**: Accessible at [http://localhost:3434](http://localhost:3434)
- **Backend (API)**: Accessible at [http://localhost:8484](http://localhost:8484)

The backend is configured with CORS to allow requests from the frontend development server.

## Core Services

### Model Management
- **Download Service**: Handles threaded downloads from HuggingFace Hub with progress reporting via a shared queue.
- **Inference Service**: Manages loading and running GGUF models using `llama-cpp-python`. Supports streaming responses.
- **Model Cache**: Implements an LRU-style cache for loaded models to optimize memory usage.

### Database & Migrations
The application uses SQLite by default, stored in `./data/buddhi.db`. Tables are automatically created on startup, but [Alembic](https://alembic.sqlalchemy.org/) is used for versioned migrations.

- **Create a migration**:
  ```bash
  uv run alembic revision --autogenerate -m "description of changes"
  ```
- **Apply migrations**:
  ```bash
  uv run alembic upgrade head
  ```

## Environment Variables

You can configure the application by creating a `.env` file in the root directory.

| Variable | Description | Default |
| :--- | :--- | :--- |
| `HF_TOKEN` | HuggingFace API token for gated models. | `None` |
| `HF_MODELS_DIR` | Directory to store downloaded models. | `./data/models` |
| `DATABASE_URL` | SQLAlchemy database URL. | `sqlite:///./data/buddhi.db` |
| `INFERENCE_MAX_LOADED_MODELS` | Max models to keep in memory. | `2` |
| `INFERENCE_N_CTX` | Model context window size (tokens). | `4096` |
| `INFERENCE_N_GPU_LAYERS` | Layers to offload to GPU (0 = CPU only). | `0` |

## Key Scripts

- `pnpm run dev`: Starts both frontend and backend in development mode.
- `pnpm run setup:project`: Initializes the project by installing all necessary dependencies.
- `pnpm run build`: Builds the Next.js application for production.
- `pnpm run lint`: Runs ESLint for the frontend.

## Contributing

When adding new Python dependencies, use `uv add <package>` to update `pyproject.toml` and `uv.lock`. For frontend changes, adhere to the established Tailwind CSS 4 patterns.
