"""Chat completion inference service."""

import logging
import time
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator

from llama_cpp import Llama

from core.services.download_service import download_store, sanitize_id
from core.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatCompletionMessage,
    ChatCompletionStreamChunk,
    ChatCompletionStreamChoice,
    ChatCompletionDelta,
    UsageInfo,
    Message,
    Role,
    FinishReason,
    ImageContentPart,
)
from core.services.model_cache import get_model_cache
from core.config import settings

logger = logging.getLogger(__name__)


# ===== Custom Exceptions =====

class InferenceError(Exception):
    """Base inference error."""
    pass


class ModelNotFoundError(InferenceError):
    """Model not found in downloads."""
    pass


class ModelNotReadyError(InferenceError):
    """Model download not complete."""
    def __init__(self, model_id: str, status: str):
        self.model_id = model_id
        self.status = status
        super().__init__(f"Model {model_id} is not ready (status: {status})")


class GGUFFileNotFoundError(InferenceError):
    """No .gguf file found in model directory."""
    pass


class AmbiguousGGUFError(InferenceError):
    """Multiple .gguf files found, ambiguous."""
    def __init__(self, local_path: str, filenames: list[str]):
        self.local_path = local_path
        self.filenames = filenames
        msg = f"Multiple GGUF files found in {local_path}: {filenames}. Specify quantization."
        super().__init__(msg)


class ModelLoadError(InferenceError):
    """Error loading model with llama-cpp-python."""
    pass


class InferenceRuntimeError(InferenceError):
    """Error during inference."""
    pass


# ===== Helper Functions =====

def resolve_model_entry(model_id: str):
    """
    Look up a completed model in the download store.

    Args:
        model_id: HuggingFace model ID (e.g., "unsloth/Qwen3.5-0.8B-GGUF")

    Returns:
        DownloadEntry with status="completed"

    Raises:
        ModelNotFoundError: No entry found
        ModelNotReadyError: Entry found but status != "completed"
    """
    # Try sanitized lookup first
    entry_id = sanitize_id(model_id)
    entry = download_store.get(entry_id)

    if not entry:
        # Try by repo_id in case we're using a different format
        entry = next((e for e in download_store.values() if e.repo_id == model_id), None)
        if not entry:
            raise ModelNotFoundError(f"Model '{model_id}' not found in downloads")

    if entry.status != "completed":
        raise ModelNotReadyError(model_id, entry.status)

    return entry


def resolve_gguf_path(local_path: str, quantization: str | None) -> Path:
    """
    Find the .gguf file within a model directory.

    Priority:
    1. If quantization specified: find file matching quantization string
    2. If exactly one .gguf file: use it
    3. Otherwise: error

    Args:
        local_path: Path to model directory
        quantization: Quantization string (e.g., "Q4_K_M") or None

    Returns:
        Path to .gguf file

    Raises:
        GGUFFileNotFoundError: No .gguf files found
        AmbiguousGGUFError: Multiple .gguf files, need quantization
    """
    directory = Path(local_path)

    # Find all .gguf files (recursive search for sharded models)
    gguf_files = list(directory.glob("*.gguf"))
    if not gguf_files:
        gguf_files = list(directory.glob("**/*.gguf"))

    if not gguf_files:
        raise GGUFFileNotFoundError(f"No .gguf files found in {local_path}")

    # If quantization specified, try to find a match
    if quantization:
        quantization_upper = quantization.upper()
        matches = [f for f in gguf_files if quantization_upper in f.name.upper()]

        if len(matches) == 1:
            logger.info(f"Found GGUF file for quantization {quantization}: {matches[0].name}")
            return matches[0]

        if len(matches) > 1:
            logger.warning(
                f"Multiple GGUF files match quantization {quantization}, using first: {matches[0].name}"
            )
            return matches[0]

        logger.debug(
            f"No GGUF file matches quantization {quantization}, falling back to single-file logic"
        )

    # Single file case
    if len(gguf_files) == 1:
        logger.info(f"Using single GGUF file: {gguf_files[0].name}")
        return gguf_files[0]

    # Multiple files, ambiguous
    filenames = [f.name for f in gguf_files]
    raise AmbiguousGGUFError(local_path, filenames)


def build_llama_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """
    Convert OpenAI message format to llama-cpp-python format.

    Args:
        messages: List of Message objects

    Returns:
        List of dicts in llama-cpp-python format
    """
    result = []

    for msg in messages:
        if msg.role == Role.system:
            result.append({"role": "system", "content": msg.content})
        elif msg.role == Role.user:
            content = msg.content
            if isinstance(content, str):
                result.append({"role": "user", "content": content})
            else:
                # content is list[ContentPart]
                content_list = []
                for part in content:
                    if part.type == "text":
                        content_list.append({"type": "text", "text": part.text})
                    elif part.type == "image_url":
                        content_list.append({
                            "type": "image_url",
                            "image_url": {
                                "url": part.image_url.url,
                                "detail": part.image_url.detail,
                            }
                        })
                result.append({"role": "user", "content": content_list})
        elif msg.role == Role.assistant:
            content_dict: dict[str, Any] = {"role": "assistant"}
            if msg.content:
                content_dict["content"] = msg.content
            if msg.tool_calls:
                content_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in msg.tool_calls
                ]
            result.append(content_dict)
        elif msg.role == Role.tool:
            result.append({
                "role": "tool",
                "tool_call_id": msg.tool_call_id,
                "content": msg.content,
            })

    return result


