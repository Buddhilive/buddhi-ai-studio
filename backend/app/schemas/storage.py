import re
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class StorageHealthStatus(BaseModel):
    status: Literal["healthy", "unhealthy"] = Field(..., description="Health status of RustFS service")
    service_url: str = Field(..., description="Configured RustFS upstream endpoint URL")
    latency_ms: float = Field(..., description="Health check latency in milliseconds")
    version: str | None = Field(None, description="RustFS engine version if available")
    error: str | None = Field(None, description="Error message if unhealthy")


class BucketInfo(BaseModel):
    name: str = Field(..., description="Bucket name")
    created_at: str | None = Field(None, description="ISO-8601 creation timestamp")


class CreateBucketRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=63, description="S3-compliant bucket name")

    @field_validator("name")
    @classmethod
    def validate_bucket_name(cls, v: str) -> str:
        name = v.strip()
        # S3 bucket naming rules: 3-63 chars, lowercase letters, numbers, dots, hyphens.
        # Starts and ends with a letter or number.
        pattern = r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$"
        if not re.match(pattern, name):
            raise ValueError(
                "Invalid bucket name. Must be 3-63 characters, lowercase alphanumeric, dots, or hyphens, starting and ending with alphanumeric."
            )
        if ".." in name or ".-" in name or "-." in name:
            raise ValueError("Bucket name contains invalid adjacent punctuation.")
        return name


class BucketListResponse(BaseModel):
    buckets: list[BucketInfo]
    default_bucket: str
