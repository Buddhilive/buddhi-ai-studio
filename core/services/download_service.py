import asyncio
import logging
import os
import shutil
import threading
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from huggingface_hub import hf_hub_download, list_repo_files
from huggingface_hub.errors import (
    RepositoryNotFoundError,
    GatedRepoError,
    HfHubHTTPError,
)
from sqlalchemy.orm import Session

from core.models.download import ModelDownload
from core.schemas.download import ProgressEvent

logger = logging.getLogger(__name__)

# Global thread pool for downloads
_download_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="hf-download-")

# Track active downloads: download_id -> DownloadContext
_active_downloads: dict[int, "DownloadContext"] = {}


class DownloadCancelledError(Exception):
    """Raised when a download is cancelled."""

    pass


@dataclass
class DownloadContext:
    """Context for an active download."""

    progress_queue: asyncio.Queue
    cancel_event: threading.Event
    loop: asyncio.AbstractEventLoop


def get_download_context(download_id: int) -> Optional[DownloadContext]:
    """Get the context for an active download."""
    return _active_downloads.get(download_id)


def cancel_download(download_id: int, db: Session) -> None:
    """Cancel an active download."""
    ctx = _active_downloads.get(download_id)
    if ctx:
        ctx.cancel_event.set()
        # Mark as cancelled in DB (will be updated by the download thread)
        try:
            db.query(ModelDownload).filter(ModelDownload.id == download_id).update(
                {"status": "cancelled"},
                synchronize_session=False,
            )
            db.commit()
        except Exception as e:
            logger.error(f"Failed to cancel download: {e}")
            db.rollback()


def delete_download_files(record: ModelDownload, db: Session) -> None:
    """Delete local files for a download."""
    if record.local_path:
        path = Path(record.local_path)
        if path.exists():
            try:
                shutil.rmtree(path)
                logger.info(f"Deleted download directory: {path}")
            except Exception as e:
                logger.error(f"Failed to delete {path}: {e}")
                record.error_msg = f"Failed to delete files: {str(e)}"
                db.commit()
                return

    record.local_path = None
    db.commit()


async def start_download(model_id: str, quantization: Optional[str], db: Session) -> ModelDownload:
    """
    Start a new model download.

    Validates that:
    - model_id is not empty
    - no other download is currently active for the same model+quantization
    """
    # Validate input
    if not model_id or not model_id.strip():
        raise ValueError("model_id cannot be empty")

    model_id = model_id.strip()

    # Check for duplicate active download
    existing = (
        db.query(ModelDownload)
        .filter(
            ModelDownload.model_id == model_id,
            ModelDownload.quantization == quantization,
            ModelDownload.status == "downloading",
        )
        .first()
    )
    if existing:
        raise ValueError(f"Download already in progress for {model_id} (quantization: {quantization})")

    # Create download record
    download_record = ModelDownload(
        model_id=model_id,
        quantization=quantization,
        status="pending",
        progress=0.0,
    )
    db.add(download_record)
    db.commit()
    db.refresh(download_record)

    # Setup download context
    loop = asyncio.get_event_loop()
    ctx = DownloadContext(
        progress_queue=asyncio.Queue(),
        cancel_event=threading.Event(),
        loop=loop,
    )
    _active_downloads[download_record.id] = ctx

    # Start download in background thread
    def run_download():
        _run_download_thread(
            download_record.id,
            model_id,
            quantization,
            ctx,
        )

    _download_executor.submit(run_download)

    return download_record


def _update_download_status(download_id: int, status: str, **kwargs) -> bool:
    """Safely update download status in DB."""
    from core.database.engine import SessionLocal

    db = SessionLocal()
    try:
        logger.debug(f"Updating download {download_id} to status={status}, kwargs={kwargs}")
        db.query(ModelDownload).filter(ModelDownload.id == download_id).update(
            {"status": status, **kwargs},
            synchronize_session=False,
        )
        db.commit()
        logger.debug(f"Successfully updated download {download_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to update download {download_id} status to {status}: {e}", exc_info=True)
        try:
            db.rollback()
        except:
            pass
        return False
    finally:
        try:
            db.close()
        except:
            pass


def _push_event(ctx: DownloadContext, event: ProgressEvent) -> None:
    """Push an event to the SSE queue from a thread."""
    try:
        ctx.loop.call_soon_threadsafe(ctx.progress_queue.put_nowait, event)
    except Exception:
        pass


