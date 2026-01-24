"""Data models package for model download system."""

from .schemas import (
    DownloadRequest,
    DownloadResponse,
    DownloadState,
    ModelInfo,
    ProblemDetail,
    ProgressUpdate,
    RepoType,
)

from .chat_schemas import (
    # Enums
    Role,
    FinishReason,
    ResponseFormatType,
    # Content parts (multimodal)
    TextContentPart,
    ImageUrl,
    ImageContentPart,
    AudioInputData,
    AudioContentPart,
    ContentPart,
    # Tool/Function calling
    FunctionParameters,
    FunctionDefinition,
    Tool,
    ToolChoice,
    ToolChoiceObject,
    ToolChoiceFunction,
    FunctionCall,
    ToolCall,
    # Response format
    JsonSchemaDefinition,
    ResponseFormat,
    # Messages
    ChatMessage,
    ChatMessageResponse,
    # Request/Response
    ChatCompletionRequest,
    Usage,
    Choice,
    ChatCompletionResponse,
    # Streaming
    DeltaContent,
    StreamChoice,
    ChatCompletionChunk,
    # Model endpoints
    ModelObject,
    ModelListResponse,
    ModelDetailResponse,
)

__all__ = [
    # Existing schemas
    "DownloadRequest",
    "DownloadResponse",
    "DownloadState",
    "ModelInfo",
    "ProblemDetail",
    "ProgressUpdate",
    "RepoType",
    # Enums
    "Role",
    "FinishReason",
    "ResponseFormatType",
    # Content parts
    "TextContentPart",
    "ImageUrl",
    "ImageContentPart",
    "AudioInputData",
    "AudioContentPart",
    "ContentPart",
    # Tool/Function calling
    "FunctionParameters",
    "FunctionDefinition",
    "Tool",
    "ToolChoice",
    "ToolChoiceObject",
    "ToolChoiceFunction",
    "FunctionCall",
    "ToolCall",
    # Response format
    "JsonSchemaDefinition",
    "ResponseFormat",
    # Messages
    "ChatMessage",
    "ChatMessageResponse",
    # Request/Response
    "ChatCompletionRequest",
    "Usage",
    "Choice",
    "ChatCompletionResponse",
    # Streaming
    "DeltaContent",
    "StreamChoice",
    "ChatCompletionChunk",
    # Model endpoints
    "ModelObject",
    "ModelListResponse",
    "ModelDetailResponse",
]