def build_llama_kwargs(request: ChatCompletionRequest, tools_list: list[dict] | None = None) -> dict[str, Any]:
    """
    Build kwargs for llama.create_chat_completion() from OpenAI request.

    Args:
        request: ChatCompletionRequest
        tools_list: Converted tools list (if any)

    Returns:
        Dict of kwargs for llama.create_chat_completion()
    """
    kwargs: dict[str, Any] = {
        "temperature": request.temperature or 0.7,
        "top_p": request.top_p or 1.0,
    }

    if request.top_k is not None:
        kwargs["top_k"] = request.top_k

    if request.max_tokens is not None:
        kwargs["max_tokens"] = request.max_tokens

    if request.stop is not None:
        kwargs["stop"] = request.stop

    if request.presence_penalty is not None:
        kwargs["presence_penalty"] = request.presence_penalty

    if request.frequency_penalty is not None:
        kwargs["frequency_penalty"] = request.frequency_penalty

    if request.seed is not None:
        kwargs["seed"] = request.seed

    if request.logprobs:
        kwargs["logprobs"] = True
        if request.top_logprobs is not None:
            kwargs["top_logprobs"] = request.top_logprobs

    if request.n and request.n > 1:
        kwargs["n"] = request.n

    if tools_list:
        kwargs["tools"] = tools_list

    if request.tool_choice is not None:
        kwargs["tool_choice"] = request.tool_choice

    # response_format
    if request.response_format:
        if request.response_format.type == "json_object":
            kwargs["response_format"] = {"type": "json_object"}
        elif request.response_format.type == "json_schema":
            # Pass the schema directly
            kwargs["response_format"] = request.response_format.json_schema

    return kwargs


async def run_chat_completion(request: ChatCompletionRequest) -> ChatCompletionResponse:
    """
    Run a non-streaming chat completion.

    Args:
        request: ChatCompletionRequest

    Returns:
        ChatCompletionResponse

    Raises:
        ModelNotFoundError: Model not found
        ModelNotReadyError: Model not ready
        InferenceRuntimeError: Inference failed
    """
    logger.info(f"Chat completion request for model: {request.model}")

    # Resolve model
    try:
        entry = resolve_model_entry(request.model)
        # entry.path is the exact path to the .gguf file
        if not entry.path:
            raise ModelNotFoundError(f"Model '{request.model}' has no local path")
    except InferenceError:
        raise
    except Exception as e:
        logger.error(f"Error resolving model: {e}")
        raise InferenceRuntimeError(f"Failed to resolve model: {e}") from e

    # Get model cache and acquire model
    cache = get_model_cache()

    try:
        messages_dicts = build_llama_messages(request.messages)

        # Convert tools if present
        tools_list = None
        if request.tools:
            tools_list = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.function.name,
                        "description": tool.function.description,
                        "parameters": tool.function.parameters or {},
                    }
                }
                for tool in request.tools
            ]

        kwargs = build_llama_kwargs(request, tools_list)

        # Check for vision (image content) and warn if model may not support it
        has_images = any(
            isinstance(msg.content, list) and any(isinstance(p, ImageContentPart) for p in msg.content)
            for msg in request.messages
            if hasattr(msg, "content")
        )
        if has_images:
            logger.warning(f"Vision input detected. Ensure model {request.model} supports multimodal inputs.")

        # Run inference in executor with model lock
        loop = __import__("asyncio").get_event_loop()

        async with cache.acquire(
            model_id=request.model,
            quantization=entry.quantization,
            gguf_path=Path(entry.path),
            n_ctx=settings.inference_n_ctx,
            n_gpu_layers=settings.inference_n_gpu_layers,
            n_threads=settings.inference_n_threads,
        ) as llama:
            result = await loop.run_in_executor(
                None,
                llama.create_chat_completion,
                messages_dicts,
                None,  # functions (deprecated)
                kwargs,
            )

        # Parse result
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())

        choices = []
        for i, choice in enumerate(result.get("choices", [])):
            message_dict = choice.get("message", {})

            tool_calls = None
            if "tool_calls" in message_dict:
                from core.schemas.chat import ToolCall, FunctionCall
                tool_calls = [
                    ToolCall(
                        id=tc.get("id", f"call_{uuid.uuid4().hex[:12]}"),
                        type="function",
                        function=FunctionCall(
                            name=tc["function"]["name"],
                            arguments=tc["function"]["arguments"],
                        )
                    )
                    for tc in message_dict.get("tool_calls", [])
                ]

            finish_reason = choice.get("finish_reason", "stop")
            finish_reason_enum = FinishReason.stop
            if finish_reason == "stop":
                finish_reason_enum = FinishReason.stop
            elif finish_reason == "length":
                finish_reason_enum = FinishReason.length
            elif finish_reason == "tool_calls":
                finish_reason_enum = FinishReason.tool_calls

            choices.append(
                ChatCompletionChoice(
                    index=i,
                    message=ChatCompletionMessage(
                        role=Role.assistant,
                        content=message_dict.get("content"),
                        tool_calls=tool_calls,
                    ),
                    finish_reason=finish_reason_enum,
                    logprobs=choice.get("logprobs"),
                )
            )

        usage = result.get("usage", {})

        response = ChatCompletionResponse(
            id=completion_id,
            created=created,
            model=request.model,
            choices=choices,
            usage=UsageInfo(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            ),
        )

        logger.info(
            f"Chat completion done: {response.usage.total_tokens} tokens "
            f"({response.usage.prompt_tokens} prompt, {response.usage.completion_tokens} completion)"
        )
        return response

    except InferenceError:
        raise
    except Exception as e:
        logger.error(f"Inference error: {e}", exc_info=True)
        raise InferenceRuntimeError(f"Inference failed: {e}") from e


