"""OpenAI Responses API compatible routes.

This module implements the /v1/responses endpoint following the OpenAI
Responses API specification.
"""

import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from models import ProblemDetail
from models.responses_schemas import (
    ResponsesRequest,
    ResponsesResponse,
    ResponseStatus,
    StreamingEvent,
)
from services.responses_service import responses_service


# Create router with OpenAI-compatible prefix
router = APIRouter(prefix="/v1", tags=["responses"])


# ============================================================================
# Responses API Endpoints
# ============================================================================


@router.post(
    "/responses",
    response_model=ResponsesResponse,
    responses={
        200: {"description": "Response created successfully"},
        400: {"model": ProblemDetail, "description": "Bad request"},
        404: {"model": ProblemDetail, "description": "Model not found"},
        422: {"model": ProblemDetail, "description": "Validation error"},
        500: {"model": ProblemDetail, "description": "Internal server error"},
        503: {"model": ProblemDetail, "description": "Service unavailable"},
    },
    summary="Create a model response",
    description="""
Create a response from the model based on the provided input.

This endpoint is compatible with the OpenAI Responses API and supports:
- Text and multimodal input (images)
- Streaming responses via SSE
- Conversation continuity via previous_response_id
- Tool/function calling
- Structured outputs via text.format
- Reasoning extraction for compatible models
    """,
)
async def create_response(
    request: ResponsesRequest,
    http_request: Request,
):
    """Create a model response.

    Args:
        request: ResponsesRequest body
        http_request: FastAPI request object

    Returns:
        ResponsesResponse for non-streaming, or
        StreamingResponse with SSE for streaming

    Raises:
        HTTPException: On validation or inference errors
    """
    try:
        if request.stream:
            # Streaming response
            return StreamingResponse(
                _stream_response(request),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",  # Disable nginx buffering
                },
            )
        else:
            # Non-streaming response
            response = await responses_service.create_response(request)

            # Check for errors
            if response.status == ResponseStatus.FAILED:
                error_msg = response.error.get("message", "Unknown error") if response.error else "Unknown error"
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=error_msg,
                )

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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )


async def _stream_response(
    request: ResponsesRequest,
) -> AsyncGenerator[str, None]:
    """Generate SSE stream for response.

    Args:
        request: ResponsesRequest

    Yields:
        SSE formatted event strings
    """
    try:
        async for event in responses_service.create_response_stream(request):
            # Format as SSE with event type
            event_type = event.type
            event_data = event.model_dump_json(exclude_none=True)

            # SSE format: event: <type>\ndata: <json>\n\n
            yield f"event: {event_type}\ndata: {event_data}\n\n"

        # Send done marker
        yield "event: done\ndata: [DONE]\n\n"

    except FileNotFoundError:
        error_event = {
            "type": "error",
            "error": {
                "message": f"Model not found: {request.model}",
                "type": "invalid_request_error",
                "code": "model_not_found",
            },
        }
        yield f"event: error\ndata: {json.dumps(error_event)}\n\n"

    except Exception as e:
        error_event = {
            "type": "error",
            "error": {
                "message": str(e),
                "type": "server_error",
                "code": "internal_error",
            },
        }
        yield f"event: error\ndata: {json.dumps(error_event)}\n\n"


@router.get(
    "/responses/{response_id}",
    response_model=ResponsesResponse,
    responses={
        200: {"description": "Response retrieved successfully"},
        404: {"model": ProblemDetail, "description": "Response not found"},
    },
    summary="Retrieve a response",
    description="Retrieve a previously created response by its ID.",
)
async def get_response(response_id: str):
    """Get a previously created response.

    Args:
        response_id: Response ID

    Returns:
        ResponsesResponse

    Raises:
        HTTPException: If response not found
    """
    response = await responses_service.get_response(response_id)

    if response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Response not found: {response_id}",
        )

    return response


@router.delete(
    "/responses/{response_id}",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Response cancelled or deleted"},
        404: {"model": ProblemDetail, "description": "Response not found"},
    },
    summary="Cancel or delete a response",
    description="Cancel an in-progress response or delete a completed one.",
)
async def cancel_response(response_id: str):
    """Cancel or delete a response.

    Args:
        response_id: Response ID

    Returns:
        Success message

    Raises:
        HTTPException: If response not found
    """
    response = await responses_service.get_response(response_id)

    if response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Response not found: {response_id}",
        )

    # Note: Actual cancellation of in-progress requests would require
    # additional infrastructure (task tracking, cancellation tokens, etc.)
    # For now, we just acknowledge the request

    return {
        "id": response_id,
        "status": "cancelled" if response.status == ResponseStatus.IN_PROGRESS else "deleted",
    }
