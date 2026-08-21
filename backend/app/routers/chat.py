import asyncio
import json
import logging
import time

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
from app.services.metrics import LLMEvent, metrics_writer, new_request_id, now_ts
from app.routers.metrics import LATENCY, REQUESTS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["chat"])

_ENDPOINT = "/v1/chat/completions"


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

    request_id = new_request_id()
    start = time.monotonic()

    if request.stream:
        return await _stream_response(request, request_id, start)
    return await _blocking_response(request, request_id, start)


def _message_text(content: str | list) -> str:
    if isinstance(content, str):
        return content
    return "".join(p.text for p in content if p.type == "text")


def _prompt_text(request: ChatCompletionRequest) -> str:
    return "\n".join(_message_text(m.content) for m in request.messages)


def _log_event(
    request: ChatCompletionRequest,
    request_id: str,
    start: float,
    *,
    status: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    error_message: str | None = None,
    output_text: str | None = None,
    stream: bool = False,
) -> None:
    latency_ms = (time.monotonic() - start) * 1000
    REQUESTS.labels(endpoint=_ENDPOINT, status=status).inc()
    LATENCY.labels(model=request.model).observe(latency_ms)
    metrics_writer.log(
        LLMEvent(
            request_id=request_id,
            ts=now_ts(),
            model_name=request.model,
            endpoint=_ENDPOINT,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            status=status,
            error_message=error_message,
            stream=stream,
            input_text=_prompt_text(request) if settings.enable_trace_logging else None,
            output_text=output_text if settings.enable_trace_logging else None,
            client_id=request.user,
            metadata={"temperature": request.temperature, "max_tokens": request.max_tokens},
        )
    )


async def _blocking_response(
    request: ChatCompletionRequest, request_id: str, start: float
) -> ChatCompletionResponse:
    try:
        text, reasoning, prompt_tokens, completion_tokens = await inference_engine_manager.generate(
            request.messages, request.max_tokens, request.enable_thinking
        )
    except ModelNotAvailableError as exc:
        _log_event(request, request_id, start, status="error", error_message=str(exc))
        raise _openai_error(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc), "model_not_available") from exc
    except InferenceError as exc:
        _log_event(request, request_id, start, status="error", error_message=str(exc))
        raise _openai_error(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc), "server_error") from exc

    content = f"<think>{reasoning}</think>{text}" if reasoning else text
    _log_event(
        request,
        request_id,
        start,
        status="ok",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        output_text=content,
    )

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


async def _stream_response(
    request: ChatCompletionRequest, request_id: str, start: float
) -> StreamingResponse:
    async def event_stream():
        chunk_id = None
        output_parts: list[str] = []
        error_message: str | None = None
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
                    output_parts.append(delta.content)
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
            error_message = str(exc)
            error_type = "model_not_available" if isinstance(exc, ModelNotAvailableError) else "server_error"
            error_payload = {"error": {"message": str(exc), "type": error_type, "param": None, "code": None}}
            yield f"data: {json.dumps(error_payload)}\n\n"
        finally:
            try:
                output_text = "".join(output_parts)
                completion_tokens = (
                    await asyncio.to_thread(inference_engine_manager.count_tokens, output_text)
                    if output_text
                    else 0
                )
                prompt_tokens = await asyncio.to_thread(
                    inference_engine_manager.count_tokens, _prompt_text(request)
                )
                _log_event(
                    request,
                    request_id,
                    start,
                    status="error" if error_message else "ok",
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    error_message=error_message,
                    output_text=output_text,
                    stream=True,
                )
            except Exception:
                logger.exception("Failed to log streaming metrics event %s", request_id)
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
