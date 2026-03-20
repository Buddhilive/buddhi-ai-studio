import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.database.engine import create_db_tables
from core.models.download import ModelDownload
from core.routers.downloads import router as downloads_router
from core.database.engine import SessionLocal

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Application lifespan context manager."""
    # Startup
    try:
        create_db_tables()
        logger.info("Database tables created")

        # Mark any stale "downloading" records as "failed" on restart
        db = SessionLocal()
        try:
            stale_downloads = db.query(ModelDownload).filter(
                ModelDownload.status == "downloading"
            ).all()
            for download in stale_downloads:
                download.status = "failed"
                download.error_msg = "Server restarted during download"
            db.commit()
            if stale_downloads:
                logger.warning(
                    f"Marked {len(stale_downloads)} stale downloads as failed"
                )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise

    yield

    # Shutdown
    logger.info("Application shutting down")


app = FastAPI(
    title="Buddhi AI Studio",
    description="Buddhi AI Studio is an AI Agent Development Environment",
    version="0.0.1",
    lifespan=lifespan,
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


# Welcome GET route for app
@app.get("/")
def read_root():
    return {"message": "Welcome to Buddhi AI"}