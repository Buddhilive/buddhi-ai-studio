"""API routes for model download operations."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from config import get_settings
from models import (
    DownloadRequest,
    DownloadResponse,
    DownloadState,
    ModelInfo,
    ProblemDetail,
)
from services import download_manager
from utils import create_sse_message, get_file_size

# Create router with prefix and tags
router = APIRouter(tags=["models"])


# ============================================================================
# Download Endpoints
# ============================================================================


@router.post(
    "/models/download",
    response_model=DownloadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Download initiated successfully"},
        400: {"model": ProblemDetail, "description": "Bad request"},
        409: {"model": ProblemDetail, "description": "Download already in progress"},
        422: {"model": ProblemDetail, "description": "Validation error"},
        500: {"model": ProblemDetail, "description": "Internal server error"},
    },
)
async def initiate_download(
    request: DownloadRequest,
    http_request: Request,
) -> DownloadResponse:
    """Initiate a model download from HuggingFace.
    
    This endpoint starts downloading a GGUF model from HuggingFace Hub.
    The download runs in the background and progress can be monitored via the SSE endpoint.
    
    Args:
        request: Download request with repo_id, filename, etc.
        http_request: FastAPI request object
        
    Returns:
        DownloadResponse with download_id and progress URL
        
    Raises:
        HTTPException: If validation fails or download cannot be started
    """
    try:
        # Start download
        task = await download_manager.start_download(
            repo_id=request.repo_id,
            filename=request.filename,
            repo_type=request.repo_type,
            token=request.token,
        )

        # Build progress URL
        base_url = str(http_request.base_url).rstrip("/")
        progress_url = f"{base_url}/api/models/download/{task.download_id}/progress"

        return DownloadResponse(
            download_id=task.download_id,
            status=task.state,
            message="Download initiated successfully",
            progress_url=progress_url,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except OSError as e:
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail=f"Insufficient disk space: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start download: {str(e)}",
        )


@router.get(
    "/models/download/{download_id}/progress",
    responses={
        200: {"description": "Server-Sent Events stream with progress updates"},
        404: {"model": ProblemDetail, "description": "Download not found"},
    },
)
async def stream_download_progress(download_id: str) -> StreamingResponse:
    """Stream real-time download progress via Server-Sent Events.
    
    This endpoint provides a continuous stream of progress updates for an active download.
    The client should use EventSource or similar to consume the SSE stream.
    
    Args:
        download_id: Unique download identifier
        
    Returns:
        StreamingResponse with text/event-stream content type
        
    Raises:
        HTTPException: If download_id is not found
    """
    # Verify download exists
    task = await download_manager.get_task(download_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Download {download_id} not found",
        )

    async def generate_events() -> AsyncGenerator[str, None]:
        """Generate SSE events for download progress.
        
        Yields:
            SSE formatted messages
        """
        settings = get_settings()
        
        try:
            while True:
                # Get current task state
                current_task = await download_manager.get_task(download_id)
                if not current_task:
                    break

                # Send progress update
                progress = current_task.to_progress_update()
                yield create_sse_message(progress.model_dump(), event="progress")

                # Check if download is complete or failed
                if current_task.state in [
                    DownloadState.COMPLETED,
                    DownloadState.FAILED,
                    DownloadState.CANCELLED,
                ]:
                    # Send final update
                    yield create_sse_message(
                        {"status": "complete", "final_state": current_task.state.value},
                        event="complete",
                    )
                    break

                # Wait before next update
                await asyncio.sleep(settings.progress_update_interval)

        except asyncio.CancelledError:
            # Client disconnected
            pass
        except Exception as e:
            # Send error event
            yield create_sse_message(
                {"error": str(e)},
                event="error",
            )

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post(
    "/models/download/{download_id}/pause",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Download paused successfully"},
        404: {"model": ProblemDetail, "description": "Download not found"},
        409: {"model": ProblemDetail, "description": "Download cannot be paused"},
    },
)
async def pause_download(download_id: str) -> dict:
    """Pause an active download.
    
    Args:
        download_id: Unique download identifier
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If download cannot be paused
    """
    success = await download_manager.pause_download(download_id)
    
    if not success:
        task = await download_manager.get_task(download_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Download {download_id} not found",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Download cannot be paused (current state: {task.state.value})",
        )

    return {"status": "success", "message": "Download paused"}


@router.post(
    "/models/download/{download_id}/resume",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Download resumed successfully"},
        404: {"model": ProblemDetail, "description": "Download not found"},
        409: {"model": ProblemDetail, "description": "Download cannot be resumed"},
    },
)
async def resume_download(download_id: str) -> dict:
    """Resume a paused download.
    
    Args:
        download_id: Unique download identifier
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If download cannot be resumed
    """
    success = await download_manager.resume_download(download_id)
    
    if not success:
        task = await download_manager.get_task(download_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Download {download_id} not found",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Download cannot be resumed (current state: {task.state.value})",
        )

    return {"status": "success", "message": "Download resumed"}


@router.delete(
    "/models/download/{download_id}",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Download cancelled successfully"},
        404: {"model": ProblemDetail, "description": "Download not found"},
    },
)
async def cancel_download(download_id: str) -> dict:
    """Cancel an active download and cleanup files.
    
    Args:
        download_id: Unique download identifier
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If download not found
    """
    success = await download_manager.cancel_download(download_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Download {download_id} not found or already completed",
        )

    return {"status": "success", "message": "Download cancelled"}


# ============================================================================
# Model Management Endpoints
# ============================================================================


@router.get(
    "/models/list",
    response_model=list[ModelInfo],
    responses={
        200: {"description": "List of downloaded models"},
        500: {"model": ProblemDetail, "description": "Internal server error"},
    },
)
async def list_models() -> list[ModelInfo]:
    """List all downloaded GGUF models.
    
    Returns:
        List of ModelInfo for each downloaded model
    """
    settings = get_settings()
    models_dir = Path(settings.models_dir)
    
    if not models_dir.exists():
        return []

    models = []
    
    try:
        # Find all .gguf files
        for gguf_file in models_dir.glob("*.gguf"):
            if gguf_file.is_file():
                stat = gguf_file.stat()
                models.append(
                    ModelInfo(
                        filename=gguf_file.name,
                        size_bytes=stat.st_size,
                        path=str(gguf_file.absolute()),
                        downloaded_at=datetime.fromtimestamp(stat.st_mtime),
                    )
                )
        
        return models
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list models: {str(e)}",
        )
