from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_url
from huggingface_hub.utils import HfHubHTTPError, build_hf_headers, hf_raise_for_status, http_stream_backoff

from app.core import model_metadata_store, settings_store
from app.core.config import settings
from app.core.model_catalog import MODEL_CATALOG, ModelCatalogEntry, ModelCategory, get_catalog_entry
from app.schemas.download import DownloadStatus, ModelAvailability, ModelDownloadState

logger = logging.getLogger(__name__)

# Chunk size used when streaming the download.
_CHUNK_SIZE = 1024 * 1024


class DownloadPaused(Exception):
    """Raised internally to abort an in-flight download when paused."""


class ModelDownloadManager:
    """Owns at most one in-flight, resumable download at a time, across the whole
    model catalog.

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
        self._active_model_id: str | None = None
        self._states: dict[str, ModelDownloadState] = {
            entry.id: ModelDownloadState(
                model_id=entry.id, repo_id=entry.repo_id, filename=entry.filename
            )
            for entry in MODEL_CATALOG
        }

    def _base_dir(self, entry: ModelCatalogEntry) -> Path:
        return settings.embedding_cache_dir if entry.category == ModelCategory.EMBEDDING else settings.models_dir

    def _target_path(self, entry: ModelCatalogEntry) -> Path:
        return self._base_dir(entry) / entry.filename

    def _part_path(self, entry: ModelCatalogEntry) -> Path:
        return self._base_dir(entry) / f"{entry.filename}.part"

    def _on_chunk(self, model_id: str, size: int) -> None:
        with self._lock:
            state = self._states[model_id]
            if state.status != DownloadStatus.DOWNLOADING:
                return
            state.downloaded_bytes += size
            if state.total_bytes:
                state.percentage = round(100 * state.downloaded_bytes / state.total_bytes, 2)
            state.updated_at = datetime.now(timezone.utc)

    def get_state(self, model_id: str) -> ModelDownloadState:
        get_catalog_entry(model_id)
        with self._lock:
            return self._states[model_id].model_copy()

    def get_all_states(self) -> list[ModelDownloadState]:
        with self._lock:
            return [self._states[entry.id].model_copy() for entry in MODEL_CATALOG]

    def _set_state(self, model_id: str, **kwargs) -> None:
        with self._lock:
            state = self._states[model_id]
            for key, value in kwargs.items():
                setattr(state, key, value)
            state.updated_at = datetime.now(timezone.utc)

    def start(self, model_id: str) -> ModelDownloadState:
        entry = get_catalog_entry(model_id)
        with self._lock:
            state = self._states[model_id]
            if self._active_model_id is not None and self._active_model_id != model_id:
                raise RuntimeError("Another download is already in progress")
            if state.status == DownloadStatus.DOWNLOADING:
                raise RuntimeError("Download already in progress")
            if state.status == DownloadStatus.COMPLETED:
                return state.model_copy()
            self._pause_event.clear()
            self._active_model_id = model_id
            state.status = DownloadStatus.DOWNLOADING
            state.error = None

        self._thread = threading.Thread(target=self._run_download, args=(entry,), daemon=True)
        self._thread.start()
        return self.get_state(model_id)

    def pause(self) -> ModelDownloadState:
        with self._lock:
            model_id = self._active_model_id
            if model_id is None or self._states[model_id].status != DownloadStatus.DOWNLOADING:
                raise RuntimeError("No active download to pause")
        self._pause_event.set()
        if self._thread is not None:
            self._thread.join(timeout=30)
        return self.get_state(model_id)

    def resume(self) -> ModelDownloadState:
        with self._lock:
            model_id = self._active_model_id
            if model_id is None or self._states[model_id].status != DownloadStatus.PAUSED:
                raise RuntimeError("Download is not paused")
            self._pause_event.clear()
            self._states[model_id].status = DownloadStatus.DOWNLOADING
            self._states[model_id].error = None

        entry = get_catalog_entry(model_id)
        self._thread = threading.Thread(target=self._run_download, args=(entry,), daemon=True)
        self._thread.start()
        return self.get_state(model_id)

    def cancel(self) -> ModelDownloadState:
        with self._lock:
            model_id = self._active_model_id
            if model_id is None or self._states[model_id].status in (
                DownloadStatus.IDLE,
                DownloadStatus.COMPLETED,
            ):
                raise RuntimeError("No download to cancel")
        self._pause_event.set()
        if self._thread is not None:
            self._thread.join(timeout=30)

        entry = get_catalog_entry(model_id)
        self._remove_partial_files(entry)
        self._set_state(
            model_id,
            status=DownloadStatus.IDLE,
            downloaded_bytes=0,
            percentage=0.0,
            error=None,
        )
        with self._lock:
            self._active_model_id = None
        return self.get_state(model_id)

    def _remove_partial_files(self, entry: ModelCatalogEntry) -> None:
        part = self._part_path(entry)
        if part.exists():
            part.unlink()
        target = self._target_path(entry)
        if target.exists():
            target.unlink()
        model_metadata_store.delete_created(entry.id)

    def _fetch_total_bytes(self, entry: ModelCatalogEntry) -> int | None:
        try:
            api = HfApi(token=settings_store.get_hf_token())
            info = api.model_info(entry.repo_id, files_metadata=True)
            for sibling in info.siblings or []:
                if sibling.rfilename == entry.filename:
                    return sibling.size
        except Exception:
            logger.warning("Could not fetch model size metadata", exc_info=True)
        return None

    def _run_download(self, entry: ModelCatalogEntry) -> None:
        model_id = entry.id
        target = self._target_path(entry)
        part = self._part_path(entry)
        try:
            self._base_dir(entry).mkdir(parents=True, exist_ok=True)
            if self._states[model_id].total_bytes is None:
                self._set_state(model_id, total_bytes=self._fetch_total_bytes(entry))
            url = hf_hub_url(entry.repo_id, entry.filename)
            headers = build_hf_headers(token=settings_store.get_hf_token())

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
                self._set_state(model_id, downloaded_bytes=resume_offset)
                with part.open(mode) as f:
                    for chunk in response.iter_bytes(chunk_size=_CHUNK_SIZE):
                        if self._pause_event.is_set():
                            raise DownloadPaused()
                        if chunk:
                            f.write(chunk)
                            self._on_chunk(model_id, len(chunk))

            os.replace(part, target)
            model_metadata_store.record_created(model_id, int(target.stat().st_mtime))
        except DownloadPaused:
            self._set_state(model_id, status=DownloadStatus.PAUSED)
            return
        except (HfHubHTTPError, OSError) as exc:
            self._set_state(model_id, status=DownloadStatus.FAILED, error=str(exc))
            with self._lock:
                self._active_model_id = None
            return
        except Exception as exc:  # pragma: no cover - unexpected failure
            self._set_state(model_id, status=DownloadStatus.FAILED, error=str(exc))
            with self._lock:
                self._active_model_id = None
            return

        self._set_state(
            model_id,
            status=DownloadStatus.COMPLETED,
            downloaded_bytes=target.stat().st_size,
            total_bytes=target.stat().st_size,
            percentage=100.0,
        )
        with self._lock:
            self._active_model_id = None

    def check_availability(self, model_id: str) -> ModelAvailability:
        entry = get_catalog_entry(model_id)
        target = self._target_path(entry)
        if target.exists():
            return ModelAvailability(
                model_id=model_id,
                available=True,
                path=str(target),
                size_bytes=target.stat().st_size,
            )
        return ModelAvailability(model_id=model_id, available=False)

    def scan_on_startup(self) -> None:
        settings.models_dir.mkdir(parents=True, exist_ok=True)
        settings.embedding_cache_dir.mkdir(parents=True, exist_ok=True)
        for entry in MODEL_CATALOG:
            target = self._target_path(entry)
            if target.exists():
                size = target.stat().st_size
                self._set_state(
                    entry.id,
                    status=DownloadStatus.COMPLETED,
                    downloaded_bytes=size,
                    total_bytes=size,
                    percentage=100.0,
                )
                model_metadata_store.record_created(entry.id, int(target.stat().st_mtime))
                continue

            part = self._part_path(entry)
            if part.exists():
                self._set_state(
                    entry.id, status=DownloadStatus.PAUSED, downloaded_bytes=part.stat().st_size
                )


model_download_manager = ModelDownloadManager()
