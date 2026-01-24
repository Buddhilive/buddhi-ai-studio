"""OpenAI-compatible Pydantic models for chat completion API."""

import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Enums
# ============================================================================


class Role(str, Enum):
    """Message roles in a chat conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class FinishReason(str, Enum):
    """Reasons why the model stopped generating tokens."""

    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    CONTENT_FILTER = "content_filter"


class ResponseFormatType(str, Enum):
    """Response format types."""

    TEXT = "text"
    JSON_OBJECT = "json_object"
    JSON_SCHEMA = "json_schema"


# ============================================================================
# Content Parts (for multimodal support)
# ============================================================================


class TextContentPart(BaseModel):
    """Text content part in a message."""

    type: Literal["text"] = "text"
    text: str = Field(..., description="The text content")


class ImageUrl(BaseModel):
    """Image URL reference."""

    url: str = Field(
        ...,
        description="URL of the image or base64 data URI (data:image/...;base64,...)",
    )
    detail: Literal["auto", "low", "high"] = Field(
        default="auto",
        description="Image detail level for processing",
    )


class ImageContentPart(BaseModel):
    """Image content part in a message."""

    type: Literal["image_url"] = "image_url"
    image_url: ImageUrl = Field(..., description="The image URL object")


class AudioInputData(BaseModel):
    """Audio input data."""

    data: str = Field(..., description="Base64 encoded audio data")
    format: Literal["wav", "mp3", "flac", "webm"] = Field(
        ...,
        description="Audio format",
    )


class AudioContentPart(BaseModel):
    """Audio content part in a message."""

    type: Literal["input_audio"] = "input_audio"
    input_audio: AudioInputData = Field(..., description="The audio data object")


# Union type for content parts
ContentPart = Union[TextContentPart, ImageContentPart, AudioContentPart]


# ============================================================================
# Tool/Function Calling
# ============================================================================


class FunctionParameters(BaseModel):
    """JSON Schema for function parameters."""

    type: Literal["object"] = "object"
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameter definitions",
    )
    required: List[str] = Field(
        default_factory=list,
        description="Required parameter names",
    )

    model_config = {"extra": "allow"}


class FunctionDefinition(BaseModel):
    """Function definition for tool calling."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Function name",
    )
    description: Optional[str] = Field(
        default=None,
        description="Description of what the function does",
    )
    parameters: Optional[FunctionParameters] = Field(
        default=None,
        description="JSON Schema for function parameters",
    )
    strict: Optional[bool] = Field(
        default=None,
        description="Whether to enforce strict schema adherence",
    )


class Tool(BaseModel):
    """Tool definition (currently only function type is supported)."""

    type: Literal["function"] = "function"
    function: FunctionDefinition = Field(..., description="Function definition")


class ToolChoiceFunction(BaseModel):
    """Specific function to call."""

    name: str = Field(..., description="Name of the function to call")


class ToolChoiceObject(BaseModel):
    """Tool choice object for specifying a specific tool."""

    type: Literal["function"] = "function"
    function: ToolChoiceFunction = Field(..., description="Function to call")


# Tool choice can be string ("none", "auto", "required") or object
ToolChoice = Union[Literal["none", "auto", "required"], ToolChoiceObject]


class FunctionCall(BaseModel):
    """A function call made by the model."""

    name: str = Field(..., description="Name of the function to call")
    arguments: str = Field(..., description="JSON string of function arguments")


class ToolCall(BaseModel):
    """A tool call made by the model."""

    id: str = Field(
        default_factory=lambda: f"call_{uuid.uuid4().hex[:24]}",
        description="Unique identifier for this tool call",
    )
    type: Literal["function"] = "function"
    function: FunctionCall = Field(..., description="The function call details")


# ============================================================================
# Response Format & Structured Output
# ============================================================================


class JsonSchemaDefinition(BaseModel):
    """JSON Schema definition for structured outputs."""

    name: str = Field(..., description="Name of the schema")
    description: Optional[str] = Field(
        default=None,
        description="Description of the schema",
    )
    schema_: Dict[str, Any] = Field(
        ...,
        alias="schema",
        description="The JSON Schema object",
    )
    strict: Optional[bool] = Field(
        default=None,
        description="Whether to enforce strict schema adherence",
    )

    model_config = {"populate_by_name": True}


