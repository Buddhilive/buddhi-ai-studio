"""Inference service for chat completion with OpenAI API compatibility."""

import asyncio
import json
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from llama_cpp import Llama

from config import get_settings
from models import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ChatMessageResponse,
    Choice,
    ContentPart,
    DeltaContent,
    FinishReason,
    ImageContentPart,
    ResponseFormat,
    ResponseFormatType,
    Role,
    StreamChoice,
    TextContentPart,
    Tool,
    ToolCall,
    Usage,
)
from services.model_manager import model_manager
from utils.inference_utils import (
    base64_to_data_uri,
    download_image_to_base64,
    format_response_format,
    format_tool_choice,
    is_data_uri,
    is_valid_url,
)


class InferenceService:
    """Handles chat completion inference with full OpenAI API compatibility.
    
    Supports streaming, tool calling, structured outputs, and multimodal inputs.
    """

    def __init__(self):
        """Initialize inference service."""
        self._model_manager = model_manager

    async def create_chat_completion(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Create a non-streaming chat completion.
        
        Args:
            request: Chat completion request
            
        Returns:
            ChatCompletionResponse
            
        Raises:
            FileNotFoundError: If model not found
            RuntimeError: If inference fails
        """
        settings = get_settings()
        
        # Load model
        llm = await self._model_manager.load_model(request.model)
        
        # Prepare messages
        messages = await self._prepare_messages(request.messages)
        
        # Prepare kwargs for llama-cpp-python
        kwargs = self._build_completion_kwargs(request, streaming=False)
        
        # Run inference in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: llm.create_chat_completion(messages=messages, **kwargs)
        )
        
        # Convert to response
        return self._convert_to_response(result, request.model)

    async def create_chat_completion_stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """Create a streaming chat completion.
        
        Args:
            request: Chat completion request
            
        Yields:
            ChatCompletionChunk for each token/delta
            
        Raises:
            FileNotFoundError: If model not found
            RuntimeError: If inference fails
        """
        settings = get_settings()
        
        # Load model
        llm = await self._model_manager.load_model(request.model)
        
        # Prepare messages
        messages = await self._prepare_messages(request.messages)
        
        # Prepare kwargs for llama-cpp-python
        kwargs = self._build_completion_kwargs(request, streaming=True)
        
        # Generate completion ID and timestamp
        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())
        
        # Track usage if requested
        include_usage = (
            request.stream_options 
            and request.stream_options.get("include_usage", False)
        )
        prompt_tokens = 0
        completion_tokens = 0
        
        # Create streaming generator
        loop = asyncio.get_event_loop()
        
        # Run the streaming call in a way that yields chunks
        stream = await loop.run_in_executor(
            None,
            lambda: llm.create_chat_completion(messages=messages, **kwargs)
        )
        
        first_chunk = True
        
        try:
            for chunk in stream:
                # Process each chunk
                choices = chunk.get("choices", [])
                
                if not choices:
                    continue
                
                choice = choices[0]
                delta = choice.get("delta", {})
                finish_reason = choice.get("finish_reason")
                
                # Build delta content
                delta_content = DeltaContent(
                    role="assistant" if first_chunk else None,
                    content=delta.get("content"),
                    tool_calls=self._extract_tool_calls(delta.get("tool_calls")),
                )
                
                first_chunk = False
                
                # Build stream choice
                stream_choice = StreamChoice(
                    index=choice.get("index", 0),
                    delta=delta_content,
                    finish_reason=FinishReason(finish_reason) if finish_reason else None,
                )
                
                # Track completion tokens
                if delta.get("content"):
                    completion_tokens += 1  # Approximate
                
                # Build chunk
                yield ChatCompletionChunk(
                    id=completion_id,
                    created=created,
                    model=request.model,
                    choices=[stream_choice],
                )
                
                # If finished, break
                if finish_reason:
                    break
            
            # Send usage if requested
            if include_usage:
                # Estimate prompt tokens (rough approximation)
                prompt_tokens = sum(
                    len(str(m.content).split()) * 2 if m.content else 0
                    for m in request.messages
                )
                
                yield ChatCompletionChunk(
                    id=completion_id,
                    created=created,
                    model=request.model,
                    choices=[],
                    usage=Usage(
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=prompt_tokens + completion_tokens,
                    ),
                )
                
        except Exception as e:
            raise RuntimeError(f"Streaming inference failed: {str(e)}")

    async def _prepare_messages(
        self,
        messages: List[ChatMessage],
    ) -> List[Dict[str, Any]]:
        """Prepare messages for llama-cpp-python, handling multimodal content.
        
        Args:
            messages: List of chat messages
            
        Returns:
            List of message dicts for llama-cpp-python
        """
        prepared = []
        
        for msg in messages:
            prepared_msg: Dict[str, Any] = {"role": msg.role.value}
            
            # Handle content
            if msg.content is None:
                prepared_msg["content"] = None
            elif isinstance(msg.content, str):
                prepared_msg["content"] = msg.content
            elif isinstance(msg.content, list):
                # Multimodal content
                prepared_msg["content"] = await self._prepare_multimodal_content(msg.content)
            
            # Handle tool calls (assistant messages)
            if msg.tool_calls:
                prepared_msg["tool_calls"] = [
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
            
            # Handle tool call ID (tool response messages)
            if msg.tool_call_id:
                prepared_msg["tool_call_id"] = msg.tool_call_id
            
            # Handle name
            if msg.name:
                prepared_msg["name"] = msg.name
            
            prepared.append(prepared_msg)
        
        return prepared

    async def _prepare_multimodal_content(
        self,
        content: List[ContentPart],
    ) -> List[Dict[str, Any]]:
        """Prepare multimodal content parts.
        
        Args:
            content: List of content parts
            
        Returns:
            List of prepared content part dicts
        """
        prepared = []
        
        for part in content:
            if isinstance(part, TextContentPart) or (isinstance(part, dict) and part.get("type") == "text"):
                text = part.text if isinstance(part, TextContentPart) else part.get("text", "")
                prepared.append({"type": "text", "text": text})
                
            elif isinstance(part, ImageContentPart) or (isinstance(part, dict) and part.get("type") == "image_url"):
                image_url = part.image_url if isinstance(part, ImageContentPart) else part.get("image_url", {})
                url = image_url.url if hasattr(image_url, "url") else image_url.get("url", "")
                
                # Convert URL to data URI if needed
                if is_valid_url(url) and not is_data_uri(url):
                    data_uri = await download_image_to_base64(url)
                    if data_uri:
                        url = data_uri
                elif not is_data_uri(url):
                    # Assume it's base64 without prefix
                    url = base64_to_data_uri(url)
                
                prepared.append({
                    "type": "image_url",
                    "image_url": {"url": url}
                })
            
            elif isinstance(part, dict):
                # Pass through as-is if already a dict
                prepared.append(part)
        
        return prepared

    def _build_completion_kwargs(
        self,
        request: ChatCompletionRequest,
        streaming: bool,
    ) -> Dict[str, Any]:
        """Build kwargs for llama-cpp-python create_chat_completion.
        
        Args:
            request: Chat completion request
            streaming: Whether this is a streaming request
            
        Returns:
            Dict of kwargs for create_chat_completion
        """
        settings = get_settings()
        kwargs: Dict[str, Any] = {}
        
        # Streaming
        kwargs["stream"] = streaming
        
        # Max tokens
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        else:
            kwargs["max_tokens"] = settings.default_max_tokens
        
        # Temperature
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        
        # Top P
        if request.top_p is not None:
            kwargs["top_p"] = request.top_p
        
        # Top K (llama-cpp specific)
        if request.top_k is not None:
            kwargs["top_k"] = request.top_k
        
        # Frequency penalty
        if request.frequency_penalty is not None:
            kwargs["frequency_penalty"] = request.frequency_penalty
        
        # Presence penalty
        if request.presence_penalty is not None:
            kwargs["presence_penalty"] = request.presence_penalty
        
        # Repetition penalty (llama-cpp specific)
        if request.repetition_penalty is not None:
            kwargs["repeat_penalty"] = request.repetition_penalty
        
        # Stop sequences
        if request.stop is not None:
            kwargs["stop"] = request.stop
        
        # Seed
        if request.seed is not None:
            kwargs["seed"] = request.seed
        
        # Tools
        if request.tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.function.name,
                        "description": tool.function.description,
                        "parameters": tool.function.parameters.model_dump() if tool.function.parameters else {},
                    }
                }
                for tool in request.tools
            ]
        
        # Tool choice
        if request.tool_choice is not None:
            formatted_choice = format_tool_choice(request.tool_choice)
            if formatted_choice:
                kwargs["tool_choice"] = formatted_choice
        
        # Response format
        if request.response_format is not None:
            formatted = format_response_format(request.response_format)
            if formatted:
                kwargs["response_format"] = formatted
        
        return kwargs

    def _convert_to_response(
        self,
        result: Dict[str, Any],
        model: str,
    ) -> ChatCompletionResponse:
        """Convert llama-cpp-python result to ChatCompletionResponse.
        
        Args:
            result: Raw result from llama-cpp-python
            model: Model identifier
            
        Returns:
            ChatCompletionResponse
        """
        choices = []
        
        for i, choice in enumerate(result.get("choices", [])):
            message = choice.get("message", {})
            
            # Extract tool calls if present
            tool_calls = self._extract_tool_calls(message.get("tool_calls"))
            
            # Build message response
            msg_response = ChatMessageResponse(
                role="assistant",
                content=message.get("content"),
                tool_calls=tool_calls,
            )
            
            # Map finish reason
            finish_reason = choice.get("finish_reason")
            if finish_reason:
                try:
                    finish_reason = FinishReason(finish_reason)
                except ValueError:
                    finish_reason = FinishReason.STOP
            
            choices.append(Choice(
                index=i,
                message=msg_response,
                finish_reason=finish_reason,
            ))
        
        # Build usage
        usage_data = result.get("usage", {})
        usage = Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )
        
        return ChatCompletionResponse(
            id=result.get("id", f"chatcmpl-{uuid.uuid4().hex}"),
            created=result.get("created", int(time.time())),
            model=model,
            choices=choices,
            usage=usage,
        )

    def _extract_tool_calls(
        self,
        tool_calls_data: Optional[List[Dict[str, Any]]],
    ) -> Optional[List[ToolCall]]:
        """Extract tool calls from llama-cpp-python response.
        
        Args:
            tool_calls_data: Raw tool calls data
            
        Returns:
            List of ToolCall or None
        """
        if not tool_calls_data:
            return None
        
        tool_calls = []
        for tc in tool_calls_data:
            function_data = tc.get("function", {})
            
            from models import FunctionCall
            
            tool_calls.append(ToolCall(
                id=tc.get("id", f"call_{uuid.uuid4().hex[:24]}"),
                type="function",
                function=FunctionCall(
                    name=function_data.get("name", ""),
                    arguments=function_data.get("arguments", "{}"),
                ),
            ))
        
        return tool_calls if tool_calls else None


# Global inference service instance
inference_service = InferenceService()
