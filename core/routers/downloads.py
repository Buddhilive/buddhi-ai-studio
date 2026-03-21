import asyncio
import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import StreamingResponse

from core.schemas.download import DownloadRequest, ModelRecord
from core.services.download_service import DownloadEntry, download_store, do_download, sanitize_id

router = APIRouter(prefix="/models", tags=["models"])
logger = logging.getLogger(__name__)


@router.post("/download", status_code=status.HTTP_202_ACCEPTED, response_model=ModelRecord)
async def request_model_download(
    request: DownloadRequest,
    background_tasks: BackgroundTasks,
) -> ModelRecord:
    """
    Start a new model download from HuggingFace.

    Returns 202 Accepted if the download is queued successfully.
    Returns 409 Conflict if a download for this model is already pending or downloading.
    """
    entry_id = sanitize_id(request.model_id)

    # Check for existing active download
    existing = download_store.get(entry_id)
    if existing and existing.status in ("pending", "downloading"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Download already in progress for {request.model_id}",
        )

    # Create new entry
    entry = DownloadEntry(
        id=entry_id,
        repo_id=request.model_id,
        name=request.model_id.split("/")[-1] if "/" in request.model_id else request.model_id,
        quantization=request.quantization,
        status="pending",
        percentage=0,
        path=None,
        filename=None,
        error=None,
    )
    download_store[entry_id] = entry

    # Add background task
    hf_token = os.getenv("HF_TOKEN")
    background_tasks.add_task(do_download, request.model_id, request.quantization, hf_token)

    logger.info(f"Download queued: {request.model_id} ({request.quantization})")
    return ModelRecord(**entry.to_dict())


@router.get("", response_model=list[ModelRecord])
async def list_downloads() -> list[ModelRecord]:
    """List all model downloads."""
    return [ModelRecord(**entry.to_dict()) for entry in download_store.values()]


# IMPORTANT: More specific routes MUST come before the catch-all /{model_id:path} route
# Otherwise GET /download will match /{model_id:path} with model_id="download"


@router.get("/{model_id:path}/progress")
async def stream_download_progress(model_id: str):
    """
    Stream download progress via Server-Sent Events (SSE).
    Polls the in-memory download_store every 1 second.

    The model_id should be the sanitized form (repo_id with / replaced by _).
    """

    async def event_stream():
        """Generate SSE events for download progress."""
        try:
            # Normalize the model_id in case it comes with slashes
            normalized_id = model_id.replace("/", "_")

            while True:
                entry = download_store.get(normalized_id)
                if not entry:
                    logger.debug(f"Model {normalized_id} not found in download_store (got: {model_id})")
                    break

                # Yield current state
                data = entry.to_dict()
                yield f"data: {json.dumps(data)}\n\n"

                # Stop if terminal state
                if entry.status in ("completed", "failed", "corrupted"):
                    break

                # Poll interval
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            raise

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/{model_id:path}", response_model=ModelRecord)
async def get_download(model_id: str) -> ModelRecord:
    """Get a specific download record by model ID (sanitized repo ID)."""
    # Normalize the model_id in case it comes with slashes
    normalized_id = model_id.replace("/", "_")
    entry = download_store.get(normalized_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    return ModelRecord(**entry.to_dict())


@router.delete("/{model_id:path}", response_model=ModelRecord)
async def cancel_or_delete_download(model_id: str) -> ModelRecord:
    """
    Cancel a pending/downloading download or delete a completed entry.
    Also deletes the local .gguf and .verified files if they exist.
    """
    # Normalize the model_id in case it comes with slashes
    normalized_id = model_id.replace("/", "_")
    entry = download_store.get(normalized_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    record = ModelRecord(**entry.to_dict())

    # Delete local files if they exist
    if entry.path:
        try:
            gguf_path = Path(entry.path)
            if gguf_path.exists():
                gguf_path.unlink()
                logger.info(f"Deleted {gguf_path}")

            verified_path = gguf_path.with_suffix(gguf_path.suffix + ".verified")
            if verified_path.exists():
                verified_path.unlink()
                logger.info(f"Deleted {verified_path}")
        except Exception as e:
            logger.error(f"Failed to delete files for {model_id}: {e}")

    # Remove from store
    del download_store[normalized_id]
    logger.info(f"Removed download entry: {model_id}")

    return record
