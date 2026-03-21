from pydantic import BaseModel, Field


class DownloadRequest(BaseModel):
    """Request to download a model."""

    model_id: str = Field(min_length=1, description="HuggingFace repo ID, e.g., 'unsloth/Qwen3.5-0.8B-GGUF'")
    quantization: str = Field(default="Q4_K_M", description="Quantization type, e.g., 'Q4_K_M'")


class ModelRecord(BaseModel):
    """Model download record (in-memory state)."""

    id: str
    model_id: str
    name: str
    quantization: str
    status: str = Field(description="Status: pending | downloading | completed | failed | corrupted")
    progress: int = Field(ge=0, le=100, description="Progress percentage (0 to 100)")
    path: str | None = Field(None, description="Local path to downloaded .gguf file")
    error: str | None = Field(None, description="Error message if status is failed")
