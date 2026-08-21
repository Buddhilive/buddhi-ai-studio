from __future__ import annotations

import base64
import logging
import time

import numpy as np
from fastapi import APIRouter, status

from app.core.config import settings
from app.core.openai_errors import openai_error
from app.schemas.embeddings import (
    EmbeddingObject,
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingUsage,
)
from app.services.embedding_service import (
    EmbeddingInferenceError,
    EmbeddingModelNotAvailableError,
    embedding_engine_manager,
)
from app.services.metrics import LLMEvent, metrics_writer, new_request_id, now_ts
from app.routers.metrics import LATENCY, REQUESTS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["embeddings"])

_ENDPOINT = "/v1/embeddings"


def _validate_model(request: EmbeddingRequest) -> None:
    if request.model != settings.embedding_model_id:
        raise openai_error(
            status.HTTP_404_NOT_FOUND,
            f"The model '{request.model}' does not exist.",
            "invalid_request_error",
            param="model",
        )


def _normalize_input(request: EmbeddingRequest) -> list[str]:
    return [request.input] if isinstance(request.input, str) else request.input


def _encode_vector(vector: list[float], encoding_format: str) -> list[float] | str:
    if encoding_format != "base64":
        return vector
    array = np.asarray(vector, dtype="<f4")
    return base64.b64encode(array.tobytes()).decode("ascii")


def _log_event(
    request: EmbeddingRequest,
    request_id: str,
    start: float,
    *,
    status_label: str,
    prompt_tokens: int = 0,
    error_message: str | None = None,
) -> None:
    latency_ms = (time.monotonic() - start) * 1000
    REQUESTS.labels(endpoint=_ENDPOINT, status=status_label).inc()
    LATENCY.labels(model=request.model).observe(latency_ms)
    metrics_writer.log(
        LLMEvent(
            request_id=request_id,
            ts=now_ts(),
            model_name=request.model,
            endpoint=_ENDPOINT,
            prompt_tokens=prompt_tokens,
            completion_tokens=0,
            total_tokens=prompt_tokens,
            latency_ms=latency_ms,
            status=status_label,
            error_message=error_message,
            stream=False,
            input_text="\n".join(_normalize_input(request)) if settings.enable_trace_logging else None,
            output_text=None,
            client_id=request.user,
            metadata={"encoding_format": request.encoding_format, "dimensions": request.dimensions},
        )
    )


@router.post("/embeddings")
async def create_embeddings(request: EmbeddingRequest) -> EmbeddingResponse:
    _validate_model(request)

    request_id = new_request_id()
    start = time.monotonic()
    texts = _normalize_input(request)

    try:
        vectors, prompt_tokens = embedding_engine_manager.encode(texts, request.dimensions)
    except EmbeddingModelNotAvailableError as exc:
        _log_event(request, request_id, start, status_label="error", error_message=str(exc))
        raise openai_error(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc), "model_not_available") from exc
    except EmbeddingInferenceError as exc:
        _log_event(request, request_id, start, status_label="error", error_message=str(exc))
        raise openai_error(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc), "server_error") from exc
    except Exception as exc:  # pragma: no cover - defensive catch-all
        logger.exception("Unexpected error during embedding generation (request %s)", request_id)
        _log_event(request, request_id, start, status_label="error", error_message="internal_error")
        raise openai_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "An internal error occurred.", "server_error"
        ) from exc

    _log_event(request, request_id, start, status_label="ok", prompt_tokens=prompt_tokens)

    return EmbeddingResponse(
        model=request.model,
        data=[
            EmbeddingObject(embedding=_encode_vector(vector, request.encoding_format), index=index)
            for index, vector in enumerate(vectors)
        ],
        usage=EmbeddingUsage(prompt_tokens=prompt_tokens, total_tokens=prompt_tokens),
    )
