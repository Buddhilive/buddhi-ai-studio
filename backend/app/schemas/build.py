from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

BuildTemplate = Literal["nextjs-vibe", "python-blank", "node-blank"]
BuildDbDialect = Literal["postgresql", "sqlite"]


class BuildProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str = Field(default="", max_length=4000)
    template: BuildTemplate = "nextjs-vibe"
    db_dialect: BuildDbDialect = "postgresql"


class BuildProjectResponse(BaseModel):
    id: str = Field(..., pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    name: str
    description: str = ""
    template: BuildTemplate = "nextjs-vibe"
    db_dialect: BuildDbDialect = "postgresql"
    active_session_id: str | None = None
    session_active: bool = False
    runtime_image: str
    created_at: datetime
    updated_at: datetime


class BuildProjectStartResponse(BaseModel):
    project: BuildProjectResponse
    session_id: str
    restored_files_count: int = 0
    hydrated_from: Literal["active_session", "snapshot", "template"] = "template"


class BuildFileNode(BaseModel):
    name: str
    path: str
    type: Literal["file", "directory"]
    size: int | None = None
    children: list["BuildFileNode"] = Field(default_factory=list)


class BuildFileTreeResponse(BaseModel):
    project_id: str
    root: str = "/workspace"
    files: list[str] = Field(default_factory=list)
    tree: list[BuildFileNode] = Field(default_factory=list)


class BuildFileContentResponse(BaseModel):
    project_id: str
    path: str
    content: str
    size: int = 0


class BuildFileWriteRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=512)
    content: str
    is_base64: bool = False


class BuildFileWriteResponse(BaseModel):
    project_id: str
    path: str
    saved: bool = True
    synced_to_storage: bool = True


class BuildHistoryPayload(BaseModel):
    messages: list[dict[str, Any]] = Field(default_factory=list)
    trajectory_events: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: datetime | None = None


class BuildPreviewStatusResponse(BaseModel):
    running: bool = False
    port: int = 3000
    url: str | None = None
