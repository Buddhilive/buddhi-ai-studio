from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from core.database.deps import get_db
from core.schemas.download import DownloadRequest, DownloadRecord, ProgressEvent
from core.models.download import ModelDownload
from core.services.download_service import start_download, get_download_context, cancel_download, delete_download_files
import logging

router = APIRouter(prefix="/models", tags=["models"])
logger = logging.getLogger(__name__)


@router.post("/download", status_code=status.HTTP_202_ACCEPTED, response_model=DownloadRecord)
async def request_model_download(
    request: DownloadRequest,
    db: Session = Depends(get_db),
) -> DownloadRecord:
    """
    Start a new model download from HuggingFace.

    Returns 202 Accepted if the download is queued successfully.
    Returns 409 Conflict if the same model+quantization is already downloading.
    Returns 400 Bad Request if the model ID is invalid or not found on HuggingFace.
    """
    download_record = await start_download(request.model_id, request.quantization, db)
    return DownloadRecord.from_orm(download_record)


@router.get("", response_model=list[DownloadRecord])
async def list_downloads(db: Session = Depends(get_db)) -> list[DownloadRecord]:
    """List all model downloads."""
    records = db.query(ModelDownload).all()
    return [DownloadRecord.from_orm(r) for r in records]


@router.get("/{download_id}", response_model=DownloadRecord)
async def get_download(
    download_id: int,
    db: Session = Depends(get_db),
) -> DownloadRecord:
    """Get a specific download record by ID."""
    record = db.query(ModelDownload).filter(ModelDownload.id == download_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Download not found")
    return DownloadRecord.from_orm(record)


@router.get("/{download_id}/progress")
async def stream_download_progress(download_id: int, db: Session = Depends(get_db)):
    """
    Stream download progress via Server-Sent Events (SSE).

    Only works when the download is in 'downloading' status.
    Returns 404 if the download record doesn't exist.
    Returns 409 if the download is not currently active.
    """
    record = db.query(ModelDownload).filter(ModelDownload.id == download_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Download not found")

    if record.status != "downloading":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Download is not active (status: {record.status})",
        )

    ctx = get_download_context(download_id)
    if not ctx:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Download context not found; download may have completed",
        )

    async def event_stream():
        """Generate SSE events for download progress."""
        try:
            while True:
                try:
                    event = await ctx.progress_queue.get()
                except Exception as e:
                    logger.error(f"Error getting progress event: {e}")
                    break

                yield f"data: {event.model_dump_json()}\n\n"

                if event.status in ("completed", "failed", "cancelled"):
                    break
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


@router.delete("/{download_id}", response_model=DownloadRecord)
async def cancel_or_delete_download(
    download_id: int,
    db: Session = Depends(get_db),
) -> DownloadRecord:
    """
    Cancel an active download or delete a completed record.

    - If status is 'downloading': cancel the download
    - If status is completed/failed/cancelled: delete the record
    - Local files are NOT deleted (use DELETE /models/{id}/files for that)
    """
    record = db.query(ModelDownload).filter(ModelDownload.id == download_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Download not found")

    if record.status == "downloading":
        cancel_download(download_id, db)
        db.refresh(record)
        return DownloadRecord.from_orm(record)
    else:
        # Delete the record but keep local files
        record_data = DownloadRecord.from_orm(record)
        db.delete(record)
        db.commit()
        return record_data


@router.delete("/{download_id}/files", response_model=DownloadRecord)
async def delete_model_files(
    download_id: int,
    db: Session = Depends(get_db),
) -> DownloadRecord:
    """
    Delete downloaded model files (keep the record).

    Returns 409 if the download is still in progress.
    """
    record = db.query(ModelDownload).filter(ModelDownload.id == download_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Download not found")

    if record.status == "downloading":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete files while download is in progress",
        )

    delete_download_files(record, db)
    return DownloadRecord.from_orm(record)
