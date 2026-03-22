from pydantic import BaseModel, Field


class DownloadRequest(BaseModel):
    """Request to pull an Ollama model."""

    model: str = Field(min_length=1, description="Ollama model name, e.g. 'qwen3.5:3b'")


class ModelRecord(BaseModel):
    """Model record returned to the frontend."""

    id: str
    model_id: str
    name: str
    quantization: str
    status: str = Field(description="Status: pending | pulling | completed | failed")
    progress: int = Field(ge=0, le=100, description="Progress percentage (0 to 100)")
    path: str | None = Field(None, description="Always null for Ollama-managed models")
    error: str | None = Field(None, description="Error message if status is failed")
