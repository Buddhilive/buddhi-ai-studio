"""Download manager for HuggingFace models with pause/resume support."""

import asyncio
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import aiofiles
from huggingface_hub import hf_hub_download, hf_hub_url
from huggingface_hub.utils import HfHubHTTPError

from config import get_settings
from models import DownloadState, ProgressUpdate
from utils import cleanup_partial_download, get_available_space, validate_gguf_file


class DownloadTask:
    """Represents a single download task with state and progress tracking.
    
    Attributes:
        download_id: Unique identifier for this download
        repo_id: HuggingFace repository ID
        filename: Name of file to download
        repo_type: Type of repository (model/dataset)
        state: Current download state
        progress_percent: Download progress (0-100)
        downloaded_bytes: Bytes downloaded so far
        total_bytes: Total file size
        speed_mbps: Current download speed in MB/s
        eta_seconds: Estimated time remaining
        error_message: Error details if failed
        file_path: Local path where file is being saved
        token: Optional HuggingFace API token
    """

    def __init__(
        self,
        repo_id: str,
        filename: str,
        repo_type: str,
        file_path: Path,
        token: Optional[str] = None,
    ):
        """Initialize download task.
        
        Args:
            repo_id: HuggingFace repository ID
            filename: File to download
            repo_type: Repository type
            file_path: Local save path
            token: Optional API token
        """
        self.download_id = str(uuid.uuid4())
        self.repo_id = repo_id
        self.filename = filename
        self.repo_type = repo_type
        self.file_path = file_path
        self.token = token

        # State tracking
        self.state = DownloadState.PENDING
        self.progress_percent: float = 0.0
        self.downloaded_bytes: int = 0
        self.total_bytes: int = 0
        self.speed_mbps: Optional[float] = None
        self.eta_seconds: Optional[int] = None
        self.error_message: Optional[str] = None

        # Internal tracking
        self._start_time: Optional[float] = None
        self._last_update_time: Optional[float] = None
        self._cancel_requested = False

    def to_progress_update(self) -> ProgressUpdate:
        """Convert task to ProgressUpdate model.
        
        Returns:
            ProgressUpdate instance
        """
        return ProgressUpdate(
            download_id=self.download_id,
            state=self.state,
            progress_percent=self.progress_percent,
            downloaded_bytes=self.downloaded_bytes,
            total_bytes=self.total_bytes,
            speed_mbps=self.speed_mbps,
            eta_seconds=self.eta_seconds,
            error_message=self.error_message,
        )

    def update_progress(self, downloaded: int, total: int) -> None:
        """Update download progress and calculate speed/ETA.
        
        Args:
            downloaded: Bytes downloaded
            total: Total bytes
        """
        self.downloaded_bytes = downloaded
        self.total_bytes = total
        
        if total > 0:
            self.progress_percent = (downloaded / total) * 100
        
        # Calculate speed and ETA
        current_time = time.time()
        
        if self._start_time is None:
            self._start_time = current_time
            
        elapsed = current_time - self._start_time
        
        if elapsed > 0 and downloaded > 0:
            # Speed in MB/s
            self.speed_mbps = (downloaded / elapsed) / (1024 * 1024)
            
            # ETA in seconds
            if downloaded < total and self.speed_mbps > 0:
                remaining_bytes = total - downloaded
                remaining_mb = remaining_bytes / (1024 * 1024)
                self.eta_seconds = int(remaining_mb / self.speed_mbps)
            else:
                self.eta_seconds = 0


