"""Embedding inference service using llama-cpp-python."""

import asyncio
import base64
import logging
import struct
import time
import uuid
from pathlib import Path
from typing import Any

from core.services.download_service import sanitize_id
from core.schemas.embeddings import (
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingObject,
    EmbeddingUsage,
)
from core.services.model_cache import get_model_cache
from core.services.inference_service import (
    resolve_model_entry,
    InferenceError,
    ModelNotFoundError,
    ModelNotReadyError,
    GGUFFileNotFoundError,
    AmbiguousGGUFError,
    ModelLoadError,
    InferenceRuntimeError,
)
from core.config import settings

logger = logging.getLogger(__name__)


def _normalize_input(input_data: Any) -> list[str]:
    """
    Normalize input to list of strings.

    Args:
        input_data: str | list[str] | list[int] | list[list[int]]

    Returns:
        List of strings

    Raises:
        ValueError: If input is invalid or in unsupported format
    """
    if isinstance(input_data, str):
        if not input_data or not input_data.strip():
            raise ValueError("Input string cannot be empty")
        return [input_data]

    if isinstance(input_data, list):
        if not input_data:
            raise ValueError("Input list cannot be empty")

        # Check if it's a list of strings
        if all(isinstance(item, str) for item in input_data):
            for item in input_data:
                if not item or not item.strip():
                    raise ValueError("Input strings cannot be empty")
            return input_data

        # Check if it's a list of integers (token IDs)
        if all(isinstance(item, int) for item in input_data):
            raise ValueError("Token array input not supported. Please provide text strings instead.")

        # Check if it's a list of token lists
        if all(isinstance(item, list) and all(isinstance(i, int) for i in item) for item in input_data):
            raise ValueError("Token batch input not supported. Please provide text strings instead.")

        raise ValueError(
            "Input list must contain only strings (or be a single string). "
            "Token inputs (lists of integers) are not supported."
        )

    raise ValueError(
        f"Input must be a string or list of strings, got {type(input_data).__name__}"
    )


def _to_base64(embedding: list[float]) -> str:
    """
    Encode embedding vector as base64.

    Args:
        embedding: List of floats

    Returns:
        Base64-encoded string representing the embedding
    """
    # Pack as little-endian float32 values
    packed = struct.pack(f"<{len(embedding)}f", *embedding)
    return base64.b64encode(packed).decode("utf-8")


def _count_tokens(llama, texts: list[str]) -> int:
    """
    Count total tokens for input texts.

    Args:
        llama: Llama instance
        texts: List of text strings

    Returns:
        Total token count
    """
    total = 0
    for text in texts:
        try:
            tokens = llama.tokenize(text.encode("utf-8"), add_bos=True)
            total += len(tokens)
        except Exception as e:
            logger.warning(f"Error tokenizing text for counting: {e}")
            # Fallback: estimate tokens (~4 chars per token)
            total += len(text) // 4

    return total


async def run_embeddings(request: EmbeddingRequest) -> EmbeddingResponse:
    """
    Run embedding inference for input text(s).

    Args:
        request: EmbeddingRequest

    Returns:
        EmbeddingResponse with embeddings data and usage info

    Raises:
        ModelNotFoundError: Model not found
        ModelNotReadyError: Model not ready
        ModelLoadError: Error loading model
        InferenceRuntimeError: Error during inference
        ValueError: Invalid input
        InferenceError: Other inference error
    """
    logger.info(f"Embedding request for model: {request.model}")

    # Normalize input
    try:
        texts = _normalize_input(request.input)
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error normalizing input: {e}")
        raise ValueError(f"Invalid input: {e}") from e

    # Resolve model
    try:
        entry = resolve_model_entry(request.model)
        if not entry.path:
            raise ModelNotFoundError(f"Model '{request.model}' has no local path")
    except InferenceError:
        raise
    except Exception as e:
        logger.error(f"Error resolving model: {e}")
        raise InferenceRuntimeError(f"Failed to resolve model: {e}") from e

    # Get model cache
    cache = get_model_cache()
    loop = asyncio.get_event_loop()

    try:
        # Acquire model in embedding mode
        async with cache.acquire(
            model_id=request.model,
            quantization=entry.quantization,
            gguf_path=Path(entry.path),
            n_ctx=settings.inference_n_ctx,
            n_gpu_layers=settings.inference_n_gpu_layers,
            n_threads=settings.inference_n_threads,
            embedding=True,
        ) as llama:
            # Run embedding in executor (llama.embed is blocking)
            embedding_result = await loop.run_in_executor(
                None,
                llama.embed,
                texts,
            )

            # embedding_result is list[list[float]]
            if not isinstance(embedding_result, list):
                raise InferenceRuntimeError(
                    f"Expected list of embeddings, got {type(embedding_result)}"
                )

            # Apply dimensions truncation if requested
            if request.dimensions:
                embedding_result = [
                    vec[: request.dimensions] for vec in embedding_result
                ]

            # Apply encoding format
            embeddings_data = []
            for i, embedding in enumerate(embedding_result):
                if request.encoding_format == "base64":
                    embedding_value = _to_base64(embedding)
                else:
                    embedding_value = embedding

                embeddings_data.append(
                    EmbeddingObject(index=i, embedding=embedding_value)
                )

            # Count tokens for usage
            prompt_tokens = await loop.run_in_executor(
                None, _count_tokens, llama, texts
            )

            # Build response
            response = EmbeddingResponse(
                data=embeddings_data,
                model=request.model,
                usage=EmbeddingUsage(
                    prompt_tokens=prompt_tokens,
                    total_tokens=prompt_tokens,
                ),
            )

            logger.info(
                f"Embedding done: {len(texts)} texts, {prompt_tokens} tokens"
            )
            return response

    except InferenceError:
        raise
    except Exception as e:
        logger.error(f"Embedding error: {e}", exc_info=True)
        raise InferenceRuntimeError(f"Embedding failed: {e}") from e