def _run_download_thread(
    download_id: int,
    model_id: str,
    _: Optional[str],
    ctx: DownloadContext,
) -> None:
    """Run the actual download in a thread."""
    logger.info(f"Download thread started for {download_id}: {model_id}")
    try:
        # Get settings from environment
        hf_models_dir = os.getenv("HF_MODELS_DIR", "./data/models")
        hf_token = os.getenv("HF_TOKEN") or None
        logger.info(f"Environment: models_dir={hf_models_dir}, has_token={bool(hf_token)}")

        # Prepare local directory
        local_dir = Path(hf_models_dir) / model_id.replace("/", "_")
        local_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Local directory prepared: {local_dir}")

        # Update status to downloading
        logger.info(f"Calling _update_download_status for {download_id}")
        if not _update_download_status(download_id, "downloading"):
            logger.warning(f"Failed to update status for {download_id}")
            return
        logger.info(f"Successfully updated {download_id} to downloading")

        # Get list of files
        try:
            logger.info(f"Fetching file list for {model_id}")
            files = list_repo_files(
                repo_id=model_id,
                token=hf_token,
                repo_type="model",
            )
            logger.info(f"Found {len(files)} files for {model_id}")
        except RepositoryNotFoundError:
            error = f"Model '{model_id}' not found on HuggingFace"
            logger.error(error)
            _update_download_status(download_id, "failed", error_msg=error)
            _push_event(ctx, ProgressEvent(
                download_id=download_id,
                status="failed",
                progress=0.0,
                message=error,
            ))
            return
        except GatedRepoError:
            error = f"Model '{model_id}' is gated. Please provide HF_TOKEN with access."
            logger.error(error)
            _update_download_status(download_id, "failed", error_msg=error)
            _push_event(ctx, ProgressEvent(
                download_id=download_id,
                status="failed",
                progress=0.0,
                message=error,
            ))
            return
        except HfHubHTTPError as e:
            error = f"HuggingFace API error: {str(e)}"
            logger.error(error)
            _update_download_status(download_id, "failed", error_msg=error)
            _push_event(ctx, ProgressEvent(
                download_id=download_id,
                status="failed",
                progress=0.0,
                message=error,
            ))
            return
        except Exception as e:
            error = f"Failed to fetch file list: {str(e)}"
            logger.error(error, exc_info=True)
            _update_download_status(download_id, "failed", error_msg=error)
            _push_event(ctx, ProgressEvent(
                download_id=download_id,
                status="failed",
                progress=0.0,
                message=error,
            ))
            return

        # Download files one by one
        total_files = len(files)
        for i, filename in enumerate(files):
            if ctx.cancel_event.is_set():
                error = "Download cancelled by user"
                logger.info(f"Download {download_id} cancelled")
                progress = ((i + 1) / total_files * 100) if total_files > 0 else 0.0
                _update_download_status(
                    download_id,
                    "cancelled",
                    error_msg=error,
                )
                _push_event(ctx, ProgressEvent(
                    download_id=download_id,
                    status="cancelled",
                    progress=progress,
                    message=error,
                ))
                # Cleanup
                if local_dir.exists():
                    try:
                        shutil.rmtree(local_dir)
                    except Exception as e:
                        logger.error(f"Failed to cleanup: {e}")
                return

            try:
                logger.debug(f"Downloading {filename} ({i+1}/{total_files})")
                hf_hub_download(
                    repo_id=model_id,
                    filename=filename,
                    local_dir=str(local_dir),
                    token=hf_token,
                    repo_type="model",
                )
            except Exception as e:
                error = f"Failed to download {filename}: {str(e)}"
                logger.error(error, exc_info=True)
                progress = ((i + 1) / total_files * 100) if total_files > 0 else 0.0
                _update_download_status(download_id, "failed", error_msg=error)
                _push_event(ctx, ProgressEvent(
                    download_id=download_id,
                    status="failed",
                    progress=progress,
                    message=error,
                ))
                return

            # Update progress
            progress = ((i + 1) / total_files) * 100
            _update_download_status(download_id, "downloading", progress=progress)

            # Send progress event (non-blocking)
            event = ProgressEvent(
                download_id=download_id,
                status="downloading",
                progress=progress,
                message=f"Downloaded {i + 1}/{total_files} files",
            )
            try:
                ctx.progress_queue.put_nowait(event)
            except:
                pass

        # Mark as completed
        _update_download_status(
            download_id,
            "completed",
            progress=100.0,
            local_path=str(local_dir),
        )
        logger.info(f"Download {download_id} completed: {model_id}")

        # Send completion event
        event = ProgressEvent(
            download_id=download_id,
            status="completed",
            progress=100.0,
            message="Download completed successfully",
        )
        try:
            ctx.progress_queue.put_nowait(event)
        except:
            pass

    except Exception as e:
        logger.error(f"Unexpected error in download thread: {e}", exc_info=True)
        error_msg = f"Unexpected error: {str(e)}"
        _update_download_status(download_id, "failed", error_msg=error_msg)
        _push_event(ctx, ProgressEvent(
            download_id=download_id,
            status="failed",
            progress=0.0,
            message=error_msg,
        ))
    finally:
        # Cleanup context
        _active_downloads.pop(download_id, None)
