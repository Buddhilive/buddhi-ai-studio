from datetime import datetime
from pydantic import BaseModel, Field


class DownloadRequest(BaseModel):
    """Request body for starting a model download."""

    model_id: str = Field(..., min_length=1, description="HuggingFace model ID (e.g., 'mistralai/Mistral-7B-v0.1')")
    quantization: str | None = Field(None, description="Quantization method (e.g., 'Q4_K_M')")


class DownloadRecord(BaseModel):
    """Response body for a download record."""

    id: int
    model_id: str
    quantization: str | None
    status: str = Field(description="Status: pending | downloading | completed | failed | cancelled")
    progress: float = Field(ge=0, le=100, description="Progress percentage (0.0 to 100.0)")
    local_path: str | None = Field(None, description="Local path to downloaded model")
    error_msg: str | None = Field(None, description="Error message if status is failed")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProgressEvent(BaseModel):
    """SSE progress event payload."""

    download_id: int
    status: str = Field(description="Current status: downloading | completed | failed | cancelled")
    progress: float = Field(ge=0, le=100)
    message: str | None = Field(None, description="Optional progress message")
