from __future__ import annotations

import logging
import threading

from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingModelNotAvailableError(RuntimeError):
    """Raised when the embedding model cannot be loaded (e.g. not downloaded, no network)."""


class EmbeddingInferenceError(RuntimeError):
    """Raised when the Sentence Transformers model fails to encode input."""


class EmbeddingEngineManager:
    """Lazily loads and caches a single Sentence Transformers model.

    Independent of `InferenceEngineManager` (chat/litert_lm): the embedding
    model is a different runtime with its own dependency stack, and
    Sentence Transformers manages its own multi-file HF repo download/cache
    rather than going through the app's single-file model download manager.
    """

    def __init__(self) -> None:
        self._model: SentenceTransformer | None = None
        self._load_lock = threading.Lock()

    def _load_model(self) -> SentenceTransformer:
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is not None:
                return self._model
            settings.embedding_cache_dir.mkdir(parents=True, exist_ok=True)
            try:
                self._model = SentenceTransformer(
                    settings.embedding_model_repo_id,
                    cache_folder=str(settings.embedding_cache_dir),
                    device=settings.embedding_device,
                )
            except Exception as exc:
                raise EmbeddingModelNotAvailableError(
                    f"Embedding model '{settings.embedding_model_repo_id}' could not be loaded: {exc}"
                ) from exc
            return self._model

    def warm_up(self) -> None:
        try:
            self._load_model()
        except EmbeddingModelNotAvailableError as exc:
            logger.warning("Embedding engine warm-up failed: %s", exc)

    def encode(self, texts: list[str], dimensions: int | None = None) -> tuple[list[list[float]], int]:
        model = self._load_model()
        try:
            vectors = model.encode(
                texts,
                normalize_embeddings=True,
                truncate_dim=dimensions,
                batch_size=settings.embedding_max_batch_size,
                convert_to_numpy=True,
            )
            token_count = self._count_tokens(model, texts)
        except EmbeddingModelNotAvailableError:
            raise
        except Exception as exc:
            raise EmbeddingInferenceError(f"Embedding generation failed: {exc}") from exc
        return vectors.tolist(), token_count

    @staticmethod
    def _count_tokens(model: SentenceTransformer, texts: list[str]) -> int:
        try:
            features = model.tokenize(texts)
            attention_mask = features.get("attention_mask")
            if attention_mask is not None:
                return int(attention_mask.sum().item())
        except Exception:  # pragma: no cover - defensive fallback
            logger.debug("Falling back to whitespace token count for usage reporting", exc_info=True)
        return sum(max(1, len(text.split())) for text in texts)


embedding_engine_manager = EmbeddingEngineManager()