class DownloadManager:
    """Manages model downloads with pause, resume, and progress tracking.
    
    This is a singleton service that coordinates all download operations.
    """

    def __init__(self):
        """Initialize download manager."""
        self._tasks: Dict[str, DownloadTask] = {}
        self._active_downloads: set = set()
        self._lock = asyncio.Lock()

    async def start_download(
        self,
        repo_id: str,
        filename: str,
        repo_type: str = "model",
        token: Optional[str] = None,
    ) -> DownloadTask:
        """Start a new model download.
        
        Args:
            repo_id: HuggingFace repository ID
            filename: File to download
            repo_type: Repository type (model/dataset)
            token: Optional HuggingFace API token
            
        Returns:
            DownloadTask instance
            
        Raises:
            ValueError: If parameters are invalid
            OSError: If disk space is insufficient
        """
        settings = get_settings()
        
        # Check if models directory is set
        if not settings.models_dir:
            raise ValueError("Models directory not initialized")

        models_dir = Path(settings.models_dir)
        file_path = models_dir / filename

        # Check available disk space (need at least 100MB free)
        available_space = get_available_space(models_dir)
        if available_space < 100 * 1024 * 1024:
            raise OSError("Insufficient disk space")

        # Check concurrent download limit
        if len(self._active_downloads) >= settings.max_concurrent_downloads:
            raise ValueError(
                f"Maximum concurrent downloads ({settings.max_concurrent_downloads}) reached"
            )

        # Create download task
        task = DownloadTask(repo_id, filename, repo_type, file_path, token)
        
        async with self._lock:
            self._tasks[task.download_id] = task
            self._active_downloads.add(task.download_id)

        # Start download in background
        asyncio.create_task(self._download_file(task))

        return task

    async def _download_file(self, task: DownloadTask) -> None:
        """Execute the download operation.
        
        Args:
            task: DownloadTask to execute
        """
        try:
            task.state = DownloadState.DOWNLOADING
            settings = get_settings()

            # Use HuggingFace Hub's download function with resume support
            downloaded_path = hf_hub_download(
                repo_id=task.repo_id,
                filename=task.filename,
                repo_type=task.repo_type,
                token=task.token or settings.hf_token,
                cache_dir=str(Path(settings.models_dir) / ".cache"),
                local_dir=settings.models_dir,
                local_dir_use_symlinks=False,
                resume_download=True,
            )

            # Move to final location if needed
            downloaded_path_obj = Path(downloaded_path)
            if downloaded_path_obj != task.file_path:
                downloaded_path_obj.rename(task.file_path)

            # Validate GGUF file
            if not validate_gguf_file(task.file_path):
                raise ValueError("Downloaded file is not a valid GGUF model")

            # Update task state
            task.state = DownloadState.COMPLETED
            task.progress_percent = 100.0
            task.downloaded_bytes = task.file_path.stat().st_size
            task.total_bytes = task.downloaded_bytes

        except HfHubHTTPError as e:
            task.state = DownloadState.FAILED
            task.error_message = f"HuggingFace API error: {str(e)}"
        except ValueError as e:
            task.state = DownloadState.FAILED
            task.error_message = str(e)
            # Clean up invalid file
            cleanup_partial_download(task.file_path)
            if task.file_path.exists():
                task.file_path.unlink()
        except Exception as e:
            task.state = DownloadState.FAILED
            task.error_message = f"Download failed: {str(e)}"
        finally:
            # Remove from active downloads
            async with self._lock:
                self._active_downloads.discard(task.download_id)

    async def pause_download(self, download_id: str) -> bool:
        """Pause an active download.
        
        Args:
            download_id: ID of download to pause
            
        Returns:
            True if paused successfully
        """
        async with self._lock:
            task = self._tasks.get(download_id)
            if task and task.state == DownloadState.DOWNLOADING:
                task.state = DownloadState.PAUSED
                task._cancel_requested = True
                return True
        return False

    async def resume_download(self, download_id: str) -> bool:
        """Resume a paused download.
        
        Args:
            download_id: ID of download to resume
            
        Returns:
            True if resumed successfully
        """
        async with self._lock:
            task = self._tasks.get(download_id)
            if task and task.state == DownloadState.PAUSED:
                task.state = DownloadState.DOWNLOADING
                task._cancel_requested = False
                # Restart download
                asyncio.create_task(self._download_file(task))
                return True
        return False

    async def cancel_download(self, download_id: str) -> bool:
        """Cancel a download and cleanup files.
        
        Args:
            download_id: ID of download to cancel
            
        Returns:
            True if cancelled successfully
        """
        async with self._lock:
            task = self._tasks.get(download_id)
            if task and task.state in [
                DownloadState.PENDING,
                DownloadState.DOWNLOADING,
                DownloadState.PAUSED,
            ]:
                task.state = DownloadState.CANCELLED
                task._cancel_requested = True
                
                # Cleanup partial download
                cleanup_partial_download(task.file_path)
                
                # Remove from active downloads
                self._active_downloads.discard(download_id)
                return True
        return False

    async def get_task(self, download_id: str) -> Optional[DownloadTask]:
        """Get download task by ID.
        
        Args:
            download_id: Download identifier
            
        Returns:
            DownloadTask if found, None otherwise
        """
        async with self._lock:
            return self._tasks.get(download_id)

    async def list_downloads(self) -> list[DownloadTask]:
        """Get list of all download tasks.
        
        Returns:
            List of DownloadTask instances
        """
        async with self._lock:
            return list(self._tasks.values())

    async def cleanup_old_tasks(self, max_age_hours: int = 24) -> int:
        """Remove old completed/failed tasks.
        
        Args:
            max_age_hours: Maximum age in hours
            
        Returns:
            Number of tasks removed
        """
        cutoff_time = time.time() - (max_age_hours * 3600)
        removed = 0
        
        async with self._lock:
            to_remove = []
            for task_id, task in self._tasks.items():
                if task.state in [DownloadState.COMPLETED, DownloadState.FAILED]:
                    if task._start_time and task._start_time < cutoff_time:
                        to_remove.append(task_id)
            
            for task_id in to_remove:
                del self._tasks[task_id]
                removed += 1
                
        return removed


# Global download manager instance
download_manager = DownloadManager()
