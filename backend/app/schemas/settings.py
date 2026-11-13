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


class RlmSettings(BaseModel):
    enabled: bool = True
    mode: Literal["auto", "always", "never"] = "auto"
    max_depth: int = Field(default=2, ge=0, le=4)
    snippet_tokens: int = Field(default=2048, ge=512, le=8192)
    max_subcalls: int = Field(default=32, ge=1, le=256)
    subcall_concurrency: int = Field(default=2, ge=1, le=8)
    auto_threshold_ratio: float = Field(default=0.6, ge=0.1, le=1.0)
    prompt_reserve_tokens: int = Field(default=2048, ge=512, le=8192)


class RlmSettingsResponse(RlmSettings):
    effective_reach_tokens: int
    fan_out: int
    bounded_by_budget: bool


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
