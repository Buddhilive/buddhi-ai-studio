from __future__ import annotations

import asyncio
import logging
import threading
import time
from enum import Enum
from typing import Any

import numpy as np
import sentencepiece as spm
from ai_edge_litert.interpreter import Interpreter

from app.core import model_metadata_store
from app.core.config import settings
from app.core.model_catalog import (
    EMBEDDING_MODEL_CATALOG_ID,
    EMBEDDING_TOKENIZER_CATALOG_ID,
    get_catalog_entry,
)
from app.schemas.download import DownloadStatus
from app.services.model_download_service import model_download_manager

logger = logging.getLogger(__name__)

_QUERY_PREFIX = "task: search result | query: "


class EmbeddingModelNotAvailableError(RuntimeError):
    """Raised when the embedding model cannot be loaded (e.g. not downloaded, no network)."""


class EmbeddingInferenceError(RuntimeError):
    """Raised when the LiteRT embedding model fails to encode input."""


class DownloadCanceledError(Exception):
    """Raised internally when an in-flight download is canceled."""


class EmbeddingStatus(str, Enum):
    NOT_DOWNLOADED = "not_downloaded"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    READY = "ready"
    ERROR = "error"


class EmbeddingEngineManager:
    """Lazily loads and caches a single LiteRT EmbeddingGemma interpreter.

    Independent of `InferenceEngineManager` (chat/litert_lm): EmbeddingGemma has
    no `.litertlm` bundle, only raw `.tflite` exports, so it runs through
    `ai_edge_litert.interpreter.Interpreter` instead of the `litert_lm` engine.
    Both the model and its SentencePiece tokenizer are downloaded as two
    separate `ModelCatalogEntry` rows via the shared `model_download_manager`,
    so unlike the previous Sentence-Transformers implementation this reports
    real byte-level download progress and supports pause/resume/cancel.
    """

    def __init__(self) -> None:
        self._interpreter: Interpreter | None = None
        self._tokenizer: spm.SentencePieceProcessor | None = None
        self._input_index: int | None = None
        self._output_index: int | None = None
        self._input_dtype: np.dtype | None = None
        self._load_lock = threading.Lock()
        self._invoke_lock = asyncio.Lock()
        self._status = EmbeddingStatus.NOT_DOWNLOADED
        self._error: str | None = None
        self._download_task: asyncio.Task | None = None
        self._cancel_requested: bool = False

    def get_status(self) -> tuple[EmbeddingStatus, str | None]:
        return self._status, self._error

    def get_progress(self) -> dict[str, Any]:
        if self._interpreter is not None:
            self._status = EmbeddingStatus.READY
        elif self._status not in (EmbeddingStatus.DOWNLOADING, EmbeddingStatus.PAUSED):
            avail_model = model_download_manager.check_availability(EMBEDDING_MODEL_CATALOG_ID)
            avail_tok = model_download_manager.check_availability(EMBEDDING_TOKENIZER_CATALOG_ID)
            if avail_model.available and avail_tok.available:
                self._status = EmbeddingStatus.READY

        entry_model = get_catalog_entry(EMBEDDING_MODEL_CATALOG_ID)
        entry_tok = get_catalog_entry(EMBEDDING_TOKENIZER_CATALOG_ID)

        state_model = model_download_manager.get_state(EMBEDDING_MODEL_CATALOG_ID)
        state_tok = model_download_manager.get_state(EMBEDDING_TOKENIZER_CATALOG_ID)

        total_bytes = (entry_model.size_bytes or 190_000_000) + (entry_tok.size_bytes or 4_800_000)

        if self._status == EmbeddingStatus.READY:
            downloaded_bytes = total_bytes
            percentage = 100.0
            current_phase = "ready"
        else:
            downloaded_bytes = state_model.downloaded_bytes + state_tok.downloaded_bytes
            percentage = min(100.0, round(100.0 * downloaded_bytes / total_bytes, 2)) if total_bytes else 0.0

            if self._status == EmbeddingStatus.DOWNLOADING:
                if state_model.status == DownloadStatus.DOWNLOADING:
                    current_phase = "model"
                elif state_tok.status == DownloadStatus.DOWNLOADING:
                    current_phase = "tokenizer"
                elif state_model.status == DownloadStatus.COMPLETED and state_tok.status == DownloadStatus.COMPLETED:
                    current_phase = "loading"
                else:
                    current_phase = "model"
            elif self._status == EmbeddingStatus.PAUSED:
                if state_model.status == DownloadStatus.PAUSED:
                    current_phase = "model"
                else:
                    current_phase = "tokenizer"
            else:
                current_phase = None

        return {
            "status": self._status,
            "error": self._error,
            "downloaded_bytes": downloaded_bytes,
            "total_bytes": total_bytes,
            "percentage": percentage,
            "current_phase": current_phase,
            "files": {
                EMBEDDING_MODEL_CATALOG_ID: state_model,
                EMBEDDING_TOKENIZER_CATALOG_ID: state_tok,
            },
        }

    def pause(self) -> None:
        if self._status != EmbeddingStatus.DOWNLOADING:
            return
        self._status = EmbeddingStatus.PAUSED
        try:
            model_download_manager.pause()
        except RuntimeError:
            pass

    def resume(self) -> None:
        if self._status != EmbeddingStatus.PAUSED:
            return
        self._status = EmbeddingStatus.DOWNLOADING
        try:
            model_download_manager.resume()
        except RuntimeError:
            pass

    def cancel(self) -> None:
        self._cancel_requested = True
        self._status = EmbeddingStatus.NOT_DOWNLOADED
        self._error = None
        try:
            model_download_manager.cancel()
        except RuntimeError:
            pass

    @staticmethod
    def _load_tokenizer(path: str) -> spm.SentencePieceProcessor:
        processor = spm.SentencePieceProcessor()
        if not processor.load(path):
            raise EmbeddingModelNotAvailableError(
                f"Failed to load SentencePiece tokenizer from {path}"
            )
        return processor

    @staticmethod
    def _load_interpreter(path: str) -> Interpreter:
        try:
            interpreter = Interpreter(model_path=path, num_threads=settings.embedding_num_threads)
            interpreter.allocate_tensors()
        except Exception as exc:
            raise EmbeddingModelNotAvailableError(
                f"Embedding model at {path} could not be loaded: {exc}"
            ) from exc
        return interpreter

    @staticmethod
    def _resolve_input_tensor(interpreter: Interpreter) -> tuple[int, np.dtype]:
        details = interpreter.get_input_details()
        logger.info(
            "Embedding model input tensors: %s",
            [{"name": d["name"], "shape": d["shape"].tolist(), "dtype": d["dtype"]} for d in details],
        )
        seq_len = settings.embedding_seq_length
        candidates = [
            d
            for d in details
            if d["dtype"] in (np.int32, np.int64)
            and len(d["shape"]) == 2
            and int(d["shape"][-1]) == seq_len
        ]
        if len(candidates) != 1:
            raise EmbeddingModelNotAvailableError(
                "Could not unambiguously identify the token-id input tensor for the "
                f"embedding model (expected exactly one int32/int64 tensor of shape "
                f"[*, {seq_len}]); candidates: {candidates!r}; all inputs: {details!r}"
            )
        chosen = candidates[0]
        return chosen["index"], chosen["dtype"]

    @staticmethod
    def _resolve_output_tensor(interpreter: Interpreter) -> int:
        details = interpreter.get_output_details()
        logger.info(
            "Embedding model output tensors: %s",
            [{"name": d["name"], "shape": d["shape"].tolist(), "dtype": d["dtype"]} for d in details],
        )
        expected_dim = settings.embedding_dim
        candidates = [d for d in details if expected_dim in tuple(int(s) for s in d["shape"])]
        if len(candidates) != 1:
            raise EmbeddingModelNotAvailableError(
                "Could not unambiguously identify the embedding output tensor (expected "
                f"a dimension equal to embedding_dim={expected_dim}); candidates: "
                f"{candidates!r}; all outputs: {details!r}"
            )
        return candidates[0]["index"]

    def _load_model(self) -> Interpreter:
        if self._interpreter is not None:
            return self._interpreter
        with self._load_lock:
            if self._interpreter is not None:
                return self._interpreter

            model_avail = model_download_manager.check_availability(EMBEDDING_MODEL_CATALOG_ID)
            tok_avail = model_download_manager.check_availability(EMBEDDING_TOKENIZER_CATALOG_ID)
            if not (model_avail.available and tok_avail.available):
                missing = [
                    name
                    for name, avail in (
                        ("model (.tflite)", model_avail),
                        ("tokenizer (sentencepiece.model)", tok_avail),
                    )
                    if not avail.available
                ]
                self._status = EmbeddingStatus.NOT_DOWNLOADED
                self._error = None
                raise EmbeddingModelNotAvailableError(
                    f"Embedding model files not downloaded yet: {', '.join(missing)}. "
                    "Start a download via POST /api/embedding-model/download."
                )

            self._status = EmbeddingStatus.DOWNLOADING
            self._error = None
            try:
                tokenizer = self._load_tokenizer(tok_avail.path)
                interpreter = self._load_interpreter(model_avail.path)
                input_index, input_dtype = self._resolve_input_tensor(interpreter)
                output_index = self._resolve_output_tensor(interpreter)
            except Exception as exc:
                self._status = EmbeddingStatus.ERROR
                self._error = str(exc)
                if isinstance(exc, EmbeddingModelNotAvailableError):
                    raise
                raise EmbeddingModelNotAvailableError(
                    f"Embedding model could not be loaded: {exc}"
                ) from exc

            self._tokenizer = tokenizer
            self._interpreter = interpreter
            self._input_index = input_index
            self._input_dtype = input_dtype
            self._output_index = output_index
            self._status = EmbeddingStatus.READY
            model_metadata_store.record_created(settings.embedding_model_id, int(time.time()))
            return self._interpreter

    def warm_up(self) -> None:
        try:
            self._load_model()
        except EmbeddingModelNotAvailableError as exc:
            logger.warning("Embedding engine warm-up failed: %s", exc)

    def trigger_download(self) -> EmbeddingStatus:
        """Kicks off background downloads (if needed) followed by a load.

        Returns the status immediately (does not wait for the load to finish)
        so the calling HTTP request doesn't block on a multi-GB download.
        """
        if self._status in (EmbeddingStatus.DOWNLOADING, EmbeddingStatus.READY):
            return self._status
        self._cancel_requested = False
        self._status = EmbeddingStatus.DOWNLOADING
        self._error = None
        self._download_task = asyncio.create_task(
            asyncio.to_thread(self._background_download_then_load)
        )
        return self._status

    def _poll_until_done(self, catalog_id: str, timeout_s: float = 3600.0, interval_s: float = 0.5) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self._cancel_requested:
                raise DownloadCanceledError("Download canceled")
            state = model_download_manager.get_state(catalog_id)
            if state.status == DownloadStatus.COMPLETED:
                return
            if state.status == DownloadStatus.FAILED:
                raise EmbeddingModelNotAvailableError(
                    f"Download failed for {catalog_id}: {state.error}"
                )
            if state.status == DownloadStatus.PAUSED:
                # Keep deadline fresh while paused so it doesn't time out
                deadline = time.monotonic() + timeout_s
            time.sleep(interval_s)
        raise EmbeddingModelNotAvailableError(f"Download timed out for {catalog_id}")

    def _background_download_then_load(self) -> None:
        try:
            for catalog_id in (EMBEDDING_MODEL_CATALOG_ID, EMBEDDING_TOKENIZER_CATALOG_ID):
                if self._cancel_requested:
                    self._status = EmbeddingStatus.NOT_DOWNLOADED
                    return
                availability = model_download_manager.check_availability(catalog_id)
                if availability.available:
                    continue
                model_download_manager.start(catalog_id)
                self._poll_until_done(catalog_id)
            if self._cancel_requested:
                self._status = EmbeddingStatus.NOT_DOWNLOADED
                return
            self._load_model()
        except DownloadCanceledError:
            self._status = EmbeddingStatus.NOT_DOWNLOADED
            self._error = None
            logger.info("Embedding engine download canceled")
        except EmbeddingModelNotAvailableError as exc:
            if not self._cancel_requested:
                self._status = EmbeddingStatus.ERROR
                self._error = str(exc)
                logger.warning("Embedding engine download/load failed: %s", exc)
        except Exception as exc:  # pragma: no cover - unexpected failure
            if not self._cancel_requested:
                self._status = EmbeddingStatus.ERROR
                self._error = str(exc)
                logger.exception("Embedding engine background download failed")

    def _tokenize_one(self, text: str) -> tuple[np.ndarray, int]:
        seq_len = settings.embedding_seq_length
        ids = self._tokenizer.encode(_QUERY_PREFIX + text, out_type=int)
        used = len(ids)
        if used > seq_len:
            logger.warning(
                "Embedding input truncated from %d to %d tokens (embedding_seq_length=%d)",
                used, seq_len, seq_len,
            )
            ids = ids[:seq_len]
            used = seq_len
        pad_id = self._tokenizer.pad_id()
        if pad_id < 0:
            pad_id = 0
        ids = ids + [pad_id] * (seq_len - len(ids))
        array = np.asarray([ids], dtype=self._input_dtype)
        return array, used

    def _invoke_one(self, ids: np.ndarray) -> np.ndarray:
        interpreter = self._interpreter
        interpreter.set_tensor(self._input_index, ids)
        interpreter.invoke()
        output = interpreter.get_tensor(self._output_index)
        return np.asarray(output, dtype=np.float32).reshape(-1)

    @staticmethod
    def _normalize(vector: np.ndarray) -> np.ndarray:
        norm = float(np.linalg.norm(vector))
        if norm == 0.0 or not np.isfinite(norm):
            return vector
        return vector / norm

    def _postprocess(self, raw: np.ndarray, dimensions: int | None) -> list[float]:
        vector = self._normalize(raw)
        if dimensions is not None:
            if dimensions > vector.shape[0]:
                raise EmbeddingInferenceError(
                    f"Requested dimensions={dimensions} exceeds model output dimension "
                    f"{vector.shape[0]} (embedding_dim={settings.embedding_dim})."
                )
            vector = self._normalize(vector[:dimensions])
        return vector.tolist()

    async def encode(
        self, texts: list[str], dimensions: int | None = None
    ) -> tuple[list[list[float]], int]:
        if not texts:
            raise EmbeddingInferenceError("texts must not be empty")

        self._load_model()

        def _run() -> tuple[list[list[float]], int]:
            vectors: list[list[float]] = []
            token_count = 0
            for text in texts:
                ids, used = self._tokenize_one(text)
                token_count += used
                raw = self._invoke_one(ids)
                vectors.append(self._postprocess(raw, dimensions))
            return vectors, token_count

        async with self._invoke_lock:
            try:
                return await asyncio.to_thread(_run)
            except (EmbeddingModelNotAvailableError, EmbeddingInferenceError):
                raise
            except Exception as exc:
                raise EmbeddingInferenceError(f"Embedding generation failed: {exc}") from exc


embedding_engine_manager = EmbeddingEngineManager()
