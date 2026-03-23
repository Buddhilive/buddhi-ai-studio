import asyncio
import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import StreamingResponse

from core.schemas.download import DownloadRequest, ModelRecord
from core.services.download_service import (
    PullEntry,
    pull_store,
    sanitize_id,
    do_pull,
    delete_ollama_model,
    get_ollama_models,
)

router = APIRouter(prefix="/models", tags=["models"])
logger = logging.getLogger(__name__)


@router.post("/download", status_code=status.HTTP_202_ACCEPTED, response_model=ModelRecord)
async def request_model_pull(
    request: DownloadRequest,
    background_tasks: BackgroundTasks,
) -> ModelRecord:
    """
    Start a new Ollama model pull.

    Returns 202 Accepted if the pull is queued.
    Returns 409 Conflict if a pull is already active for this model.
    """
    entry_id = sanitize_id(request.model)

    existing = pull_store.get(entry_id)
    if existing and existing.status in ("pending", "pulling"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Pull already in progress for {request.model}",
        )

    entry = PullEntry(
        id=entry_id,
        model=request.model,
        name=request.model.split(":")[0],
        status="pending",
        percentage=0,
    )
    pull_store[entry_id] = entry

    background_tasks.add_task(do_pull, request.model)

    logger.info(f"Pull queued: {request.model}")
    return ModelRecord(**entry.to_dict())


@router.get("", response_model=list[ModelRecord])
async def list_models() -> list[ModelRecord]:
    """
    List all models: active/failed pulls from pull_store plus any
    Ollama-installed models not yet in the store.
    """
    # Merge Ollama's installed list into pull_store (completed entries)
    installed = get_ollama_models()
    for m in installed:
        name = m.get("name", "")
        if not name:
            continue
        entry_id = sanitize_id(name)
        if entry_id not in pull_store:
            pull_store[entry_id] = PullEntry(
                id=entry_id,
                model=name,
                name=name.split(":")[0],
                status="completed",
                percentage=100,
            )

    return [ModelRecord(**entry.to_dict()) for entry in pull_store.values()]


# IMPORTANT: specific routes must come before /{model_id:path}

@router.get("/{model_id:path}/progress")
async def stream_pull_progress(model_id: str):
    """Stream pull progress via Server-Sent Events (SSE). Polls pull_store every second."""

    async def event_stream():
        normalized = model_id.replace("/", "_")
        try:
            while True:
                entry = pull_store.get(normalized)
                if not entry:
                    break
                yield f"data: {json.dumps(entry.to_dict())}\n\n"
                if entry.status in ("completed", "failed"):
                    break
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
async def get_model(model_id: str) -> ModelRecord:
    """Get a specific model record by sanitized model ID."""
    normalized = model_id.replace("/", "_")
    entry = pull_store.get(normalized)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    return ModelRecord(**entry.to_dict())


@router.delete("/{model_id:path}", response_model=ModelRecord)
async def delete_model(model_id: str) -> ModelRecord:
    """Delete a model from Ollama and remove it from pull_store."""
    normalized = model_id.replace("/", "_")
    entry = pull_store.get(normalized)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    record = ModelRecord(**entry.to_dict())

    if entry.status == "completed":
        try:
            delete_ollama_model(entry.model)
        except Exception as e:
            logger.error(f"Failed to delete Ollama model {entry.model}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete model from Ollama: {e}",
            )

    del pull_store[normalized]
    logger.info(f"Removed model entry: {entry.model}")
    return record
