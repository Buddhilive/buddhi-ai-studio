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


class EgmSettings(BaseModel):
    enabled: bool = False
    max_review_rounds: int = Field(default=3, ge=1, le=10)
    goldfish_concurrency: int = Field(default=1, ge=1, le=4)
    reviewer_timeout_s: int = Field(default=90, ge=15, le=600)
    context_budget_tokens: int = Field(default=4096, ge=1024, le=32768)
    enable_brainstorm: bool = False
    default_skill_mode: Literal["standard", "brainstorm", "bootstrap", "drift_report"] = "standard"


class HarnessSettings(BaseModel):
    enabled: bool = True
    auto_calibrate_uncalibrated: bool = False
    auto_calibrate_on_retry: bool = True
    max_calibration_rounds: int = Field(default=1, ge=1, le=3)
    max_candidates: int = Field(default=2, ge=1, le=3)
    probe_concurrency: int = Field(default=1, ge=1, le=2)
    probe_max_steps: int = Field(default=6, ge=2, le=15)
    probe_timeout_s: int = Field(default=60, ge=15, le=300)
    experience_max_entries: int = Field(default=50, ge=5, le=200)
