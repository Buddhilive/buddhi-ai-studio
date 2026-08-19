from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class DownloadStatus(str, Enum):
    IDLE = "idle"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class ModelDownloadState(BaseModel):
    status: DownloadStatus = DownloadStatus.IDLE
    repo_id: str
    filename: str
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    percentage: float = 0.0
    error: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ModelAvailability(BaseModel):
    available: bool
    path: str | None = None
    size_bytes: int | None = None
