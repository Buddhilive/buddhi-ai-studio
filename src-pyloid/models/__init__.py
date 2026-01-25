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

from .responses_schemas import (
    # Enums
    ResponseStatus,
    OutputItemStatus,
    ReasoningEffort,
    # Input items
    InputTextItem,
    InputImageItem,
    InputAudioItem,
    InputFileItem,
    EasyInputMessage,
    FunctionCallOutput,
    InputItem,
    # Output items
    OutputTextContent,
    OutputMessageItem,
    ReasoningItem,
    ReasoningSummaryItem,
    FunctionCallItem,
    OutputItem,
    # Tools
    FunctionToolDefinition,
    ToolDefinition,
    # Text format
    JsonSchemaFormat,
    JsonObjectFormat,
    TextFormat,
    # Config
    ReasoningConfig,
    # Usage
    ResponseUsage,
    # Request/Response
    ResponsesRequest,
    ResponsesResponse,
    # Streaming events
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
    StreamingEvent,
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
    # Responses API
    "ResponseStatus",
    "OutputItemStatus",
    "ReasoningEffort",
    "InputTextItem",
    "InputImageItem",
    "InputAudioItem",
    "InputFileItem",
    "EasyInputMessage",
    "FunctionCallOutput",
    "InputItem",
    "OutputTextContent",
    "OutputMessageItem",
    "ReasoningItem",
    "ReasoningSummaryItem",
    "FunctionCallItem",
    "OutputItem",
    "FunctionToolDefinition",
    "ToolDefinition",
    "JsonSchemaFormat",
    "JsonObjectFormat",
    "TextFormat",
    "ReasoningConfig",
    "ResponseUsage",
    "ResponsesRequest",
    "ResponsesResponse",
    "ResponseCreatedEvent",
    "ResponseInProgressEvent",
    "OutputItemAddedEvent",
    "OutputItemDoneEvent",
    "ContentPartAddedEvent",
    "ContentPartDoneEvent",
    "OutputTextDeltaEvent",
    "OutputTextDoneEvent",
    "FunctionCallArgumentsDeltaEvent",
    "FunctionCallArgumentsDoneEvent",
    "ResponseCompletedEvent",
    "ResponseFailedEvent",
    "StreamingEvent",
]
