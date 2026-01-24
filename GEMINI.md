# Gemini Code Assistant Context

This document provides context for the Gemini code assistant to understand the project structure, technologies, and conventions.

## Project Overview

**Buddhi AI Studio** is a desktop application designed for discovering, downloading, and running the Gemma family of open models. It provides a user-friendly graphical interface for interacting with powerful AI models locally on your machine.

The application consists of two main parts:

-   **Frontend:** A [Next.js](https://nextjs.org/) and [React](https://react.dev/) application located in the `src` directory. It uses [Tailwind CSS](https://tailwindcss.com/) for styling and [@radix-ui/react](https://www.radix-ui.com/) for accessible UI components.
-   **Backend:** A Python application located in the `src-pyloid` directory. It uses the [Pyloid](https://github.com/louis-br/pyloid) framework to create the desktop application window and manage the backend services.

The frontend and backend communicate using the `pyloid-js` library, which allows for seamless integration between the JavaScript and Python parts of the application.

## Building and Running the Application

The project uses `pnpm` as the package manager for Node.js and `uv` for managing the Python environment.

### Prerequisites

-   [Node.js](https://nodejs.org/) (v20 or higher)
-   [pnpm](https://pnpm.io/)
-   [Python](https://www.python.org/) (v3.9 or higher)
-   [uv](https://github.com/astral-sh/uv)

### Setup

To set up the project and install all dependencies, run the following command:

```bash
pnpm run setup:project
```

This command will:

1.  Install the Node.js dependencies using `pnpm install`.
2.  Create a Python virtual environment in the `.venv` directory using `uv venv`.
3.  Install the Python dependencies into the virtual environment using `uv sync`.

### Development

To run the application in development mode, use the following command:

```bash
pnpm run dev
```

This will start both the Next.js development server (on `http://localhost:5173`) and the Python backend service concurrently. The application window will open automatically and load the frontend from the Next.js development server.

### Building

To build the application for production, run the following command:

```bash
pnpm run build
```

This command will:

1.  Build the Next.js frontend and output the static files to the `dist-front` directory.
2.  Prepare the Python backend for packaging into a distributable desktop application.

## Development Conventions

-   **Frontend:**
    -   Follow the standard [Next.js](https://nextjs.org/docs) and [React](https://react.dev/learn) conventions.
    -   Use [Tailwind CSS](https://tailwindcss.com/docs) for styling.
    -   Use [@radix-ui/react](https://www.radix-ui.com/primitives/docs/overview/introduction) for building accessible UI components.
    -   Components are located in the `src/components` directory.
-   **Backend:**
    -   The backend is built using the [Pyloid](https://github.com/louis-br/pyloid) framework.
    -   The main entry point for the backend is `src-pyloid/main.py`.
    -   The backend is responsible for creating the application window, managing the system tray, and handling any backend-specific logic.
-   **Communication:**
    -   The frontend and backend communicate using the `pyloid-js` library.
    -   The `Pyloid` instance in the backend can expose functions to the frontend, and the frontend can call them.
