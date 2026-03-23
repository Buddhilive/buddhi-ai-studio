"""OpenAI Embeddings API compatible schemas."""

from typing import Literal, Union
from pydantic import BaseModel, Field, field_validator


class EmbeddingRequest(BaseModel):
    """OpenAI-compatible embedding request."""
    input: Union[str, list[str], list[int], list[list[int]]]
    model: str
    encoding_format: Literal["float", "base64"] = "float"
    dimensions: int | None = Field(default=None, ge=1)
    user: str | None = None

    @field_validator("input")
    @classmethod
    def validate_input(cls, v):
        """Validate input is not empty."""
        if isinstance(v, str):
            if not v or not v.strip():
                raise ValueError("Input string cannot be empty")
        elif isinstance(v, list):
            if not v:
                raise ValueError("Input list cannot be empty")
            # Check for empty strings in list
            if isinstance(v[0], str):
                for item in v:
                    if not isinstance(item, str) or not item.strip():
                        raise ValueError("Input strings cannot be empty")
        return v


class EmbeddingObject(BaseModel):
    """Embedding result object."""
    index: int
    object: Literal["embedding"] = "embedding"
    embedding: list[float] | str  # list of floats or base64-encoded string


class EmbeddingUsage(BaseModel):
    """Token usage information."""
    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    """OpenAI-compatible embedding response."""
    object: Literal["list"] = "list"
    data: list[EmbeddingObject]
    model: str
    usage: EmbeddingUsage
