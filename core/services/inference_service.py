"""Chat completion inference service — proxies to Ollama's OpenAI-compatible API."""

import logging
from typing import AsyncGenerator

import httpx

from core.config import settings
from core.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
)

logger = logging.getLogger(__name__)


# ── Custom exceptions (kept for router error handling) ────────────────────────

class InferenceError(Exception):
    """Base inference error."""
    pass


class ModelNotFoundError(InferenceError):
    """Model not installed in Ollama."""
    pass


class ModelNotReadyError(InferenceError):
    """Model pull not yet complete."""
    def __init__(self, model_id: str, status: str):
        self.model_id = model_id
        self.status = status
        super().__init__(f"Model {model_id} is not ready (status: {status})")


class InferenceRuntimeError(InferenceError):
    """Error during inference."""
    pass


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _check_model_available(model_id: str) -> None:
    """
    Verify model is installed in Ollama.

    Raises:
        ModelNotFoundError: if the model is not in Ollama's tag list
        InferenceRuntimeError: if Ollama is unreachable
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            resp.raise_for_status()
            models = resp.json().get("models", [])
            names = {m.get("name", "") for m in models}
            if model_id not in names:
                raise ModelNotFoundError(
                    f"Model '{model_id}' is not installed. "
                    "Please visit the Models page to download it."
                )
    except ModelNotFoundError:
        raise
    except Exception as e:
        raise InferenceRuntimeError(f"Could not reach Ollama: {e}") from e


# ── Chat completion ───────────────────────────────────────────────────────────

async def run_chat_completion(request: ChatCompletionRequest) -> ChatCompletionResponse:
    """
    Run a non-streaming chat completion via Ollama.

    Raises:
        ModelNotFoundError, InferenceRuntimeError
    """
    logger.info(f"Chat completion request for model: {request.model}")

    await _check_model_available(request.model)

    payload = request.model_dump(exclude_none=True)
    payload["stream"] = False

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=300, write=30, pool=10)) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/v1/chat/completions",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        # Ollama returns an OpenAI-compatible response — parse directly
        response = ChatCompletionResponse.model_validate(data)
        logger.info(
            f"Chat completion done: {response.usage.total_tokens} tokens "
            f"({response.usage.prompt_tokens} prompt, {response.usage.completion_tokens} completion)"
        )
        return response

    except ModelNotFoundError:
        raise
    except httpx.HTTPStatusError as e:
        raise InferenceRuntimeError(
            f"Ollama returned HTTP {e.response.status_code}: {e.response.text}"
        ) from e
    except Exception as e:
        logger.error(f"Inference error: {e}", exc_info=True)
        raise InferenceRuntimeError(f"Inference failed: {e}") from e


async def run_chat_completion_stream(
    request: ChatCompletionRequest,
) -> AsyncGenerator[str, None]:
    """
    Run a streaming chat completion via Ollama.

    Proxies Ollama's SSE stream directly.

    Yields:
        SSE data strings (e.g., "data: {...}\\n\\n")

    Raises:
        ModelNotFoundError, InferenceRuntimeError
    """
    logger.info(f"Streaming chat completion request for model: {request.model}")

    await _check_model_available(request.model)

    payload = request.model_dump(exclude_none=True)
    payload["stream"] = True

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=300, write=30, pool=10)) as client:
            async with client.stream(
                "POST",
                f"{settings.ollama_base_url}/v1/chat/completions",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        yield line + "\n\n"

        yield "data: [DONE]\n\n"

    except ModelNotFoundError:
        raise
    except httpx.HTTPStatusError as e:
        raise InferenceRuntimeError(
            f"Ollama returned HTTP {e.response.status_code}"
        ) from e
    except Exception as e:
        logger.error(f"Streaming inference error: {e}", exc_info=True)
        raise InferenceRuntimeError(f"Streaming inference failed: {e}") from e
