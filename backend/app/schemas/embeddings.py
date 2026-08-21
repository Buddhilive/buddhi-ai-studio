from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator


class EmbeddingRequest(BaseModel):
    model: str
    input: str | list[str]
    encoding_format: Literal["float", "base64"] = "float"
    dimensions: int | None = None
    user: str | None = None

    @field_validator("input")
    @classmethod
    def input_must_not_be_empty(cls, value: str | list[str]) -> str | list[str]:
        if isinstance(value, str):
            if not value:
                raise ValueError("input must not be empty")
            return value
        if not value:
            raise ValueError("input must not be empty")
        if any(not item for item in value):
            raise ValueError("input must not contain empty strings")
        return value

    @field_validator("dimensions")
    @classmethod
    def dimensions_must_be_positive(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("dimensions must be a positive integer")
        return value


class EmbeddingObject(BaseModel):
    object: Literal["embedding"] = "embedding"
    embedding: list[float] | str
    index: int


class EmbeddingUsage(BaseModel):
    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    object: Literal["list"] = "list"
    data: list[EmbeddingObject]
    model: str
    usage: EmbeddingUsage
