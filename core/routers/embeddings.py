"""OpenAI Embeddings API compatible endpoints."""

import json
import logging

from fastapi import APIRouter, HTTPException

from core.schemas.embeddings import (
    EmbeddingRequest,
    EmbeddingResponse,
)
from core.services.embedding_service import (
    run_embeddings,
)
from core.services.inference_service import (
    ModelNotFoundError,
    ModelNotReadyError,
    GGUFFileNotFoundError,
    AmbiguousGGUFError,
    ModelLoadError,
    InferenceRuntimeError,
    InferenceError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["embeddings"])


def _error_response(message: str, code: str, http_status: int) -> dict:
    """Build OpenAI-compatible error response."""
    return {
        "error": {
            "message": message,
            "type": "invalid_request_error" if http_status < 500 else "server_error",
            "code": code,
        }
    }


@router.post("/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(request: EmbeddingRequest):
    """
    OpenAI-compatible embeddings endpoint.

    Generates embeddings for input text(s) using a local GGUF model.

    Args:
        request: EmbeddingRequest with input, model, and optional encoding_format, dimensions

    Returns:
        EmbeddingResponse with embeddings data and usage statistics

    Raises:
        400: Invalid input parameters
        404: Model not found
        422: Model not ready, ambiguous model files, etc.
        500: Server error during inference
    """
    try:
        return await run_embeddings(request)

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

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        error = _error_response(f"Unexpected error: {e}", "internal_error", 500)
        raise HTTPException(status_code=500, detail=error)
