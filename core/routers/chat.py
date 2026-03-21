"""OpenAI Chat Completion API compatible endpoints."""

import logging
import json

import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from core.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
)
from core.services.inference_service import (
    run_chat_completion,
    run_chat_completion_stream,
    ModelNotFoundError,
    ModelNotReadyError,
    GGUFFileNotFoundError,
    AmbiguousGGUFError,
    ModelLoadError,
    InferenceRuntimeError,
    InferenceError,
)
from core.services.download_service import download_store, sanitize_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["chat"])


def _error_response(message: str, code: str, http_status: int) -> dict:
    """Build OpenAI-compatible error response."""
    return {
        "error": {
            "message": message,
            "type": "invalid_request_error" if http_status < 500 else "server_error",
            "code": code,
        }
    }


@router.post("/chat/completions", response_model=None)
async def create_chat_completion(request: ChatCompletionRequest):
    """
    OpenAI-compatible chat completions endpoint.

    Supports text inputs, vision (image) inputs, function/tool calling,
    structured outputs (JSON mode), and streaming.

    Args:
        request: ChatCompletionRequest matching OpenAI API spec

    Returns:
        ChatCompletionResponse for non-streaming,
        StreamingResponse (text/event-stream) for streaming=True

    Raises:
        400: Invalid parameters
        404: Model not found
        422: Model not ready, ambiguous model files, etc.
        500: Server error during inference
    """
    try:
        if request.stream:
            return StreamingResponse(
                _stream_generator(request),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            return await run_chat_completion(request)

    except ModelNotFoundError as e:
        logger.error(f"Model not found: {e}")
        error = _error_response(str(e), "model_not_found", 404)
        raise HTTPException(status_code=404, detail=error)

    except ModelNotReadyError as e:
        logger.error(f"Model not ready: {e}")
        error = _error_response(str(e), "model_not_ready", 422)
        raise HTTPException(status_code=422, detail=error)

    except GGUFFileNotFoundError as e:
        logger.error(f"GGUF file not found: {e}")
        error = _error_response(str(e), "model_file_missing", 500)
        raise HTTPException(status_code=500, detail=error)

    except AmbiguousGGUFError as e:
        logger.error(f"Ambiguous GGUF files: {e}")
        error = _error_response(str(e), "ambiguous_model", 422)
        raise HTTPException(status_code=422, detail=error)

    except ModelLoadError as e:
        logger.error(f"Model load error: {e}")
        error = _error_response(str(e), "model_load_failed", 500)
        raise HTTPException(status_code=500, detail=error)

    except InferenceRuntimeError as e:
        logger.error(f"Inference runtime error: {e}")
        error = _error_response(str(e), "inference_failed", 500)
        raise HTTPException(status_code=500, detail=error)

    except ValueError as e:
        logger.error(f"Invalid parameters: {e}")
        error = _error_response(str(e), "invalid_parameter", 400)
        raise HTTPException(status_code=400, detail=error)

    except InferenceError as e:
        logger.error(f"Inference error: {e}")
        error = _error_response(str(e), "inference_error", 500)
        raise HTTPException(status_code=500, detail=error)


async def _stream_generator(request: ChatCompletionRequest):
    """
    Async generator for streaming chat completion chunks.

    Yields SSE-formatted strings.
    """
    try:
        async for chunk in run_chat_completion_stream(request):
            yield chunk
    except ModelNotFoundError as e:
        logger.error(f"Stream error - model not found: {e}")
        error = _error_response(str(e), "model_not_found", 404)
        yield f"data: {json.dumps(error)}\n\n"
        yield "data: [DONE]\n\n"

    except ModelNotReadyError as e:
        logger.error(f"Stream error - model not ready: {e}")
        error = _error_response(str(e), "model_not_ready", 422)
        yield f"data: {json.dumps(error)}\n\n"
        yield "data: [DONE]\n\n"

    except (GGUFFileNotFoundError, AmbiguousGGUFError, ModelLoadError, InferenceRuntimeError) as e:
        logger.error(f"Stream error: {e}")
        error_code = {
            GGUFFileNotFoundError: "model_file_missing",
            AmbiguousGGUFError: "ambiguous_model",
            ModelLoadError: "model_load_failed",
            InferenceRuntimeError: "inference_failed",
        }.get(type(e), "inference_error")
        error = _error_response(str(e), error_code, 500)
        yield f"data: {json.dumps(error)}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Unexpected stream error: {e}", exc_info=True)
        error = _error_response(f"Unexpected error: {e}", "internal_error", 500)
        yield f"data: {json.dumps(error)}\n\n"
        yield "data: [DONE]\n\n"


@router.get("/models")
async def list_models():
    """
    List all available models for inference.

    Returns models that have completed downloading in OpenAI API format.
    """
    try:
        completed = [e for e in download_store.values() if e.status == "completed"]

        models = [
            {
                "id": entry.repo_id,
                "object": "model",
                "owned_by": "local",
                "created": int(time.time()),
                "permission": [
                    {
                        "id": "modelperm-123",
                        "object": "model_permission",
                        "created": int(time.time()),
                        "allow_create_engine": False,
                        "allow_sampling": True,
                        "allow_logprobs": True,
                        "allow_search_indices": False,
                        "allow_view": True,
                        "allow_fine_tuning": False,
                        "organization": "*",
                        "group_id": None,
                        "is_blocking": False,
                    }
                ],
            }
            for entry in completed
        ]

        return {"object": "list", "data": models}

    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/models/{model_id:path}")
async def get_model(model_id: str):
    """
    Get information for a specific model.

    Args:
        model_id: HuggingFace model ID (e.g., "user/model-name")

    Returns:
        Model info in OpenAI API format

    Raises:
        404: Model not found or not ready
    """
    try:
        # Try sanitized lookup first, then by repo_id
        entry_id = sanitize_id(model_id)
        entry = download_store.get(entry_id) or next(
            (e for e in download_store.values() if e.repo_id == model_id), None
        )

        if not entry:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "message": f"Model '{model_id}' not found",
                        "type": "invalid_request_error",
                        "code": "model_not_found",
                    }
                },
            )

        if entry.status != "completed":
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "message": f"Model '{model_id}' is not ready (status: {entry.status})",
                        "type": "invalid_request_error",
                        "code": "model_not_ready",
                    }
                },
            )

        model_info = {
            "id": entry.repo_id,
            "object": "model",
            "owned_by": "local",
            "created": int(time.time()),
            "permission": [
                {
                    "id": "modelperm-123",
                    "object": "model_permission",
                    "created": int(time.time()),
                    "allow_create_engine": False,
                    "allow_sampling": True,
                    "allow_logprobs": True,
                    "allow_search_indices": False,
                    "allow_view": True,
                    "allow_fine_tuning": False,
                    "organization": "*",
                    "group_id": None,
                    "is_blocking": False,
                }
            ],
        }

        return model_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model: {e}")
        raise HTTPException(status_code=500, detail={"error": str(e)})
