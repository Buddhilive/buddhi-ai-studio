"""LRU model cache for loaded GGUF models with per-model locking."""

import asyncio
from contextlib import asynccontextmanager
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from llama_cpp import Llama

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Entry in the model cache."""
    llama: Any
    lock: asyncio.Lock
    last_used: float
    model_id: str
    quantization: str | None
    embedding: bool


class ModelCache:
    """LRU cache for loaded GGUF models."""

    def __init__(self, max_models: int):
        self._max = max_models
        self._entries: dict[tuple[str, str | None, bool], CacheEntry] = {}
        self._cache_lock = threading.Lock()

    def load_model(
        self,
        gguf_path: Path,
        model_id: str,
        quantization: str | None,
        n_ctx: int,
        n_gpu_layers: int,
        n_threads: Optional[int] = None,
        embedding: bool = False,
    ) -> CacheEntry:
        """
        Load a GGUF model into memory.

        BLOCKING - must be called from a thread via run_in_executor, not async context.

        Args:
            gguf_path: Path to the .gguf file
            model_id: HuggingFace model ID (for logging)
            quantization: Quantization used (for logging)
            n_ctx: Context window size
            n_gpu_layers: Layers to offload to GPU
            n_threads: CPU threads (None = auto)
            embedding: If True, load model in embedding mode (for llama.embed())

        Returns:
            CacheEntry with loaded Llama instance

        Raises:
            ModelLoadError if loading fails
        """
        try:
            mode_str = "embedding" if embedding else "chat"
            logger.info(
                f"Loading model {model_id} from {gguf_path} "
                f"(quantization={quantization}, n_ctx={n_ctx}, gpu_layers={n_gpu_layers}, mode={mode_str})"
            )

            try:
                llama = Llama(
                    model_path=str(gguf_path),
                    n_ctx=n_ctx,
                    n_gpu_layers=n_gpu_layers,
                    n_threads=n_threads,
                    embedding=embedding,
                    verbose=False,
                )
            except ValueError as e:
                # llama-cpp-python raises ValueError("Failed to load model from file: <path>")
                # when the architecture is unsupported. The "unknown model architecture" detail
                # only appears in llama.cpp stderr, not in the Python exception message.
                # Fall back to Transformers if the file exists but llama-cpp-python can't load it.
                if "Failed to load model from file" not in str(e) or not Path(gguf_path).exists():
                    raise
                logger.warning(
                    f"llama-cpp-python does not support architecture for {model_id} ({e}). "
                    "Falling back to HuggingFace Transformers backend (slower, higher RAM usage)."
                )
                from core.services.transformers_backend import TransformersLlama
                llama = TransformersLlama(
                    model_path=str(gguf_path),
                    model_id=model_id,
                    n_ctx=n_ctx,
                    n_gpu_layers=n_gpu_layers,
                    n_threads=n_threads,
                    embedding=embedding,
                )

            logger.info(f"Successfully loaded {model_id} ({mode_str})")

            entry = CacheEntry(
                llama=llama,
                lock=asyncio.Lock(),
                last_used=time.monotonic(),
                model_id=model_id,
                quantization=quantization,
                embedding=embedding,
            )
            return entry
        except Exception as e:
            logger.error(f"Failed to load model {model_id}: {e}")
            raise

    @asynccontextmanager
    async def acquire(
        self,
        model_id: str,
        quantization: str | None,
        gguf_path: Path,
        n_ctx: int,
        n_gpu_layers: int,
        n_threads: Optional[int] = None,
        embedding: bool = False,
    ):
        """
        Acquire a model for inference.

        Loads the model if not in cache. Ensures only one inference request
        uses the model at a time via asyncio.Lock.

        Usage:
            async with cache.acquire(...) as llama:
                # run inference
                result = llama.create_chat_completion(...) or llama.embed(...)

        Args:
            model_id: HuggingFace model ID
            quantization: Quantization version
            gguf_path: Path to .gguf file
            n_ctx: Context window size
            n_gpu_layers: GPU layers
            n_threads: CPU threads
            embedding: If True, acquire in embedding mode

        Yields:
            Llama instance
        """
        loop = asyncio.get_event_loop()
        key = (model_id, quantization, embedding)

        # Check cache and load if needed
        with self._cache_lock:
            if key not in self._entries:
                if len(self._entries) >= self._max:
                    self._evict_lru()

            if key not in self._entries:
                # Load in thread pool
                entry = await loop.run_in_executor(
                    None,
                    self.load_model,
                    gguf_path,
                    model_id,
                    quantization,
                    n_ctx,
                    n_gpu_layers,
                    n_threads,
                    embedding,
                )
                self._entries[key] = entry
            else:
                entry = self._entries[key]

        # Acquire per-model lock for serialized inference
        await entry.lock.acquire()
        try:
            entry.last_used = time.monotonic()
            yield entry.llama
        finally:
            entry.lock.release()

    def _evict_lru(self) -> None:
        """Evict least-recently-used entry. Must be called with _cache_lock held."""
        if not self._entries:
            return

        lru_key = min(self._entries.keys(), key=lambda k: self._entries[k].last_used)
        entry = self._entries.pop(lru_key)

        mode_str = "embedding" if entry.embedding else "chat"
        logger.info(f"Evicting model {entry.model_id} (quantization={entry.quantization}, mode={mode_str}) from cache")

        # Cleanup
        try:
            del entry.llama
        except Exception as e:
            logger.warning(f"Error cleaning up evicted model: {e}")

    def shutdown(self) -> None:
        """Release all loaded models and clear cache."""
        logger.info("Shutting down model cache")
        with self._cache_lock:
            for key, entry in list(self._entries.items()):
                try:
                    mode_str = "embedding" if entry.embedding else "chat"
                    logger.info(f"Unloading {entry.model_id} ({mode_str})")
                    del entry.llama
                except Exception as e:
                    logger.warning(f"Error unloading {entry.model_id}: {e}")
            self._entries.clear()
        logger.info("Model cache shut down")


# Module-level singleton
_cache: Optional[ModelCache] = None


def init_model_cache(max_models: int) -> None:
    """Initialize the global model cache."""
    global _cache
    _cache = ModelCache(max_models)
    logger.info(f"Model cache initialized (max_models={max_models})")


def get_model_cache() -> ModelCache:
    """Get the global model cache. Must be initialized first."""
    if _cache is None:
        raise RuntimeError("Model cache not initialized. Call init_model_cache() in lifespan.")
    return _cache


def shutdown_model_cache() -> None:
    """Shutdown the global model cache."""
    global _cache
    if _cache:
        _cache.shutdown()
        _cache = None
