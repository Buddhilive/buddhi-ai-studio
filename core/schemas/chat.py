"""OpenAI Chat Completion API compatible schemas."""

from enum import Enum
from typing import Any, Annotated, Union, Literal
from pydantic import BaseModel, Field


class Role(str, Enum):
    """Message role enum."""
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class FinishReason(str, Enum):
    """Completion finish reason."""
    stop = "stop"
    length = "length"
    tool_calls = "tool_calls"
    content_filter = "content_filter"


# ===== Content Parts =====

class ImageURL(BaseModel):
    """Image URL for vision inputs."""
    url: str
    detail: str = "auto"  # "low" | "high" | "auto"


class TextContentPart(BaseModel):
    """Text content in a message."""
    type: Literal["text"]
    text: str


class ImageContentPart(BaseModel):
    """Image content in a message (vision)."""
    type: Literal["image_url"]
    image_url: ImageURL


ContentPart = Annotated[
    Union[TextContentPart, ImageContentPart],
    Field(discriminator="type")
]


# ===== Tool/Function Calling =====

class FunctionDefinition(BaseModel):
    """Function definition for tool calling."""
    name: str
    description: str | None = None
    parameters: dict[str, Any] | None = None  # JSON Schema object


class Tool(BaseModel):
    """Tool definition."""
    type: Literal["function"] = "function"
    function: FunctionDefinition


class FunctionCall(BaseModel):
    """Function call in a tool_call."""
    name: str
    arguments: str  # JSON string


class ToolCall(BaseModel):
    """Tool call from assistant."""
    id: str
    type: Literal["function"] = "function"
    function: FunctionCall


# ===== Messages =====

class SystemMessage(BaseModel):
    """System message."""
    role: Literal["system"]
    content: str
    name: str | None = None


class UserMessage(BaseModel):
    """User message."""
    role: Literal["user"]
    content: str | list[ContentPart]
    name: str | None = None


class AssistantMessage(BaseModel):
    """Assistant message."""
    role: Literal["assistant"]
    content: str | None = None
    name: str | None = None
    tool_calls: list[ToolCall] | None = None


class ToolMessage(BaseModel):
    """Tool result message."""
    role: Literal["tool"]
    content: str
    tool_call_id: str


Message = Annotated[
    Union[SystemMessage, UserMessage, AssistantMessage, ToolMessage],
    Field(discriminator="role")
]


# ===== Response Format =====

class ResponseFormatText(BaseModel):
    """Text response format (default)."""
    type: Literal["text"]


class ResponseFormatJSON(BaseModel):
    """JSON response format."""
    type: Literal["json_object"]


class ResponseFormatJSONSchema(BaseModel):
    """JSON Schema response format."""
    type: Literal["json_schema"]
    json_schema: dict[str, Any]  # {"name": ..., "schema": {...}, "strict": bool}


ResponseFormat = Union[ResponseFormatText, ResponseFormatJSON, ResponseFormatJSONSchema]


# ===== Request =====

class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""
    model: str
    messages: list[Message]
    temperature: float | None = 0.7
    top_p: float | None = 1.0
    top_k: int | None = 40
    n: int | None = 1
    max_tokens: int | None = None
    stop: str | list[str] | None = None
    stream: bool = False
    presence_penalty: float | None = 0.0
    frequency_penalty: float | None = 0.0
    tools: list[Tool] | None = None
    tool_choice: str | dict[str, Any] | None = None  # "none"|"auto"|"required"|ToolChoice
    response_format: ResponseFormat | None = None
    seed: int | None = None
    logprobs: bool | None = None
    top_logprobs: int | None = None
    user: str | None = None


# ===== Response =====

class UsageInfo(BaseModel):
    """Token usage information."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionMessage(BaseModel):
    """Message in completion response."""
    role: Role
    content: str | None = None
    tool_calls: list[ToolCall] | None = None


class ChatCompletionChoice(BaseModel):
    """Choice in completion response."""
    index: int
    message: ChatCompletionMessage
    finish_reason: FinishReason | None = None
    logprobs: dict[str, Any] | None = None


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: UsageInfo
    system_fingerprint: str | None = None


# ===== Streaming =====

class ChatCompletionDelta(BaseModel):
    """Delta in streaming chunk."""
    role: Role | None = None
    content: str | None = None
    tool_calls: list[ToolCall] | None = None


class ChatCompletionStreamChoice(BaseModel):
    """Choice in streaming chunk."""
    index: int
    delta: ChatCompletionDelta
    finish_reason: FinishReason | None = None


class ChatCompletionStreamChunk(BaseModel):
    """OpenAI-compatible streaming chunk."""
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChatCompletionStreamChoice]
