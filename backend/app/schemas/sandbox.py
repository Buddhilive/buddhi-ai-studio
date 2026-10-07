from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class SandboxExecutionRequest(BaseModel):
    code: str = Field(..., description="Code or shell script to execute")
    language: Literal["python", "bash", "sh"] = Field("python", description="Execution runtime language or shell")
    timeout_s: int = Field(60, ge=1, le=600, description="Execution timeout in seconds")
    allow_network: bool = Field(False, description="Whether to allow outbound network access")
    env_vars: dict[str, str] = Field(default_factory=dict, description="Environment variables passed to the sandbox")
    session_id: str | None = Field(None, description="Optional existing session to run within")


class SandboxExecutionResult(BaseModel):
    status: Literal["completed", "timeout", "error"] = Field(..., description="Execution status")
    stdout: str = Field("", description="Standard output from execution")
    stderr: str = Field("", description="Standard error or diagnostic trace")
    exit_code: int = Field(0, description="Process return code")
    execution_time_ms: float = Field(..., description="Elapsed wall-clock time in milliseconds")


class SandboxSessionCreateRequest(BaseModel):
    runtime_image: str = Field("python:3.11-slim", description="Docker image tag for sandbox container")
    timeout_s: int = Field(1800, ge=60, le=7200, description="Inactivity TTL in seconds before reaping")
    allow_network: bool = Field(False, description="Whether to allow outbound internet access")
    memory_limit_mb: int = Field(512, ge=128, le=4096, description="Memory limit in megabytes")
    cpu_limit: float = Field(1.0, ge=0.1, le=4.0, description="CPU cores quota")


class SandboxSessionResponse(BaseModel):
    session_id: str
    runtime_image: str
    status: Literal["running", "idle", "terminated"]
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime
    allow_network: bool


class SandboxFilePayload(BaseModel):
    path: str = Field(..., description="Relative path within /workspace")
    content: str = Field(..., description="File content (text or base64)")
    is_base64: bool = Field(False, description="Set True if content is base64 encoded")


class SandboxFileListResponse(BaseModel):
    session_id: str
    files: list[str] = Field(default_factory=list, description="List of file paths inside /workspace")


class SandboxHealthStatus(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    server_connected: bool
    server_url: str
    active_sessions_count: int
    error: str | None = None
