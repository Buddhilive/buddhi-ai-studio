"""OpenAI Chat Completion API compatible endpoints."""

import logging
import json
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from core.schemas.chat import ChatCompletionRequest, ChatCompletionResponse
from core.services.inference_service import (
    run_chat_completion,
    run_chat_completion_stream,
    ModelNotFoundError,
    ModelNotReadyError,
    InferenceRuntimeError,
    InferenceError,
)
from core.services.download_service import pull_store

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
    """OpenAI-compatible chat completions endpoint."""
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
        raise HTTPException(status_code=404, detail=_error_response(str(e), "model_not_found", 404))

    except ModelNotReadyError as e:
        logger.error(f"Model not ready: {e}")
        raise HTTPException(status_code=422, detail=_error_response(str(e), "model_not_ready", 422))

    except InferenceRuntimeError as e:
        logger.error(f"Inference runtime error: {e}")
        raise HTTPException(status_code=500, detail=_error_response(str(e), "inference_failed", 500))

    except ValueError as e:
        logger.error(f"Invalid parameters: {e}")
        raise HTTPException(status_code=400, detail=_error_response(str(e), "invalid_parameter", 400))

    except InferenceError as e:
        logger.error(f"Inference error: {e}")
        raise HTTPException(status_code=500, detail=_error_response(str(e), "inference_error", 500))


async def _stream_generator(request: ChatCompletionRequest):
    """Async generator for streaming chat completion chunks."""
    try:
        async for chunk in run_chat_completion_stream(request):
            yield chunk

    except ModelNotFoundError as e:
        logger.error(f"Stream error - model not found: {e}")
        yield f"data: {json.dumps(_error_response(str(e), 'model_not_found', 404))}\n\n"
        yield "data: [DONE]\n\n"

    except ModelNotReadyError as e:
        logger.error(f"Stream error - model not ready: {e}")
        yield f"data: {json.dumps(_error_response(str(e), 'model_not_ready', 422))}\n\n"
        yield "data: [DONE]\n\n"

    except InferenceRuntimeError as e:
        logger.error(f"Stream error: {e}")
        yield f"data: {json.dumps(_error_response(str(e), 'inference_failed', 500))}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Unexpected stream error: {e}", exc_info=True)
        yield f"data: {json.dumps(_error_response(f'Unexpected error: {e}', 'internal_error', 500))}\n\n"
        yield "data: [DONE]\n\n"


@router.get("/models")
async def list_models():
    """List all available models in OpenAI API format."""
    completed = [e for e in pull_store.values() if e.status == "completed"]
    models = [
        {
            "id": entry.model,
            "object": "model",
            "owned_by": "local",
            "created": int(time.time()),
        }
        for entry in completed
    ]
    return {"object": "list", "data": models}


@router.get("/models/{model_id:path}")
async def get_model(model_id: str):
    """Get information for a specific model."""
    entry = next((e for e in pull_store.values() if e.model == model_id), None)

    if not entry:
        raise HTTPException(
            status_code=404,
            detail=_error_response(f"Model '{model_id}' not found", "model_not_found", 404),
        )

    if entry.status != "completed":
        raise HTTPException(
            status_code=422,
            detail=_error_response(
                f"Model '{model_id}' is not ready (status: {entry.status})",
                "model_not_ready",
                422,
            ),
        )

    return {"id": entry.model, "object": "model", "owned_by": "local", "created": int(time.time())}