class ResponseFormat(BaseModel):
    """Response format specification."""

    type: ResponseFormatType = Field(
        default=ResponseFormatType.TEXT,
        description="Response format type",
    )
    json_schema: Optional[JsonSchemaDefinition] = Field(
        default=None,
        description="JSON Schema for structured output (when type is json_schema)",
    )


# ============================================================================
# Chat Messages
# ============================================================================


class ChatMessage(BaseModel):
    """A message in the chat conversation."""

    role: Role = Field(..., description="Role of the message author")
    content: Optional[Union[str, List[ContentPart]]] = Field(
        default=None,
        description="Content of the message (text or multimodal parts)",
    )
    name: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Optional name for the participant",
    )
    tool_calls: Optional[List[ToolCall]] = Field(
        default=None,
        description="Tool calls made by the assistant",
    )
    tool_call_id: Optional[str] = Field(
        default=None,
        description="ID of the tool call this message is responding to",
    )

    @field_validator("content", mode="before")
    @classmethod
    def validate_content(cls, v):
        """Ensure content is properly formatted."""
        if v is None:
            return v
        if isinstance(v, str):
            return v
        if isinstance(v, list):
            return v
        return str(v)


class ChatMessageResponse(BaseModel):
    """A message in the chat response (assistant message)."""

    role: Literal["assistant"] = "assistant"
    content: Optional[str] = Field(
        default=None,
        description="Text content of the response",
    )
    tool_calls: Optional[List[ToolCall]] = Field(
        default=None,
        description="Tool calls made by the assistant",
    )
    refusal: Optional[str] = Field(
        default=None,
        description="Refusal message if the model refused to respond",
    )


# ============================================================================
# Chat Completion Request
# ============================================================================


class ChatCompletionRequest(BaseModel):
    """Request body for chat completion endpoint."""

    model: str = Field(
        ...,
        description="Model identifier (filename or path to GGUF file)",
    )
    messages: List[ChatMessage] = Field(
        ...,
        min_length=1,
        description="List of messages in the conversation",
    )
    
    # Generation parameters
    max_tokens: Optional[int] = Field(
        default=None,
        ge=1,
        le=131072,
        description="Maximum tokens to generate",
    )
    temperature: Optional[float] = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature",
    )
    top_p: Optional[float] = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling probability",
    )
    top_k: Optional[int] = Field(
        default=None,
        ge=0,
        description="Top-k sampling",
    )
    frequency_penalty: Optional[float] = Field(
        default=0.0,
        ge=-2.0,
        le=2.0,
        description="Frequency penalty",
    )
    presence_penalty: Optional[float] = Field(
        default=0.0,
        ge=-2.0,
        le=2.0,
        description="Presence penalty",
    )
    repetition_penalty: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Repetition penalty (llama-cpp specific)",
    )
    stop: Optional[Union[str, List[str]]] = Field(
        default=None,
        description="Stop sequences",
    )
    seed: Optional[int] = Field(
        default=None,
        description="Random seed for reproducibility",
    )
    
    # Streaming
    stream: bool = Field(
        default=False,
        description="Whether to stream the response",
    )
    stream_options: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Options for streaming (e.g., include_usage)",
    )
    
    # Tool calling
    tools: Optional[List[Tool]] = Field(
        default=None,
        description="List of tools the model can use",
    )
    tool_choice: Optional[ToolChoice] = Field(
        default=None,
        description="How the model should use tools",
    )
    parallel_tool_calls: Optional[bool] = Field(
        default=True,
        description="Whether to allow parallel tool calls",
    )
    
    # Response format
    response_format: Optional[ResponseFormat] = Field(
        default=None,
        description="Response format specification",
    )
    
    # Additional options
    n: int = Field(
        default=1,
        ge=1,
        le=1,  # Only support n=1 for local models
        description="Number of completions (only 1 supported)",
    )
    user: Optional[str] = Field(
        default=None,
        description="User identifier for tracking",
    )

    @field_validator("stop", mode="before")
    @classmethod
    def normalize_stop(cls, v):
        """Normalize stop sequences to list."""
        if v is None:
            return None
        if isinstance(v, str):
            return [v]
        return v


