import asyncio
import json
import logging
import time

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.model_catalog import ModelCategory, get_catalog_entry
from app.core.openai_errors import openai_error as _openai_error
from app.core.tool_parser import StreamingToolCallBuffer, extract_tool_calls
from app.services.model_download_service import model_download_manager
from app.schemas.chat import (
    ChatCompletionChoice,
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    ChatCompletionChunkDeltaToolCall,
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


def _validate_model(request: ChatCompletionRequest) -> None:
    try:
        entry = get_catalog_entry(request.model)
    except KeyError as exc:
        raise _openai_error(
            status.HTTP_400_BAD_REQUEST,
            f"The model '{request.model}' does not exist.",
            "invalid_request_error",
            param="model",
        ) from exc
    if entry.category != ModelCategory.LLM:
        raise _openai_error(
            status.HTTP_400_BAD_REQUEST,
            f"The model '{request.model}' is not an LLM and cannot be used for chat.",
            "invalid_request_error",
            param="model",
        )
    if not model_download_manager.check_availability(request.model).available:
        raise _openai_error(
            status.HTTP_400_BAD_REQUEST,
            f"The model '{request.model}' has not been downloaded yet.",
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


def _message_text(content: str | list | None) -> str:
    if content is None:
        return ""
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
            request.messages,
            request.max_tokens,
            request.enable_thinking,
            model_id=request.model,
            tools=request.tools,
        )
    except ModelNotAvailableError as exc:
        _log_event(request, request_id, start, status="error", error_message=str(exc))
        raise _openai_error(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc), "model_not_available") from exc
    except InferenceError as exc:
        _log_event(request, request_id, start, status="error", error_message=str(exc))
        raise _openai_error(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc), "server_error") from exc

    residual_text, tool_calls = extract_tool_calls(text)
    if tool_calls:
        finish_reason = "tool_calls"
        if reasoning:
            assistant_content = (
                f"<think>{reasoning}</think>{residual_text}"
                if residual_text
                else f"<think>{reasoning}</think>"
            )
        else:
            assistant_content = residual_text
    else:
        finish_reason = "stop"
        assistant_content = f"<think>{reasoning}</think>{text}" if reasoning else text

    _log_event(
        request,
        request_id,
        start,
        status="ok",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        output_text=text,
    )

    return ChatCompletionResponse(
        model=request.model,
        choices=[
            ChatCompletionChoice(
                message=ChatMessage(
                    role="assistant",
                    content=assistant_content,
                    tool_calls=tool_calls if tool_calls else None,
                ),
                finish_reason=finish_reason,
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
        reasoning_parts: list[str] = []
        error_message: str | None = None
        tool_buffer = StreamingToolCallBuffer()
        tc_index = 0
        try:
            first = True
            in_thinking = False
            async for delta in inference_engine_manager.generate_stream(
                request.messages,
                request.max_tokens,
                request.enable_thinking,
                model_id=request.model,
                tools=request.tools,
            ):
                piece = ""
                if delta.reasoning:
                    if not in_thinking:
                        piece += "<think>"
                        in_thinking = True
                    piece += delta.reasoning
                    reasoning_parts.append(delta.reasoning)
                if delta.content:
                    if in_thinking:
                        piece += "</think>"
                        in_thinking = False
                    output_parts.append(delta.content)
                    text_to_yield, extracted_calls = tool_buffer.process_chunk(delta.content)
                    if text_to_yield:
                        piece += text_to_yield
                else:
                    extracted_calls = []

                if piece:
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

                for tc in extracted_calls:
                    tc_chunk = ChatCompletionChunk(
                        model=request.model,
                        choices=[
                            ChatCompletionChunkChoice(
                                delta=ChatCompletionChunkDelta(
                                    role="assistant" if first else None,
                                    tool_calls=[
                                        ChatCompletionChunkDeltaToolCall(
                                            index=tc_index,
                                            id=tc.id,
                                            type="function",
                                            function=tc.function,
                                        )
                                    ],
                                ),
                                finish_reason=None,
                            )
                        ],
                    )
                    chunk_id = chunk_id or tc_chunk.id
                    first = False
                    tc_index += 1
                    yield f"data: {tc_chunk.model_dump_json()}\n\n"

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

            final_text, final_calls = tool_buffer.finalize()
            if final_text:
                chunk = ChatCompletionChunk(
                    id=chunk_id,
                    model=request.model,
                    choices=[
                        ChatCompletionChunkChoice(
                            delta=ChatCompletionChunkDelta(
                                role="assistant" if first else None,
                                content=final_text,
                            ),
                            finish_reason=None,
                        )
                    ],
                )
                first = False
                yield f"data: {chunk.model_dump_json()}\n\n"

            for tc in final_calls:
                tc_chunk = ChatCompletionChunk(
                    id=chunk_id,
                    model=request.model,
                    choices=[
                        ChatCompletionChunkChoice(
                            delta=ChatCompletionChunkDelta(
                                role="assistant" if first else None,
                                tool_calls=[
                                    ChatCompletionChunkDeltaToolCall(
                                        index=tc_index,
                                        id=tc.id,
                                        type="function",
                                        function=tc.function,
                                    )
                                ],
                            ),
                            finish_reason=None,
                        )
                    ],
                )
                first = False
                tc_index += 1
                yield f"data: {tc_chunk.model_dump_json()}\n\n"

            final_finish_reason = "tool_calls" if tool_buffer.has_tool_calls else "stop"
            final_chunk = ChatCompletionChunk(
                id=chunk_id or ChatCompletionChunk(model=request.model, choices=[]).id,
                model=request.model,
                choices=[
                    ChatCompletionChunkChoice(
                        delta=ChatCompletionChunkDelta(),
                        finish_reason=final_finish_reason,
                    )
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
                reasoning_text = "".join(reasoning_parts)
                completion_tokens = (
                    await asyncio.to_thread(
                        inference_engine_manager.count_tokens, output_text, request.model
                    )
                    if output_text
                    else 0
                ) + (
                    await asyncio.to_thread(
                        inference_engine_manager.count_tokens, reasoning_text, request.model
                    )
                    if reasoning_text
                    else 0
                )
                prompt_tokens = await asyncio.to_thread(
                    inference_engine_manager.count_tokens, _prompt_text(request), request.model
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
