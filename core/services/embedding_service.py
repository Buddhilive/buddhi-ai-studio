"""Embedding service — proxies to Ollama's OpenAI-compatible embeddings endpoint."""

import base64
import logging
import struct
from typing import Any

import httpx

from core.config import settings
from core.schemas.embeddings import (
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingObject,
    EmbeddingUsage,
)
from core.services.inference_service import (
    InferenceError,
    InferenceRuntimeError,
    ModelNotFoundError,
    _check_model_available,
)

logger = logging.getLogger(__name__)


def _normalize_input(input_data: Any) -> list[str]:
    """Normalize input to list of strings."""
    if isinstance(input_data, str):
        if not input_data or not input_data.strip():
            raise ValueError("Input string cannot be empty")
        return [input_data]

    if isinstance(input_data, list):
        if not input_data:
            raise ValueError("Input list cannot be empty")
        if all(isinstance(item, str) for item in input_data):
            for item in input_data:
                if not item or not item.strip():
                    raise ValueError("Input strings cannot be empty")
            return input_data
        if all(isinstance(item, int) for item in input_data):
            raise ValueError("Token array input not supported. Please provide text strings instead.")
        if all(isinstance(item, list) for item in input_data):
            raise ValueError("Token batch input not supported. Please provide text strings instead.")
        raise ValueError("Input list must contain only strings.")

    raise ValueError(f"Input must be a string or list of strings, got {type(input_data).__name__}")


def _to_base64(embedding: list[float]) -> str:
    """Encode embedding vector as base64 (little-endian float32)."""
    packed = struct.pack(f"<{len(embedding)}f", *embedding)
    return base64.b64encode(packed).decode("utf-8")


async def run_embeddings(request: EmbeddingRequest) -> EmbeddingResponse:
    """
    Run embedding inference via Ollama's /v1/embeddings endpoint.

    Raises:
        ValueError: Invalid input
        ModelNotFoundError: Model not installed
        InferenceRuntimeError: Ollama error
    """
    logger.info(f"Embedding request for model: {request.model}")

    texts = _normalize_input(request.input)
    await _check_model_available(request.model)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=120, write=30, pool=10)) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/v1/embeddings",
                json={"model": request.model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()

        raw_data = data.get("data", [])
        if not raw_data:
            raise InferenceRuntimeError("Ollama returned empty embeddings")

        embeddings_data = []
        for i, item in enumerate(raw_data):
            embedding = item.get("embedding", [])

            # Truncate dimensions if requested
            if request.dimensions:
                embedding = embedding[: request.dimensions]

            if request.encoding_format == "base64":
                embedding_value = _to_base64(embedding)
            else:
                embedding_value = embedding

            embeddings_data.append(EmbeddingObject(index=i, embedding=embedding_value))

        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)

        response = EmbeddingResponse(
            data=embeddings_data,
            model=request.model,
            usage=EmbeddingUsage(
                prompt_tokens=prompt_tokens,
                total_tokens=usage.get("total_tokens", prompt_tokens),
            ),
        )

        logger.info(f"Embedding done: {len(texts)} texts, {prompt_tokens} tokens")
        return response

    except (InferenceError, ValueError):
        raise
    except httpx.HTTPStatusError as e:
        raise InferenceRuntimeError(
            f"Ollama returned HTTP {e.response.status_code}: {e.response.text}"
        ) from e
    except Exception as e:
        logger.error(f"Embedding error: {e}", exc_info=True)
        raise InferenceRuntimeError(f"Embedding failed: {e}") from e