# ============================================================================
# Chat Completion Response
# ============================================================================


class Usage(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int = Field(..., ge=0, description="Tokens in the prompt")
    completion_tokens: int = Field(..., ge=0, description="Tokens in the completion")
    total_tokens: int = Field(..., ge=0, description="Total tokens used")


class Choice(BaseModel):
    """A completion choice."""

    index: int = Field(default=0, ge=0, description="Index of this choice")
    message: ChatMessageResponse = Field(..., description="The generated message")
    finish_reason: Optional[FinishReason] = Field(
        default=None,
        description="Reason generation stopped",
    )
    logprobs: Optional[Any] = Field(
        default=None,
        description="Log probabilities (not implemented)",
    )


class ChatCompletionResponse(BaseModel):
    """Non-streaming chat completion response."""

    id: str = Field(
        default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex}",
        description="Unique completion identifier",
    )
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(
        default_factory=lambda: int(time.time()),
        description="Unix timestamp of creation",
    )
    model: str = Field(..., description="Model used for completion")
    choices: List[Choice] = Field(..., description="List of completion choices")
    usage: Optional[Usage] = Field(
        default=None,
        description="Token usage statistics",
    )
    system_fingerprint: Optional[str] = Field(
        default=None,
        description="System fingerprint",
    )


# ============================================================================
# Streaming Response (SSE chunks)
# ============================================================================


class DeltaContent(BaseModel):
    """Delta content for streaming responses."""

    role: Optional[Literal["assistant"]] = Field(
        default=None,
        description="Role (only in first chunk)",
    )
    content: Optional[str] = Field(
        default=None,
        description="Content delta",
    )
    tool_calls: Optional[List[ToolCall]] = Field(
        default=None,
        description="Tool call deltas",
    )
    refusal: Optional[str] = Field(
        default=None,
        description="Refusal delta",
    )


class StreamChoice(BaseModel):
    """A streaming choice."""

    index: int = Field(default=0, ge=0, description="Index of this choice")
    delta: DeltaContent = Field(..., description="Content delta")
    finish_reason: Optional[FinishReason] = Field(
        default=None,
        description="Reason generation stopped (only in final chunk)",
    )
    logprobs: Optional[Any] = Field(
        default=None,
        description="Log probabilities (not implemented)",
    )


class ChatCompletionChunk(BaseModel):
    """Streaming chat completion chunk."""

    id: str = Field(..., description="Completion identifier (same across chunks)")
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int = Field(..., description="Unix timestamp of creation")
    model: str = Field(..., description="Model used for completion")
    choices: List[StreamChoice] = Field(..., description="List of choice deltas")
    usage: Optional[Usage] = Field(
        default=None,
        description="Token usage (only if stream_options.include_usage is true)",
    )
    system_fingerprint: Optional[str] = Field(
        default=None,
        description="System fingerprint",
    )


# ============================================================================
# Model List Response (OpenAI /v1/models compatible)
# ============================================================================


class ModelObject(BaseModel):
    """Model object in the models list."""

    id: str = Field(..., description="Model identifier")
    object: Literal["model"] = "model"
    created: int = Field(..., description="Unix timestamp of creation")
    owned_by: str = Field(default="local", description="Model owner")


class ModelListResponse(BaseModel):
    """Response for /v1/models endpoint."""

    object: Literal["list"] = "list"
    data: List[ModelObject] = Field(..., description="List of available models")


class ModelDetailResponse(ModelObject):
    """Detailed model information."""

    path: str = Field(..., description="Path to the model file")
    size_bytes: int = Field(..., ge=0, description="Model file size in bytes")
    loaded: bool = Field(default=False, description="Whether model is loaded in memory")
