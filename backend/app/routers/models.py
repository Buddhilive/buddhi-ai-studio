import asyncio

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core import settings_store
from app.core.model_catalog import MODEL_CATALOG, ModelCatalogEntry, get_catalog_entry
from app.schemas.download import ModelAvailability, ModelDownloadState
from app.services.model_download_service import model_download_manager

router = APIRouter(prefix="/api/models", tags=["models"])


def _resolve_model_id(model_id: str) -> None:
    try:
        get_catalog_entry(model_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/catalog", response_model=list[ModelCatalogEntry])
def get_catalog() -> list[ModelCatalogEntry]:
    return MODEL_CATALOG


@router.get("/status", response_model=list[ModelDownloadState])
def get_all_status() -> list[ModelDownloadState]:
    return model_download_manager.get_all_states()


@router.post(
    "/{model_id}/download", status_code=status.HTTP_202_ACCEPTED, response_model=ModelDownloadState
)
def start_download(model_id: str) -> ModelDownloadState:
    _resolve_model_id(model_id)
    if settings_store.get_hf_token() is None:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Hugging Face token is not configured. Set it on the Settings page first.",
        )
    try:
        return model_download_manager.start(model_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not start download: {exc}",
        ) from exc


@router.post("/{model_id}/download/pause", response_model=ModelDownloadState)
def pause_download(model_id: str) -> ModelDownloadState:
    _resolve_model_id(model_id)
    try:
        return model_download_manager.pause()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/{model_id}/download/resume", status_code=status.HTTP_202_ACCEPTED, response_model=ModelDownloadState
)
def resume_download(model_id: str) -> ModelDownloadState:
    _resolve_model_id(model_id)
    try:
        return model_download_manager.resume()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/{model_id}/download", response_model=ModelDownloadState)
def cancel_download(model_id: str) -> ModelDownloadState:
    _resolve_model_id(model_id)
    try:
        return model_download_manager.cancel()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not remove partial download: {exc}",
        ) from exc


@router.get("/download/progress")
async def stream_download_progress() -> StreamingResponse:
    async def event_stream():
        while True:
            states = model_download_manager.get_all_states()
            payload = "[" + ",".join(s.model_dump_json() for s in states) + "]"
            yield f"data: {payload}\n\n"
            if not any(s.status == "downloading" for s in states):
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/{model_id}/availability", response_model=ModelAvailability)
def get_availability(model_id: str) -> ModelAvailability:
    _resolve_model_id(model_id)
    return model_download_manager.check_availability(model_id)
