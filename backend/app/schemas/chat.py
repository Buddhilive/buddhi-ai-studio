import time
import uuid
from typing import Literal, Union

from pydantic import BaseModel, Field, field_validator

Role = Literal["system", "user", "assistant"]


class TextContentPart(BaseModel):
    type: Literal["text"]
    text: str


class ImageUrl(BaseModel):
    url: str


class ImageContentPart(BaseModel):
    type: Literal["image_url"]
    image_url: ImageUrl


ContentPart = Union[TextContentPart, ImageContentPart]


class ChatMessage(BaseModel):
    role: Role
    content: str | list[ContentPart]


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: float = 1.0
    top_p: float = 1.0
    max_tokens: int | None = None
    stream: bool = False
    stop: str | list[str] | None = None
    n: int = 1
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    user: str | None = None

    @field_validator("messages")
    @classmethod
    def messages_must_not_be_empty(cls, value: list[ChatMessage]) -> list[ChatMessage]:
        if not value:
            raise ValueError("messages must not be empty")
        return value

    @field_validator("n")
    @classmethod
    def n_must_be_one(cls, value: int) -> int:
        if value != 1:
            raise ValueError("only n=1 is supported")
        return value


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: Literal["stop", "length"] = "stop"


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex}")
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[ChatCompletionChoice]
    usage: Usage


class ChatCompletionChunkDelta(BaseModel):
    role: Role | None = None
    content: str | None = None


class ChatCompletionChunkChoice(BaseModel):
    index: int = 0
    delta: ChatCompletionChunkDelta
    finish_reason: Literal["stop", "length"] | None = None


class ChatCompletionChunk(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex}")
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[ChatCompletionChunkChoice]


class OpenAIError(BaseModel):
    message: str
    type: str
    param: str | None = None
    code: str | None = None


class OpenAIErrorResponse(BaseModel):
    error: OpenAIError
