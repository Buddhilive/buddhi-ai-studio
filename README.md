# Buddhi AI Studio

Buddhi AI Studio is a user-friendly desktop application designed to simplify the process of discovering, downloading, and running the Gemma family of open models. It provides an intuitive graphical interface for interacting with powerful AI models locally on your machine.

## Project Status

This project is in the early stages of development. The core structure is in place, but many features are still under construction.

## Project Structure

The application is built with a modern stack, separating the frontend and backend concerns:

-   **`src/`**: Contains the frontend application built with [Next.js](https://nextjs.org/) and [React](https://react.dev/).
-   **`src-pyloid/`**: Contains the backend service built with Python, which handles model management, server operations, and other core logic.

## Getting Started

Follow these instructions to set up your local development environment.

### Prerequisites

Make sure you have the following tools installed on your system:

-   [Node.js](https://nodejs.org/) (v20 or higher recommended)
-   [pnpm](https://pnpm.io/) package manager
-   [Python](https://www.python.org/) (v3.9 or higher recommended)
-   [uv](https://github.com/astral-sh/uv) - An extremely fast Python package installer and resolver.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd buddhi-ai-studio
    ```

2.  **Run the setup script:**

    This single command will install both the frontend (Node.js) and backend (Python) dependencies.
    ```bash
    pnpm run setup:project
    ```
    This script executes the following steps:
    - Installs Node.js packages using `pnpm install`.
    - Creates a Python virtual environment in `.venv/` using `uv venv`.
    - Installs Python packages into the virtual environment using `uv sync`.

## Running the Application

To run the application in development mode, use the following command:

```bash
pnpm run dev
```

This will start both the Next.js frontend development server and the Python backend service concurrently. The application window should open automatically once the services are ready.

## Building the Application

To build the application for production, run:

```bash
pnpm run build
```

This command bundles the Next.js frontend and prepares the Python backend for packaging into a distributable desktop application.