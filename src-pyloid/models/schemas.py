"""Pydantic models for request/response validation and data structures."""

import re
from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class DownloadState(str, Enum):
    """State of a model download operation."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RepoType(str, Enum):
    """Type of HuggingFace repository."""

    MODEL = "model"
    DATASET = "dataset"


# ============================================================================
# Request Models
# ============================================================================


class DownloadRequest(BaseModel):
    """Request to download a GGUF model from HuggingFace.
    
    Attributes:
        repo_id: HuggingFace repository ID (e.g., 'TheBloke/Llama-2-7B-GGUF')
        filename: Name of the GGUF file to download
        repo_type: Type of repository (model or dataset)
        token: Optional HuggingFace API token for private repos
    """

    repo_id: str = Field(
        ...,
        min_length=1,
        description="HuggingFace repository ID in format 'username/repo-name'",
        examples=["TheBloke/Llama-2-7B-GGUF"],
    )
    filename: str = Field(
        ...,
        min_length=1,
        description="GGUF model filename",
        examples=["llama-2-7b.Q4_K_M.gguf"],
    )
    repo_type: Literal["model", "dataset"] = Field(
        default="model",
        description="Type of repository",
    )
    token: Optional[str] = Field(
        default=None,
        min_length=20,
        description="HuggingFace API token for private repositories",
    )

    @field_validator("repo_id")
    @classmethod
    def validate_repo_id(cls, v: str) -> str:
        """Validate HuggingFace repository ID format.
        
        Args:
            v: Repository ID to validate
            
        Returns:
            Validated repository ID
            
        Raises:
            ValueError: If repo_id format is invalid
        """
        # Validate format: username/repo-name
        pattern = r"^[\w-]+/[\w.-]+$"
        if not re.match(pattern, v):
            raise ValueError(
                "repo_id must be in format 'username/repo-name' "
                "(alphanumeric, hyphens, underscores, and dots allowed)"
            )
        return v

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate and sanitize filename.
        
        Args:
            v: Filename to validate
            
        Returns:
            Validated filename
            
        Raises:
            ValueError: If filename is invalid or contains path traversal
        """
        # Check for path traversal attempts
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("Filename must not contain path separators or '..'")

        # Ensure .gguf extension
        if not v.lower().endswith(".gguf"):
            raise ValueError("Filename must have .gguf extension")

        return v


# ============================================================================
# Response Models
# ============================================================================


class DownloadResponse(BaseModel):
    """Response from initiating a download.
    
    Attributes:
        download_id: Unique identifier for this download
        status: Current state of the download
        message: Human-readable status message
        progress_url: URL for SSE progress updates
    """

    download_id: str = Field(
        ...,
        description="Unique download identifier (UUID)",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    status: DownloadState = Field(
        ...,
        description="Current download state",
    )
    message: str = Field(
        ...,
        description="Human-readable status message",
        examples=["Download initiated successfully"],
    )
    progress_url: str = Field(
        ...,
        description="SSE endpoint URL for progress updates",
        examples=["/api/models/download/550e8400-e29b-41d4-a716-446655440000/progress"],
    )


class ProgressUpdate(BaseModel):
    """Real-time progress update for a download.
    
    Attributes:
        download_id: Download identifier
        state: Current download state
        progress_percent: Completion percentage (0-100)
        downloaded_bytes: Number of bytes downloaded
        total_bytes: Total file size in bytes
        speed_mbps: Current download speed in MB/s
        eta_seconds: Estimated time remaining in seconds
        error_message: Error details if state is FAILED
    """

    download_id: str = Field(..., description="Download identifier")
    state: DownloadState = Field(..., description="Current state")
    progress_percent: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Download progress percentage",
    )
    downloaded_bytes: int = Field(
        ...,
        ge=0,
        description="Bytes downloaded so far",
    )
    total_bytes: int = Field(
        ...,
        ge=0,
        description="Total file size in bytes",
    )
    speed_mbps: Optional[float] = Field(
        default=None,
        ge=0,
        description="Download speed in MB/s",
    )
    eta_seconds: Optional[int] = Field(
        default=None,
        ge=0,
        description="Estimated time remaining in seconds",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if download failed",
    )


class ModelInfo(BaseModel):
    """Information about a downloaded model.
    
    Attributes:
        filename: Model filename
        size_bytes: File size in bytes
        path: Absolute path to the model file
        downloaded_at: Timestamp when download completed
        sha256_hash: SHA256 hash of the file (optional)
    """

    filename: str = Field(..., min_length=1, description="Model filename")
    size_bytes: int = Field(..., gt=0, description="File size in bytes")
    path: str = Field(..., description="Absolute file path")
    downloaded_at: datetime = Field(..., description="Download completion time")
    sha256_hash: Optional[str] = Field(
        default=None,
        min_length=64,
        max_length=64,
        description="SHA256 hash (64 hex characters)",
    )

    @field_validator("sha256_hash")
    @classmethod
    def validate_hash(cls, v: Optional[str]) -> Optional[str]:
        """Validate SHA256 hash format.
        
        Args:
            v: Hash string to validate
            
        Returns:
            Validated hash or None
            
        Raises:
            ValueError: If hash format is invalid
        """
        if v is None:
            return v

        # Validate hex format
        if not re.match(r"^[a-fA-F0-9]{64}$", v):
            raise ValueError("sha256_hash must be 64 hexadecimal characters")

        return v.lower()


# ============================================================================
# Error Models (RFC 9457)
# ============================================================================


class ProblemDetail(BaseModel):
    """RFC 9457 Problem Details for HTTP APIs.
    
    Attributes:
        type: URI reference identifying the problem type
        title: Short, human-readable summary
        status: HTTP status code
        detail: Human-readable explanation
        instance: URI reference to this specific occurrence
    """

    type: str = Field(
        default="about:blank",
        description="URI reference identifying problem type",
        examples=["https://api.example.com/problems/validation-error"],
    )
    title: str = Field(
        ...,
        description="Short, human-readable summary",
        examples=["Validation Error"],
    )
    status: int = Field(
        ...,
        ge=400,
        le=599,
        description="HTTP status code",
    )
    detail: Optional[str] = Field(
        default=None,
        description="Human-readable explanation",
        examples=["The filename field must end with .gguf extension"],
    )
    instance: Optional[str] = Field(
        default=None,
        description="URI reference to this occurrence",
        examples=["/api/models/download"],
    )
