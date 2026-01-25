"""Responses API service for OpenAI-compatible response generation.

This service handles the newer OpenAI Responses API format, converting
requests to llama-cpp-python format and managing conversation state.
"""

import asyncio
import json
import re
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union

from llama_cpp import Llama

from config import get_settings
from models.responses_schemas import (
    ContentPartAddedEvent,
    ContentPartDoneEvent,
    EasyInputMessage,
    FunctionCallArgumentsDeltaEvent,
    FunctionCallArgumentsDoneEvent,
    FunctionCallItem,
    FunctionCallOutput,
    FunctionToolDefinition,
    InputAudioItem,
    InputFileItem,
    InputImageItem,
    InputItem,
    InputTextItem,
    JsonObjectFormat,
    JsonSchemaFormat,
    OutputItemAddedEvent,
    OutputItemDoneEvent,
    OutputItemStatus,
    OutputMessageItem,
    OutputTextContent,
    OutputTextDeltaEvent,
    OutputTextDoneEvent,
    ReasoningConfig,
    ReasoningItem,
    ReasoningSummaryItem,
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseFailedEvent,
    ResponseInProgressEvent,
    ResponsesRequest,
    ResponsesResponse,
    ResponseStatus,
    ResponseUsage,
    StreamingEvent,
)
from services.model_manager import model_manager
from utils.inference_utils import (
    base64_to_data_uri,
    download_image_to_base64,
    format_tool_choice,
    is_data_uri,
    is_valid_url,
)


