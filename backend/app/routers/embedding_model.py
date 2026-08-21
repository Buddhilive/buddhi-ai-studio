from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.services.embedding_service import EmbeddingStatus, embedding_engine_manager

router = APIRouter(prefix="/api/embedding-model", tags=["embedding-model"])


class EmbeddingModelStatusResponse(BaseModel):
    model_id: str
    repo_id: str
    status: EmbeddingStatus
    error: str | None = None


def _status_response() -> EmbeddingModelStatusResponse:
    status, error = embedding_engine_manager.get_status()
    return EmbeddingModelStatusResponse(
        model_id=settings.embedding_model_id,
        repo_id=settings.embedding_model_repo_id,
        status=status,
        error=error,
    )


@router.get("/status")
def get_embedding_model_status() -> EmbeddingModelStatusResponse:
    return _status_response()


@router.post("/download")
async def start_embedding_model_download() -> EmbeddingModelStatusResponse:
    embedding_engine_manager.trigger_download()
    return _status_response()
