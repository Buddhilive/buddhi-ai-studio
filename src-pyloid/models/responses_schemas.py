"""OpenAI Responses API compatible Pydantic models.

This module implements the newer OpenAI Responses API format which combines
features from Chat Completions and Assistants APIs.
"""

import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Enums
# ============================================================================


class ResponseStatus(str, Enum):
    """Status of a response."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OutputItemStatus(str, Enum):
    """Status of an output item."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ReasoningEffort(str, Enum):
    """Reasoning effort level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ============================================================================
# Input Items
# ============================================================================


class InputTextItem(BaseModel):
    """Text input item."""

    type: Literal["input_text"] = "input_text"
    text: str = Field(..., description="The text content")


class InputImageItem(BaseModel):
    """Image input item."""

    type: Literal["input_image"] = "input_image"
    image_url: Optional[str] = Field(
        default=None,
        description="URL of the image or base64 data URI",
    )
    file_id: Optional[str] = Field(
        default=None,
        description="ID of a previously uploaded file",
    )
    detail: Literal["auto", "low", "high"] = Field(
        default="auto",
        description="Image detail level",
    )


class InputAudioItem(BaseModel):
    """Audio input item."""

    type: Literal["input_audio"] = "input_audio"
    data: str = Field(..., description="Base64 encoded audio data")
    format: Literal["wav", "mp3", "flac", "webm"] = Field(
        ...,
        description="Audio format",
    )


class InputFileItem(BaseModel):
    """File input item."""

    type: Literal["input_file"] = "input_file"
    file_id: Optional[str] = Field(
        default=None,
        description="ID of a previously uploaded file",
    )
    file_url: Optional[str] = Field(
        default=None,
        description="URL of the file",
    )
    file_data: Optional[str] = Field(
        default=None,
        description="Base64 encoded file content",
    )
    filename: Optional[str] = Field(
        default=None,
        description="Name of the file",
    )


class EasyInputMessage(BaseModel):
    """Message-style input (compatibility with chat format)."""

    role: Literal["user", "assistant", "system"] = Field(
        ...,
        description="Role of the message author",
    )
    content: str = Field(..., description="Message content")


class FunctionCallOutput(BaseModel):
    """Function call output for tool result input."""

    type: Literal["function_call_output"] = "function_call_output"
    call_id: str = Field(..., description="ID of the function call being responded to")
    output: str = Field(..., description="Output of the function call (JSON string)")


# Union type for all input items
InputItem = Union[
    InputTextItem,
    InputImageItem,
    InputAudioItem,
    InputFileItem,
    EasyInputMessage,
    FunctionCallOutput,
]


# ============================================================================
# Output Items
# ============================================================================


class OutputTextContent(BaseModel):
    """Text content in an output message."""

    type: Literal["output_text"] = "output_text"
    text: str = Field(..., description="The text content")
    annotations: List[Any] = Field(
        default_factory=list,
        description="Annotations for citations, file references, etc.",
    )


class OutputMessageItem(BaseModel):
    """Message output item containing text content."""

    type: Literal["message"] = "message"
    id: str = Field(
        default_factory=lambda: f"msg_{uuid.uuid4().hex[:24]}",
        description="Unique identifier for this message",
    )
    role: Literal["assistant"] = "assistant"
    status: OutputItemStatus = Field(
        default=OutputItemStatus.COMPLETED,
        description="Status of the message",
    )
    content: List[OutputTextContent] = Field(
        default_factory=list,
        description="Content parts of the message",
    )


class ReasoningSummaryItem(BaseModel):
    """A summary item in reasoning output."""

    type: Literal["summary_text"] = "summary_text"
    text: str = Field(..., description="The reasoning summary text")


class ReasoningItem(BaseModel):
    """Reasoning output item (for models that support thinking/reasoning)."""

    type: Literal["reasoning"] = "reasoning"
    id: str = Field(
        default_factory=lambda: f"rs_{uuid.uuid4().hex[:24]}",
        description="Unique identifier for this reasoning item",
    )
    summary: List[ReasoningSummaryItem] = Field(
        default_factory=list,
        description="Summary of the reasoning process",
    )


class FunctionCallItem(BaseModel):
    """Function call output item."""

    type: Literal["function_call"] = "function_call"
    id: str = Field(
        default_factory=lambda: f"fc_{uuid.uuid4().hex[:24]}",
        description="Unique identifier for this function call",
    )
    call_id: str = Field(
        default_factory=lambda: f"call_{uuid.uuid4().hex[:24]}",
        description="ID to reference this call in function_call_output",
    )
    name: str = Field(..., description="Name of the function to call")
    arguments: str = Field(..., description="JSON string of function arguments")
    status: OutputItemStatus = Field(
        default=OutputItemStatus.COMPLETED,
        description="Status of the function call",
    )


# Union type for all output items
OutputItem = Union[OutputMessageItem, ReasoningItem, FunctionCallItem]


# ============================================================================
# Tool Definitions (Responses API format)
# ============================================================================


class FunctionToolDefinition(BaseModel):
    """Function tool definition."""

    type: Literal["function"] = "function"
    name: str = Field(..., min_length=1, max_length=64, description="Function name")
    description: Optional[str] = Field(
        default=None,
        description="Description of what the function does",
    )
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="JSON Schema for function parameters",
    )
    strict: Optional[bool] = Field(
        default=None,
        description="Whether to enforce strict schema adherence",
    )


# Union for all tool types (can be extended for web_search, file_search, etc.)
ToolDefinition = Union[FunctionToolDefinition]


# ============================================================================
# Text Format Configuration (Structured Output)
# ============================================================================


class JsonSchemaFormat(BaseModel):
    """JSON Schema format for structured output."""

    type: Literal["json_schema"] = "json_schema"
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


class JsonObjectFormat(BaseModel):
    """JSON object format (any valid JSON)."""

    type: Literal["json_object"] = "json_object"


class TextFormat(BaseModel):
    """Text format configuration for structured output."""

    format: Union[Literal["text"], JsonObjectFormat, JsonSchemaFormat] = Field(
        default="text",
        description="Output format specification",
    )


# ============================================================================
# Reasoning Configuration
# ============================================================================


class ReasoningConfig(BaseModel):
    """Configuration for reasoning/thinking."""

    effort: ReasoningEffort = Field(
        default=ReasoningEffort.MEDIUM,
        description="Reasoning effort level",
    )
    summary: Optional[Literal["auto", "concise", "detailed"]] = Field(
        default=None,
        description="Summary style for reasoning",
    )


# ============================================================================
# Usage Statistics
# ============================================================================


class ResponseUsage(BaseModel):
    """Token and request usage statistics."""

    input_tokens: int = Field(..., ge=0, description="Tokens in the input")
    output_tokens: int = Field(..., ge=0, description="Tokens in the output")
    total_tokens: int = Field(..., ge=0, description="Total tokens used")
    reasoning_tokens: Optional[int] = Field(
        default=None,
        ge=0,
        description="Tokens used for reasoning (if applicable)",
    )


# ============================================================================
# Request Model
# ============================================================================


class ResponsesRequest(BaseModel):
    """Request body for the Responses API endpoint."""

    model: str = Field(
        ...,
        description="Model identifier (filename or path to GGUF file)",
    )

    # Input can be a simple string or array of input items
    input: Union[str, List[InputItem]] = Field(
        ...,
        description="Input content (text or array of input items)",
    )

    # Optional system instructions
    instructions: Optional[str] = Field(
        default=None,
        description="System instructions for the model",
    )

    # Conversation continuity
    previous_response_id: Optional[str] = Field(
        default=None,
        description="ID of previous response to continue from",
    )

    # Generation parameters
    max_output_tokens: Optional[int] = Field(
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
        description="Top-k sampling (llama-cpp specific)",
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

    # Tool calling
    tools: Optional[List[ToolDefinition]] = Field(
        default=None,
        description="List of tools the model can use",
    )
    tool_choice: Optional[Union[Literal["none", "auto", "required"], Dict[str, Any]]] = Field(
        default=None,
        description="How the model should use tools",
    )
    parallel_tool_calls: Optional[bool] = Field(
        default=True,
        description="Whether to allow parallel tool calls",
    )

    # Structured output
    text: Optional[TextFormat] = Field(
        default=None,
        description="Text format configuration for structured output",
    )

    # Reasoning
    reasoning: Optional[ReasoningConfig] = Field(
        default=None,
        description="Reasoning configuration",
    )

    # Additional options
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

    @field_validator("input", mode="before")
    @classmethod
    def normalize_input(cls, v):
        """Handle various input formats."""
        if v is None:
            raise ValueError("Input is required")
        return v


# ============================================================================
# Response Model
# ============================================================================


class ResponsesResponse(BaseModel):
    """Response from the Responses API endpoint."""

    id: str = Field(
        default_factory=lambda: f"resp_{uuid.uuid4().hex}",
        description="Unique response identifier",
    )
    object: Literal["response"] = "response"
    created_at: int = Field(
        default_factory=lambda: int(time.time()),
        description="Unix timestamp of creation",
    )
    model: str = Field(..., description="Model used for the response")
    status: ResponseStatus = Field(
        default=ResponseStatus.COMPLETED,
        description="Status of the response",
    )
    output: List[OutputItem] = Field(
        default_factory=list,
        description="Output items from the model",
    )
    usage: Optional[ResponseUsage] = Field(
        default=None,
        description="Token usage statistics",
    )
    error: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Error information if status is failed",
    )


# ============================================================================
# Streaming Events
# ============================================================================


class ResponseCreatedEvent(BaseModel):
    """Event emitted when a response is created."""

    type: Literal["response.created"] = "response.created"
    response: ResponsesResponse


class ResponseInProgressEvent(BaseModel):
    """Event emitted when response generation is in progress."""

    type: Literal["response.in_progress"] = "response.in_progress"
    response: ResponsesResponse


class OutputItemAddedEvent(BaseModel):
    """Event emitted when an output item is added."""

    type: Literal["response.output_item.added"] = "response.output_item.added"
    output_index: int
    item: OutputItem


class OutputItemDoneEvent(BaseModel):
    """Event emitted when an output item is complete."""

    type: Literal["response.output_item.done"] = "response.output_item.done"
    output_index: int
    item: OutputItem


class ContentPartAddedEvent(BaseModel):
    """Event emitted when a content part is added to a message."""

    type: Literal["response.content_part.added"] = "response.content_part.added"
    item_id: str
    output_index: int
    content_index: int
    part: OutputTextContent


class ContentPartDoneEvent(BaseModel):
    """Event emitted when a content part is complete."""

    type: Literal["response.content_part.done"] = "response.content_part.done"
    item_id: str
    output_index: int
    content_index: int
    part: OutputTextContent


class OutputTextDeltaEvent(BaseModel):
    """Event emitted for streaming text deltas."""

    type: Literal["response.output_text.delta"] = "response.output_text.delta"
    item_id: str
    output_index: int
    content_index: int
    delta: str


class OutputTextDoneEvent(BaseModel):
    """Event emitted when text output is complete."""

    type: Literal["response.output_text.done"] = "response.output_text.done"
    item_id: str
    output_index: int
    content_index: int
    text: str


class FunctionCallArgumentsDeltaEvent(BaseModel):
    """Event emitted for streaming function call arguments."""

    type: Literal["response.function_call_arguments.delta"] = "response.function_call_arguments.delta"
    item_id: str
    output_index: int
    call_id: str
    delta: str


class FunctionCallArgumentsDoneEvent(BaseModel):
    """Event emitted when function call arguments are complete."""

    type: Literal["response.function_call_arguments.done"] = "response.function_call_arguments.done"
    item_id: str
    output_index: int
    call_id: str
    arguments: str


class ResponseCompletedEvent(BaseModel):
    """Event emitted when response generation is complete."""

    type: Literal["response.completed"] = "response.completed"
    response: ResponsesResponse


class ResponseFailedEvent(BaseModel):
    """Event emitted when response generation fails."""

    type: Literal["response.failed"] = "response.failed"
    response: ResponsesResponse


# Union of all streaming events
StreamingEvent = Union[
    ResponseCreatedEvent,
    ResponseInProgressEvent,
    OutputItemAddedEvent,
    OutputItemDoneEvent,
    ContentPartAddedEvent,
    ContentPartDoneEvent,
    OutputTextDeltaEvent,
    OutputTextDoneEvent,
    FunctionCallArgumentsDeltaEvent,
    FunctionCallArgumentsDoneEvent,
    ResponseCompletedEvent,
    ResponseFailedEvent,
]