async def run_chat_completion_stream(
    request: ChatCompletionRequest,
) -> AsyncGenerator[str, None]:
    """
    Run a streaming chat completion.

    Yields SSE-formatted data chunks.

    Args:
        request: ChatCompletionRequest

    Yields:
        SSE data strings (e.g., "data: {...}\n\n")

    Raises:
        ModelNotFoundError, ModelNotReadyError, InferenceRuntimeError
    """
    logger.info(f"Streaming chat completion request for model: {request.model}")

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

    cache = get_model_cache()
    import asyncio
    import json

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())
    chunk_queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def producer():
        """Run blocking inference in thread, push chunks to queue."""
        loop = asyncio.get_event_loop()

        try:
            messages_dicts = build_llama_messages(request.messages)

            tools_list = None
            if request.tools:
                tools_list = [
                    {
                        "type": "function",
                        "function": {
                            "name": tool.function.name,
                            "description": tool.function.description,
                            "parameters": tool.function.parameters or {},
                        }
                    }
                    for tool in request.tools
                ]

            kwargs = build_llama_kwargs(request, tools_list)

            async with cache.acquire(
                model_id=request.model,
                quantization=entry.quantization,
                gguf_path=Path(entry.path),
                n_ctx=settings.inference_n_ctx,
                n_gpu_layers=settings.inference_n_gpu_layers,
                n_threads=settings.inference_n_threads,
            ) as llama:
                def blocking_stream():
                    for chunk in llama.create_chat_completion(
                        messages_dicts,
                        functions=None,
                        stream=True,
                        **kwargs,
                    ):
                        loop.call_soon_threadsafe(chunk_queue.put_nowait, chunk)

                await loop.run_in_executor(None, blocking_stream)

        except Exception as e:
            logger.error(f"Streaming inference error: {e}", exc_info=True)
            error_chunk = {
                "error": {
                    "message": str(e),
                    "type": "server_error",
                    "code": "inference_failed",
                }
            }
            loop.call_soon_threadsafe(chunk_queue.put_nowait, error_chunk)
        finally:
            loop.call_soon_threadsafe(chunk_queue.put_nowait, None)  # Sentinel

    # Start producer task
    task = asyncio.create_task(producer())

    try:
        while True:
            chunk = await chunk_queue.get()

            if chunk is None:
                # End of stream
                yield "data: [DONE]\n\n"
                break

            if "error" in chunk:
                # Error chunk
                yield f"data: {json.dumps(chunk)}\n\n"
                break

            # Normal chunk
            choices = []
            for i, choice in enumerate(chunk.get("choices", [])):
                delta_dict = choice.get("delta", {})

                tool_calls = None
                if "tool_calls" in delta_dict:
                    from core.schemas.chat import ToolCall, FunctionCall
                    tool_calls = [
                        ToolCall(
                            id=tc.get("id", f"call_{uuid.uuid4().hex[:12]}"),
                            type="function",
                            function=FunctionCall(
                                name=tc["function"]["name"],
                                arguments=tc["function"]["arguments"],
                            )
                        )
                        for tc in delta_dict.get("tool_calls", [])
                    ]

                finish_reason = choice.get("finish_reason")
                finish_reason_enum = None
                if finish_reason == "stop":
                    finish_reason_enum = FinishReason.stop
                elif finish_reason == "length":
                    finish_reason_enum = FinishReason.length
                elif finish_reason == "tool_calls":
                    finish_reason_enum = FinishReason.tool_calls

                choices.append(
                    ChatCompletionStreamChoice(
                        index=i,
                        delta=ChatCompletionDelta(
                            role=Role.assistant if delta_dict.get("role") else None,
                            content=delta_dict.get("content"),
                            tool_calls=tool_calls,
                        ),
                        finish_reason=finish_reason_enum,
                    )
                )

            stream_chunk = ChatCompletionStreamChunk(
                id=completion_id,
                created=created,
                model=request.model,
                choices=choices,
            )

            yield f"data: {stream_chunk.model_dump_json()}\n\n"

    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
