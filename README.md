# Buddhi AI Studio

An AI Agent Development Environment consisting of a Next.js frontend and a FastAPI backend.

## Project Structure

The project is structured as a monorepo-style application, where the root directory orchestrates both the frontend and backend components.

- `core/`: Contains the FastAPI backend source code (`main.py`).
- `src/app/`: Contains the Next.js frontend code using the App Router.
- `package.json`: Manages scripts and Node.js dependencies for the entire project.
- `pyproject.toml`: Manages Python dependencies using `uv`.
- `.python-version`: Specifies the Python version (3.12+).

## Prerequisites

Ensure you have the following installed on your machine:

- **Node.js**: Version 20 or higher (recommended).
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

## Core Components

### Backend (FastAPI)
The backend is located in the `core/` directory. It uses FastAPI for a high-performance, asynchronous API.
- **Main Entry Point**: `core/main.py`
- **Dependencies**: Managed via `pyproject.toml` and `uv.lock`.

### Frontend (Next.js)
The frontend is a modern Next.js application located in the `src/` directory.
- **Framework**: Next.js 16 (App Router).
- **Styling**: Tailwind CSS 4.
- **Communication**: Interacts with the backend via JSON over HTTP.

## Key Scripts

- `pnpm run dev`: Starts both frontend and backend in development mode.
- `pnpm run setup:project`: Initializes the project by installing all necessary dependencies.
- `pnpm run build`: Builds the Next.js application for production.
- `pnpm run start`: Starts the production Next.js server.
- `pnpm run lint`: Runs ESLint for the frontend.

## Contributing

Please ensure that you have the latest versions of `pnpm` and `uv` installed to maintain consistency across development environments. When adding new Python dependencies, use `uv add <package>` to update `pyproject.toml` and `uv.lock`.
