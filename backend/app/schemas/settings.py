from typing import Literal

from pydantic import BaseModel, Field, field_validator


class HfTokenRequest(BaseModel):
    token: str

    @field_validator("token")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Token must not be empty")
        return trimmed


class HfTokenStatus(BaseModel):
    configured: bool


class SupportedBackend(BaseModel):
    id: str
    name: str
    supported: bool
    recommended: bool = False
    reason: str | None = None


class InferenceSettings(BaseModel):
    litert_backend: Literal["cpu", "gpu", "npu"] = "cpu"
    max_num_token: int = Field(default=16384, ge=512, le=131072)


class SystemResourceRecommendation(BaseModel):
    total_memory_bytes: int
    available_memory_bytes: int
    cpu_count: int
    gpu_name: str | None = None
    gpu_total_memory_bytes: int | None = None
    gpu_free_memory_bytes: int | None = None
    supported_backends: list[SupportedBackend]
    recommended_backend: Literal["cpu", "gpu", "npu"] = "cpu"
    recommended_max_num_tokens: int
    max_viable_tokens: int
    model_assumed: str = "Gemma 4 E4B"
    reasoning: str
