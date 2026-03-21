import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# Diagnostic print at module level
print("--- [DIAGNOSTIC] core.main is being imported ---", file=sys.stderr, flush=True)

from core.database.engine import create_db_tables
from core.routers.downloads import router as downloads_router
from core.routers.chat import router as chat_router

# Configure a basic handler if none exists to ensure core logs appear
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.DEBUG, stream=sys.stderr, format="%(levelname)s:     %(message)s")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Application lifespan context manager."""
    print("--- [DIAGNOSTIC] lifespan startup beginning ---", file=sys.stderr, flush=True)
    # Startup
    try:
        # Scan local models directory and populate download_store
        from core.services.download_service import scan_models_dir
        scan_models_dir()
        logger.info("Download store initialized from disk")

        # Initialize model cache for inference
        from core.services.model_cache import init_model_cache
        from core.config import settings
        init_model_cache(max_models=settings.inference_max_loaded_models)
        logger.info("Model cache initialized")

    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise

    yield

    # Shutdown
    from core.services.model_cache import shutdown_model_cache
    shutdown_model_cache()
    logger.info("Application shutting down")


app = FastAPI(
    title="Buddhi AI Studio",
    description="Buddhi AI Studio is an AI Agent Development Environment",
    version="0.0.1",
    lifespan=lifespan,
    debug=True
)

# Not safe! Add your own allowed domains
origins = [
    "http://localhost:3434",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(downloads_router, prefix="/api/v1")
app.include_router(chat_router)  # No prefix - router already has /v1


@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"--- [DIAGNOSTIC] Request: {request.method} {request.url.path} ---", file=sys.stderr, flush=True)
    response = await call_next(request)
    print(f"--- [DIAGNOSTIC] Response: {response.status_code} ---", file=sys.stderr, flush=True)
    return response

@app.get("/ping")
def ping():
    print("--- [DIAGNOSTIC] PING received (stdout) ---", flush=True)
    print("--- [DIAGNOSTIC] PING received (__stdout__) ---", file=sys.__stdout__, flush=True)
    print("--- [DIAGNOSTIC] PING received (stderr) ---", file=sys.stderr, flush=True)
    print("--- [DIAGNOSTIC] PING received (__stderr__) ---", file=sys.__stderr__, flush=True)
    
    logger.info("--- [DIAGNOSTIC] PING received (core.main logger) ---")
    
    u_error = logging.getLogger("uvicorn.error")
    u_error.info("--- [DIAGNOSTIC] PING received (uvicorn.error logger) ---")
    
    root = logging.getLogger()
    root.warning("--- [DIAGNOSTIC] PING received (root logger) ---")
    
    return {"status": "pong", "handlers": [str(h) for h in root.handlers]}

# Welcome GET route for app
@app.get("/")
def read_root():
    return {"message": "Welcome to Buddhi AI"}