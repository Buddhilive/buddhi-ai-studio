import json

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.schemas.chat import (
    ChatCompletionChoice,
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    Usage,
)
from app.services.inference_service import (
    InferenceError,
    ModelNotAvailableError,
    inference_engine_manager,
)

router = APIRouter(prefix="/v1", tags=["chat"])


def _openai_error(status_code: int, message: str, error_type: str, param: str | None = None) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"message": message, "type": error_type, "param": param, "code": None}},
    )


def _validate_model(request: ChatCompletionRequest) -> None:
    if request.model != settings.chat_model_id:
        raise _openai_error(
            status.HTTP_400_BAD_REQUEST,
            f"The model '{request.model}' does not exist. Available model: '{settings.chat_model_id}'.",
            "invalid_request_error",
            param="model",
        )


@router.post("/chat/completions")
async def create_chat_completion(request: ChatCompletionRequest):
    _validate_model(request)

    if request.stream:
        return await _stream_response(request)
    return await _blocking_response(request)


async def _blocking_response(request: ChatCompletionRequest) -> ChatCompletionResponse:
    try:
        text, reasoning, prompt_tokens, completion_tokens = await inference_engine_manager.generate(
            request.messages, request.max_tokens, request.enable_thinking
        )
    except ModelNotAvailableError as exc:
        raise _openai_error(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc), "model_not_available") from exc
    except InferenceError as exc:
        raise _openai_error(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc), "server_error") from exc

    content = f"<think>{reasoning}</think>{text}" if reasoning else text

    return ChatCompletionResponse(
        model=request.model,
        choices=[
            ChatCompletionChoice(
                message=ChatMessage(role="assistant", content=content),
                finish_reason="stop",
            )
        ],
        usage=Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )


async def _stream_response(request: ChatCompletionRequest) -> StreamingResponse:
    async def event_stream():
        chunk_id = None
        try:
            first = True
            in_thinking = False
            async for delta in inference_engine_manager.generate_stream(
                request.messages, request.max_tokens, request.enable_thinking
            ):
                piece = ""
                if delta.reasoning:
                    if not in_thinking:
                        piece += "<think>"
                        in_thinking = True
                    piece += delta.reasoning
                if delta.content:
                    if in_thinking:
                        piece += "</think>"
                        in_thinking = False
                    piece += delta.content
                if not piece:
                    continue
                chunk = ChatCompletionChunk(
                    model=request.model,
                    choices=[
                        ChatCompletionChunkChoice(
                            delta=ChatCompletionChunkDelta(
                                role="assistant" if first else None,
                                content=piece,
                            ),
                            finish_reason=None,
                        )
                    ],
                )
                chunk_id = chunk_id or chunk.id
                first = False
                yield f"data: {chunk.model_dump_json()}\n\n"

            if in_thinking:
                closing_chunk = ChatCompletionChunk(
                    id=chunk_id,
                    model=request.model,
                    choices=[
                        ChatCompletionChunkChoice(
                            delta=ChatCompletionChunkDelta(content="</think>"),
                            finish_reason=None,
                        )
                    ],
                )
                yield f"data: {closing_chunk.model_dump_json()}\n\n"

            final_chunk = ChatCompletionChunk(
                id=chunk_id or ChatCompletionChunk(model=request.model, choices=[]).id,
                model=request.model,
                choices=[
                    ChatCompletionChunkChoice(delta=ChatCompletionChunkDelta(), finish_reason="stop")
                ],
            )
            yield f"data: {final_chunk.model_dump_json()}\n\n"
        except (ModelNotAvailableError, InferenceError) as exc:
            error_type = "model_not_available" if isinstance(exc, ModelNotAvailableError) else "server_error"
            error_payload = {"error": {"message": str(exc), "type": error_type, "param": None, "code": None}}
            yield f"data: {json.dumps(error_payload)}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
