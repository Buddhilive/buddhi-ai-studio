from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_url
from huggingface_hub.utils import HfHubHTTPError, build_hf_headers, hf_raise_for_status, http_stream_backoff

from app.core.config import settings
from app.schemas.download import DownloadStatus, ModelAvailability, ModelDownloadState

logger = logging.getLogger(__name__)

# Chunk size used when streaming the download.
_CHUNK_SIZE = 1024 * 1024


class DownloadPaused(Exception):
    """Raised internally to abort an in-flight download when paused."""


class ModelDownloadManager:
    """Owns the single in-flight, resumable download of the configured HF model file.

    huggingface_hub's own `hf_hub_download` (as of v1) writes each attempt to a
    process-unique temp file and deletes it on any exception, so it cannot resume
    across separate calls. We therefore stream the file ourselves via a stable
    `<filename>.part` file and HTTP Range requests, using huggingface_hub only to
    resolve the download URL, auth headers, and retry/redirect handling.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pause_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._state = ModelDownloadState(
            repo_id=settings.hf_model_repo_id,
            filename=settings.hf_model_filename,
        )

    @property
    def pause_event(self) -> threading.Event:
        return self._pause_event

    def _target_path(self) -> Path:
        return settings.models_dir / settings.hf_model_filename

    def _part_path(self) -> Path:
        return settings.models_dir / f"{settings.hf_model_filename}.part"

    def _on_chunk(self, size: int) -> None:
        with self._lock:
            if self._state.status != DownloadStatus.DOWNLOADING:
                return
            self._state.downloaded_bytes += size
            if self._state.total_bytes:
                self._state.percentage = round(
                    100 * self._state.downloaded_bytes / self._state.total_bytes, 2
                )
            self._state.updated_at = datetime.now(timezone.utc)

    def get_state(self) -> ModelDownloadState:
        with self._lock:
            return self._state.model_copy()

    def _set_state(self, **kwargs) -> None:
        with self._lock:
            for key, value in kwargs.items():
                setattr(self._state, key, value)
            self._state.updated_at = datetime.now(timezone.utc)

    def start(self) -> ModelDownloadState:
        with self._lock:
            if self._state.status == DownloadStatus.DOWNLOADING:
                raise RuntimeError("Download already in progress")
            if self._state.status == DownloadStatus.COMPLETED:
                return self._state.model_copy()
            self._pause_event.clear()
            self._state.status = DownloadStatus.DOWNLOADING
            self._state.error = None

        self._thread = threading.Thread(target=self._run_download, daemon=True)
        self._thread.start()
        return self.get_state()

    def pause(self) -> ModelDownloadState:
        with self._lock:
            if self._state.status != DownloadStatus.DOWNLOADING:
                raise RuntimeError("No active download to pause")
        self._pause_event.set()
        if self._thread is not None:
            self._thread.join(timeout=30)
        return self.get_state()

    def resume(self) -> ModelDownloadState:
        with self._lock:
            if self._state.status != DownloadStatus.PAUSED:
                raise RuntimeError("Download is not paused")
            self._pause_event.clear()
            self._state.status = DownloadStatus.DOWNLOADING
            self._state.error = None

        self._thread = threading.Thread(target=self._run_download, daemon=True)
        self._thread.start()
        return self.get_state()

    def cancel(self) -> ModelDownloadState:
        with self._lock:
            if self._state.status in (DownloadStatus.IDLE, DownloadStatus.COMPLETED):
                raise RuntimeError("No download to cancel")
        self._pause_event.set()
        if self._thread is not None:
            self._thread.join(timeout=30)

        self._remove_partial_files()
        self._set_state(
            status=DownloadStatus.IDLE,
            downloaded_bytes=0,
            percentage=0.0,
            error=None,
        )
        return self.get_state()

    def _remove_partial_files(self) -> None:
        part = self._part_path()
        if part.exists():
            part.unlink()
        target = self._target_path()
        if target.exists():
            target.unlink()

    def _fetch_total_bytes(self) -> int | None:
        try:
            api = HfApi(token=settings.hf_token)
            info = api.model_info(settings.hf_model_repo_id, files_metadata=True)
            for sibling in info.siblings or []:
                if sibling.rfilename == settings.hf_model_filename:
                    return sibling.size
        except Exception:
            logger.warning("Could not fetch model size metadata", exc_info=True)
        return None

    def _run_download(self) -> None:
        target = self._target_path()
        part = self._part_path()
        try:
            settings.models_dir.mkdir(parents=True, exist_ok=True)
            if self._state.total_bytes is None:
                self._set_state(total_bytes=self._fetch_total_bytes())
            url = hf_hub_url(settings.hf_model_repo_id, settings.hf_model_filename)
            headers = build_hf_headers(token=settings.hf_token)

            resume_offset = part.stat().st_size if part.exists() else 0
            if resume_offset:
                headers["Range"] = f"bytes={resume_offset}-"

            with http_stream_backoff("GET", url, headers=headers) as response:
                hf_raise_for_status(response)

                # Server may ignore the Range header (e.g. no Range support) and return
                # the full file with 200 instead of 206 Partial Content. In that case we
                # cannot append, so start over from scratch.
                if resume_offset and response.status_code != 206:
                    resume_offset = 0

                mode = "ab" if resume_offset else "wb"
                self._set_state(downloaded_bytes=resume_offset)
                with part.open(mode) as f:
                    for chunk in response.iter_bytes(chunk_size=_CHUNK_SIZE):
                        if self._pause_event.is_set():
                            raise DownloadPaused()
                        if chunk:
                            f.write(chunk)
                            self._on_chunk(len(chunk))

            os.replace(part, target)
        except DownloadPaused:
            self._set_state(status=DownloadStatus.PAUSED)
            return
        except (HfHubHTTPError, OSError) as exc:
            self._set_state(status=DownloadStatus.FAILED, error=str(exc))
            return
        except Exception as exc:  # pragma: no cover - unexpected failure
            self._set_state(status=DownloadStatus.FAILED, error=str(exc))
            return

        self._set_state(
            status=DownloadStatus.COMPLETED,
            downloaded_bytes=target.stat().st_size,
            total_bytes=target.stat().st_size,
            percentage=100.0,
        )

    def check_availability(self) -> ModelAvailability:
        target = self._target_path()
        if target.exists():
            return ModelAvailability(
                available=True, path=str(target), size_bytes=target.stat().st_size
            )
        return ModelAvailability(available=False)

    def scan_on_startup(self) -> None:
        settings.models_dir.mkdir(parents=True, exist_ok=True)
        target = self._target_path()
        if target.exists():
            size = target.stat().st_size
            self._set_state(
                status=DownloadStatus.COMPLETED,
                downloaded_bytes=size,
                total_bytes=size,
                percentage=100.0,
            )
            return

        part = self._part_path()
        if part.exists():
            self._set_state(status=DownloadStatus.PAUSED, downloaded_bytes=part.stat().st_size)


model_download_manager = ModelDownloadManager()
