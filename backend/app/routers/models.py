import asyncio

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.schemas.download import DownloadStatus, ModelAvailability, ModelDownloadState
from app.services.model_download_service import model_download_manager

router = APIRouter(prefix="/api/models", tags=["models"])

_TERMINAL_STATUSES = {DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.IDLE}


@router.post("/download", status_code=status.HTTP_202_ACCEPTED, response_model=ModelDownloadState)
def start_download() -> ModelDownloadState:
    try:
        return model_download_manager.start()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not start download: {exc}",
        ) from exc


@router.post("/download/pause", response_model=ModelDownloadState)
def pause_download() -> ModelDownloadState:
    try:
        return model_download_manager.pause()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/download/resume", status_code=status.HTTP_202_ACCEPTED, response_model=ModelDownloadState)
def resume_download() -> ModelDownloadState:
    try:
        return model_download_manager.resume()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/download", response_model=ModelDownloadState)
def cancel_download() -> ModelDownloadState:
    try:
        return model_download_manager.cancel()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not remove partial download: {exc}",
        ) from exc


@router.get("/download/status", response_model=ModelDownloadState)
def get_download_status() -> ModelDownloadState:
    return model_download_manager.get_state()


@router.get("/download/progress")
async def stream_download_progress() -> StreamingResponse:
    async def event_stream():
        while True:
            state = model_download_manager.get_state()
            yield f"data: {state.model_dump_json()}\n\n"
            if state.status in _TERMINAL_STATUSES:
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/availability", response_model=ModelAvailability)
def get_availability() -> ModelAvailability:
    return model_download_manager.check_availability()