class ResponsesService:
    """Handles OpenAI Responses API requests.

    Supports conversation continuity, reasoning extraction, tool calling,
    structured outputs, and streaming.
    """

    def __init__(self):
        """Initialize responses service."""
        self._model_manager = model_manager
        # Store responses for continuation via previous_response_id
        self._response_store: Dict[str, ResponsesResponse] = {}
        self._max_stored_responses = 100  # Limit stored responses

    async def create_response(
        self,
        request: ResponsesRequest,
    ) -> ResponsesResponse:
        """Create a non-streaming response.

        Args:
            request: Responses API request

        Returns:
            ResponsesResponse

        Raises:
            FileNotFoundError: If model not found
            RuntimeError: If inference fails
        """
        settings = get_settings()

        # Load model
        llm = await self._model_manager.load_model(request.model)

        # Build messages from input and previous response
        messages = await self._build_messages(request)

        # Build completion kwargs
        kwargs = self._build_completion_kwargs(request, streaming=False)

        # Run inference in thread pool
        loop = asyncio.get_event_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: llm.create_chat_completion(messages=messages, **kwargs)
                ),
                timeout=settings.inference_timeout,
            )
        except asyncio.TimeoutError:
            return self._create_error_response(
                request.model,
                f"Inference timed out after {settings.inference_timeout}s",
            )
        except Exception as e:
            return self._create_error_response(request.model, str(e))

        # Convert to response
        response = self._convert_to_response(result, request)

        # Store for continuation
        self._store_response(response)

        return response

    async def create_response_stream(
        self,
        request: ResponsesRequest,
    ) -> AsyncGenerator[StreamingEvent, None]:
        """Create a streaming response.

        Args:
            request: Responses API request

        Yields:
            StreamingEvent for each update

        Raises:
            FileNotFoundError: If model not found
            RuntimeError: If inference fails
        """
        settings = get_settings()

        # Load model
        llm = await self._model_manager.load_model(request.model)

        # Build messages
        messages = await self._build_messages(request)

        # Build completion kwargs
        kwargs = self._build_completion_kwargs(request, streaming=True)

        # Create initial response object
        response_id = f"resp_{uuid.uuid4().hex}"
        created_at = int(time.time())

        initial_response = ResponsesResponse(
            id=response_id,
            created_at=created_at,
            model=request.model,
            status=ResponseStatus.IN_PROGRESS,
            output=[],
        )

        # Emit response.created event
        yield ResponseCreatedEvent(response=initial_response)

        # Create message output item
        message_id = f"msg_{uuid.uuid4().hex[:24]}"
        current_text = ""
        content_index = 0
        output_index = 0

        # Emit response.in_progress
        yield ResponseInProgressEvent(response=initial_response)

        # Add message output item
        message_item = OutputMessageItem(
            id=message_id,
            status=OutputItemStatus.IN_PROGRESS,
            content=[],
        )
        yield OutputItemAddedEvent(output_index=output_index, item=message_item)

        # Add content part
        content_part = OutputTextContent(text="")
        yield ContentPartAddedEvent(
            item_id=message_id,
            output_index=output_index,
            content_index=content_index,
            part=content_part,
        )

        # Run streaming inference
        loop = asyncio.get_event_loop()

        try:
            stream = await loop.run_in_executor(
                None,
                lambda: llm.create_chat_completion(messages=messages, **kwargs)
            )

            prompt_tokens = 0
            completion_tokens = 0
            accumulated_text = ""

            for chunk in stream:
                choices = chunk.get("choices", [])
                if not choices:
                    continue

                choice = choices[0]
                delta = choice.get("delta", {})
                content = delta.get("content", "")
                finish_reason = choice.get("finish_reason")

                if content:
                    accumulated_text += content
                    completion_tokens += 1

                    # Emit text delta
                    yield OutputTextDeltaEvent(
                        item_id=message_id,
                        output_index=output_index,
                        content_index=content_index,
                        delta=content,
                    )

                # Handle tool calls in streaming
                tool_calls = delta.get("tool_calls")
                if tool_calls:
                    for tc in tool_calls:
                        function_data = tc.get("function", {})
                        if function_data.get("arguments"):
                            yield FunctionCallArgumentsDeltaEvent(
                                item_id=message_id,
                                output_index=output_index,
                                call_id=tc.get("id", ""),
                                delta=function_data.get("arguments", ""),
                            )

                if finish_reason:
                    break

            # Extract reasoning if present
            reasoning_text, clean_text = self._extract_reasoning(accumulated_text)

            # Build final output items
            output_items: List[Any] = []

            # Add reasoning item if present
            if reasoning_text:
                reasoning_item = ReasoningItem(
                    summary=[ReasoningSummaryItem(text=reasoning_text)]
                )
                output_items.append(reasoning_item)

            # Emit text done
            yield OutputTextDoneEvent(
                item_id=message_id,
                output_index=output_index,
                content_index=content_index,
                text=clean_text,
            )

            # Complete content part
            final_content = OutputTextContent(text=clean_text)
            yield ContentPartDoneEvent(
                item_id=message_id,
                output_index=output_index,
                content_index=content_index,
                part=final_content,
            )

            # Complete message item
            final_message = OutputMessageItem(
                id=message_id,
                status=OutputItemStatus.COMPLETED,
                content=[final_content],
            )
            output_items.append(final_message)

            yield OutputItemDoneEvent(
                output_index=len(output_items) - 1,
                item=final_message,
            )

            # Estimate prompt tokens
            prompt_tokens = sum(
                len(str(m.get("content", "")).split()) * 2
                for m in messages
            )

            # Build final response
            final_response = ResponsesResponse(
                id=response_id,
                created_at=created_at,
                model=request.model,
                status=ResponseStatus.COMPLETED,
                output=output_items,
                usage=ResponseUsage(
                    input_tokens=prompt_tokens,
                    output_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    reasoning_tokens=len(reasoning_text.split()) if reasoning_text else None,
                ),
            )

            # Store for continuation
            self._store_response(final_response)

            # Emit completed event
            yield ResponseCompletedEvent(response=final_response)

        except Exception as e:
            error_response = ResponsesResponse(
                id=response_id,
                created_at=created_at,
                model=request.model,
                status=ResponseStatus.FAILED,
                output=[],
                error={"message": str(e), "type": "inference_error"},
            )
            yield ResponseFailedEvent(response=error_response)

    async def get_response(self, response_id: str) -> Optional[ResponsesResponse]:
        """Get a previously created response.

        Args:
            response_id: Response ID

        Returns:
            ResponsesResponse or None if not found
        """
        return self._response_store.get(response_id)

    async def _build_messages(
        self,
        request: ResponsesRequest,
    ) -> List[Dict[str, Any]]:
        """Build chat messages from Responses API input.

        Args:
            request: Responses API request

        Returns:
            List of message dicts for llama-cpp-python
        """
        messages: List[Dict[str, Any]] = []

        # Add system instructions if provided
        if request.instructions:
            messages.append({
                "role": "system",
                "content": request.instructions,
            })

        # Restore previous conversation if continuing
        if request.previous_response_id:
            prev_response = self._response_store.get(request.previous_response_id)
            if prev_response:
                # Add previous response output as assistant message
                for item in prev_response.output:
                    if isinstance(item, OutputMessageItem):
                        content_text = ""
                        for content in item.content:
                            if hasattr(content, "text"):
                                content_text += content.text
                        if content_text:
                            messages.append({
                                "role": "assistant",
                                "content": content_text,
                            })

        # Process current input
        if isinstance(request.input, str):
            # Simple string input
            messages.append({"role": "user", "content": request.input})
        elif isinstance(request.input, list):
            # Array of input items
            await self._process_input_items(request.input, messages)

        return messages

    async def _process_input_items(
        self,
        items: List[InputItem],
        messages: List[Dict[str, Any]],
    ) -> None:
        """Process input items and add to messages.

        Args:
            items: List of input items
            messages: Messages list to append to
        """
        for item in items:
            if isinstance(item, InputTextItem):
                messages.append({"role": "user", "content": item.text})

            elif isinstance(item, EasyInputMessage):
                messages.append({"role": item.role, "content": item.content})

            elif isinstance(item, InputImageItem):
                # Handle image input (multimodal)
                image_url = item.image_url
                if image_url:
                    if is_valid_url(image_url) and not is_data_uri(image_url):
                        data_uri = await download_image_to_base64(image_url)
                        if data_uri:
                            image_url = data_uri
                    elif not is_data_uri(image_url):
                        image_url = base64_to_data_uri(image_url)

                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ],
                })

            elif isinstance(item, InputAudioItem):
                # Audio input - convert to text note (limited support)
                messages.append({
                    "role": "user",
                    "content": f"[Audio input: {item.format} format, {len(item.data)} bytes base64]",
                })

            elif isinstance(item, InputFileItem):
                # File input - add as text reference
                filename = item.filename or "file"
                messages.append({
                    "role": "user",
                    "content": f"[File: {filename}]",
                })

            elif isinstance(item, FunctionCallOutput):
                # Tool result message
                messages.append({
                    "role": "tool",
                    "tool_call_id": item.call_id,
                    "content": item.output,
                })

            elif isinstance(item, dict):
                # Handle raw dict input
                item_type = item.get("type", "")
                if item_type == "input_text":
                    messages.append({"role": "user", "content": item.get("text", "")})
                elif "role" in item and "content" in item:
                    messages.append({"role": item["role"], "content": item["content"]})

    def _build_completion_kwargs(
        self,
        request: ResponsesRequest,
        streaming: bool,
    ) -> Dict[str, Any]:
        """Build kwargs for llama-cpp-python create_chat_completion.

        Args:
            request: Responses API request
            streaming: Whether this is a streaming request

        Returns:
            Dict of kwargs
        """
        settings = get_settings()
        kwargs: Dict[str, Any] = {"stream": streaming}

        # Max tokens
        if request.max_output_tokens is not None:
            kwargs["max_tokens"] = request.max_output_tokens
        else:
            kwargs["max_tokens"] = settings.default_max_tokens

        # Generation parameters
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.top_p is not None:
            kwargs["top_p"] = request.top_p
        if request.top_k is not None:
            kwargs["top_k"] = request.top_k
        if request.frequency_penalty is not None:
            kwargs["frequency_penalty"] = request.frequency_penalty
        if request.presence_penalty is not None:
            kwargs["presence_penalty"] = request.presence_penalty
        if request.stop is not None:
            kwargs["stop"] = request.stop
        if request.seed is not None:
            kwargs["seed"] = request.seed

        # Tools
        if request.tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters or {},
                    },
                }
                for tool in request.tools
                if isinstance(tool, FunctionToolDefinition)
            ]

        # Tool choice
        if request.tool_choice is not None:
            if isinstance(request.tool_choice, str):
                if request.tool_choice != "none":
                    kwargs["tool_choice"] = request.tool_choice
            else:
                kwargs["tool_choice"] = request.tool_choice

        # Response format (from text.format)
        if request.text and request.text.format:
            fmt = request.text.format
            if isinstance(fmt, JsonObjectFormat):
                kwargs["response_format"] = {"type": "json_object"}
            elif isinstance(fmt, JsonSchemaFormat):
                kwargs["response_format"] = {
                    "type": "json_object",
                    "schema": fmt.schema_,
                }

        return kwargs

    def _extract_reasoning(self, content: str) -> Tuple[Optional[str], str]:
        """Extract reasoning content from <think> tags.

        Args:
            content: Raw model output

        Returns:
            Tuple of (reasoning_text, clean_content)
        """
        if not content:
            return None, content

        # Pattern to match <think>...</think> tags
        pattern = r"<think>(.*?)</think>"
        matches = re.findall(pattern, content, re.DOTALL)

        if matches:
            reasoning = "\n".join(m.strip() for m in matches)
            clean_content = re.sub(pattern, "", content, flags=re.DOTALL).strip()
            return reasoning, clean_content

        return None, content

    def _convert_to_response(
        self,
        result: Dict[str, Any],
        request: ResponsesRequest,
    ) -> ResponsesResponse:
        """Convert llama-cpp-python result to ResponsesResponse.

        Args:
            result: Raw result from llama-cpp-python
            request: Original request

        Returns:
            ResponsesResponse
        """
        output_items: List[Any] = []

        for choice in result.get("choices", []):
            message = choice.get("message", {})
            content = message.get("content", "")

            # Extract reasoning
            reasoning_text, clean_text = self._extract_reasoning(content)

            # Add reasoning item if present
            if reasoning_text:
                output_items.append(
                    ReasoningItem(
                        summary=[ReasoningSummaryItem(text=reasoning_text)]
                    )
                )

            # Handle tool calls
            tool_calls = message.get("tool_calls", [])
            if tool_calls:
                for tc in tool_calls:
                    function_data = tc.get("function", {})
                    output_items.append(
                        FunctionCallItem(
                            call_id=tc.get("id", f"call_{uuid.uuid4().hex[:24]}"),
                            name=function_data.get("name", ""),
                            arguments=function_data.get("arguments", "{}"),
                            status=OutputItemStatus.COMPLETED,
                        )
                    )
            else:
                # Add message output item
                output_items.append(
                    OutputMessageItem(
                        status=OutputItemStatus.COMPLETED,
                        content=[OutputTextContent(text=clean_text)],
                    )
                )

        # Build usage
        usage_data = result.get("usage", {})
        usage = ResponseUsage(
            input_tokens=usage_data.get("prompt_tokens", 0),
            output_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        return ResponsesResponse(
            id=f"resp_{result.get('id', uuid.uuid4().hex)}",
            created_at=result.get("created", int(time.time())),
            model=request.model,
            status=ResponseStatus.COMPLETED,
            output=output_items,
            usage=usage,
        )

    def _create_error_response(
        self,
        model: str,
        error_message: str,
    ) -> ResponsesResponse:
        """Create an error response.

        Args:
            model: Model identifier
            error_message: Error message

        Returns:
            ResponsesResponse with error status
        """
        return ResponsesResponse(
            model=model,
            status=ResponseStatus.FAILED,
            output=[],
            error={"message": error_message, "type": "inference_error"},
        )

    def _store_response(self, response: ResponsesResponse) -> None:
        """Store response for continuation.

        Args:
            response: Response to store
        """
        # Enforce max stored responses (simple LRU-like behavior)
        if len(self._response_store) >= self._max_stored_responses:
            # Remove oldest entries
            oldest_keys = list(self._response_store.keys())[
                : len(self._response_store) - self._max_stored_responses + 1
            ]
            for key in oldest_keys:
                del self._response_store[key]

        self._response_store[response.id] = response


# Global responses service instance
responses_service = ResponsesService()
