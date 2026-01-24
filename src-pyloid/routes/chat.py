"""OpenAI-compatible chat completion API routes."""

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from models import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ModelDetailResponse,
    ModelListResponse,
    ModelObject,
    ProblemDetail,
)
from services import inference_service, model_manager


# Create router with OpenAI-compatible prefix
router = APIRouter(prefix="/v1", tags=["chat"])


# ============================================================================
# Chat Completion Endpoints
# ============================================================================


@router.post(
    "/chat/completions",
    response_model=ChatCompletionResponse,
    responses={
        200: {"description": "Chat completion response"},
        400: {"model": ProblemDetail, "description": "Bad request"},
        404: {"model": ProblemDetail, "description": "Model not found"},
        422: {"model": ProblemDetail, "description": "Validation error"},
        500: {"model": ProblemDetail, "description": "Internal server error"},
        503: {"model": ProblemDetail, "description": "Service unavailable"},
    },
)
async def create_chat_completion(
    request: ChatCompletionRequest,
    http_request: Request,
):
    """Create a chat completion.
    
    This endpoint is compatible with the OpenAI Chat Completions API.
    It supports both streaming and non-streaming responses.
    
    Args:
        request: ChatCompletionRequest body
        http_request: FastAPI request object
        
    Returns:
        ChatCompletionResponse for non-streaming, or
        StreamingResponse with SSE for streaming
        
    Raises:
        HTTPException: On validation or inference errors
    """
    try:
        if request.stream:
            # Streaming response
            return StreamingResponse(
                _stream_chat_completion(request),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",  # Disable nginx buffering
                },
            )
        else:
            # Non-streaming response
            response = await inference_service.create_chat_completion(request)
            return response

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model not found: {request.model}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )


async def _stream_chat_completion(
    request: ChatCompletionRequest,
) -> AsyncGenerator[str, None]:
    """Generate SSE stream for chat completion.
    
    Args:
        request: ChatCompletionRequest
        
    Yields:
        SSE formatted data strings
    """
    try:
        async for chunk in inference_service.create_chat_completion_stream(request):
            # Format as SSE
            data = chunk.model_dump_json(exclude_none=True)
            yield f"data: {data}\n\n"
        
        # Send done marker
        yield "data: [DONE]\n\n"
        
    except FileNotFoundError:
        error_data = json.dumps({
            "error": {
                "message": f"Model not found: {request.model}",
                "type": "invalid_request_error",
                "code": "model_not_found",
            }
        })
        yield f"data: {error_data}\n\n"
    except Exception as e:
        error_data = json.dumps({
            "error": {
                "message": str(e),
                "type": "server_error",
                "code": "internal_error",
            }
        })
        yield f"data: {error_data}\n\n"


# ============================================================================
# Model Endpoints
# ============================================================================


@router.get(
    "/models",
    response_model=ModelListResponse,
    responses={
        200: {"description": "List of available models"},
        500: {"model": ProblemDetail, "description": "Internal server error"},
    },
)
async def list_models():
    """List all available models.
    
    Returns models available in the models directory, indicating which are loaded.
    
    Returns:
        ModelListResponse with list of model objects
    """
    try:
        available_models = await model_manager.list_available_models()
        
        models = [
            ModelObject(
                id=model["id"],
                created=model["created"],
                owned_by="local",
            )
            for model in available_models
        ]
        
        return ModelListResponse(data=models)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list models: {str(e)}",
        )


@router.get(
    "/models/{model_id:path}",
    response_model=ModelDetailResponse,
    responses={
        200: {"description": "Model details"},
        404: {"model": ProblemDetail, "description": "Model not found"},
        500: {"model": ProblemDetail, "description": "Internal server error"},
    },
)
async def get_model(model_id: str):
    """Get details for a specific model.
    
    Args:
        model_id: Model identifier (filename)
        
    Returns:
        ModelDetailResponse with model details
        
    Raises:
        HTTPException: If model not found
    """
    try:
        available_models = await model_manager.list_available_models()
        
        # Find the model
        model_info = None
        for model in available_models:
            if model["id"] == model_id or model_id in model["id"]:
                model_info = model
                break
        
        if model_info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model not found: {model_id}",
            )
        
        return ModelDetailResponse(
            id=model_info["id"],
            created=model_info["created"],
            owned_by="local",
            path=model_info["path"],
            size_bytes=model_info["size_bytes"],
            loaded=model_info["loaded"],
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get model: {str(e)}",
        )


@router.delete(
    "/models/{model_id:path}/unload",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Model unloaded successfully"},
        404: {"model": ProblemDetail, "description": "Model not found or not loaded"},
        500: {"model": ProblemDetail, "description": "Internal server error"},
    },
)
async def unload_model(model_id: str):
    """Unload a model from memory.
    
    Args:
        model_id: Model identifier
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If model not found or not loaded
    """
    try:
        success = await model_manager.unload_model(model_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model not found or not loaded: {model_id}",
            )
        
        return {"status": "success", "message": f"Model {model_id} unloaded"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unload model: {str(e)}",
        )


@router.get(
    "/models/loaded",
    responses={
        200: {"description": "List of loaded models"},
    },
)
async def list_loaded_models():
    """List all currently loaded models.
    
    Returns:
        List of loaded model metadata
    """
    loaded = model_manager.list_loaded_models()
    
    return {
        "object": "list",
        "data": [
            {
                "id": m.model_id,
                "path": str(m.path),
                "chat_format": m.chat_format,
                "n_ctx": m.n_ctx,
                "n_gpu_layers": m.n_gpu_layers,
                "loaded_at": m.loaded_at,
                "is_multimodal": m.is_multimodal,
                "size_bytes": m.size_bytes,
            }
            for m in loaded
        ],
    }
