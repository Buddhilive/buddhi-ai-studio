from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core import settings_store
from app.core.config import settings
from app.schemas.download import ModelDownloadState
from app.services.embedding_service import EmbeddingStatus, embedding_engine_manager

router = APIRouter(prefix="/api/embedding-model", tags=["embedding-model"])


class EmbeddingModelStatusResponse(BaseModel):
    model_id: str
    repo_id: str
    status: EmbeddingStatus
    error: str | None = None
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    percentage: float = 0.0
    current_phase: str | None = None
    files: dict[str, ModelDownloadState] = {}


def _status_response() -> EmbeddingModelStatusResponse:
    info = embedding_engine_manager.get_progress()
    return EmbeddingModelStatusResponse(
        model_id=settings.embedding_model_id,
        repo_id=settings.embedding_model_repo_id,
        status=info["status"],
        error=info["error"],
        downloaded_bytes=info["downloaded_bytes"],
        total_bytes=info["total_bytes"],
        percentage=info["percentage"],
        current_phase=info["current_phase"],
        files=info["files"],
    )


@router.get("/status", response_model=EmbeddingModelStatusResponse)
def get_embedding_model_status() -> EmbeddingModelStatusResponse:
    return _status_response()


@router.post("/download", status_code=status.HTTP_202_ACCEPTED, response_model=EmbeddingModelStatusResponse)
async def start_embedding_model_download() -> EmbeddingModelStatusResponse:
    if settings_store.get_hf_token() is None:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Hugging Face token is not configured. Set it on the Settings page first.",
        )
    embedding_engine_manager.trigger_download()
    return _status_response()


@router.post("/download/pause", response_model=EmbeddingModelStatusResponse)
def pause_embedding_model_download() -> EmbeddingModelStatusResponse:
    embedding_engine_manager.pause()
    return _status_response()


@router.post("/download/resume", status_code=status.HTTP_202_ACCEPTED, response_model=EmbeddingModelStatusResponse)
def resume_embedding_model_download() -> EmbeddingModelStatusResponse:
    embedding_engine_manager.resume()
    return _status_response()


@router.delete("/download", response_model=EmbeddingModelStatusResponse)
def cancel_embedding_model_download() -> EmbeddingModelStatusResponse:
    embedding_engine_manager.cancel()
    return _status_response()
