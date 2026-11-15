from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Path, Query, Request, status

from app.schemas.build import (
    BuildFileContentResponse,
    BuildFileTreeResponse,
    BuildFileWriteRequest,
    BuildFileWriteResponse,
    BuildHistoryPayload,
    BuildPreviewStatusResponse,
    BuildProjectCreateRequest,
    BuildProjectResponse,
    BuildProjectStartResponse,
)
from app.schemas.sandbox import SandboxExecutionRequest, SandboxExecutionResult
from app.services.build_project_service import build_project_service

router = APIRouter(prefix="/v1/build", tags=["Build"])

ProjectIdParam = Path(..., pattern=r"^[a-zA-Z0-9_-]{1,64}$")


@router.get("/projects", response_model=list[BuildProjectResponse])
async def list_build_projects() -> list[BuildProjectResponse]:
    return await build_project_service.list_projects()


@router.post("/projects", response_model=BuildProjectStartResponse, status_code=status.HTTP_201_CREATED)
async def create_build_project(request: BuildProjectCreateRequest) -> BuildProjectStartResponse:
    return await build_project_service.create_project(request)


@router.get("/projects/{project_id}", response_model=BuildProjectResponse)
async def get_build_project(project_id: str = ProjectIdParam) -> BuildProjectResponse:
    return await build_project_service.get_project(project_id)


@router.delete("/projects/{project_id}")
async def delete_build_project(project_id: str = ProjectIdParam) -> dict[str, Any]:
    return await build_project_service.delete_project(project_id)


@router.post("/projects/{project_id}/start", response_model=BuildProjectStartResponse)
async def start_build_project(project_id: str = ProjectIdParam) -> BuildProjectStartResponse:
    return await build_project_service.start_or_restore_project(project_id)


@router.get("/projects/{project_id}/files", response_model=BuildFileTreeResponse)
async def list_build_project_files(project_id: str = ProjectIdParam) -> BuildFileTreeResponse:
    return await build_project_service.list_files(project_id)


@router.get("/projects/{project_id}/files/{file_path:path}", response_model=BuildFileContentResponse)
async def read_build_project_file(
    file_path: str,
    project_id: str = ProjectIdParam,
) -> BuildFileContentResponse:
    return await build_project_service.read_file(project_id, file_path)


@router.put("/projects/{project_id}/files", response_model=BuildFileWriteResponse)
async def write_build_project_file(
    payload: BuildFileWriteRequest,
    project_id: str = ProjectIdParam,
) -> BuildFileWriteResponse:
    return await build_project_service.write_file(
        project_id, payload.path, payload.content, is_base64=payload.is_base64
    )


@router.post("/projects/{project_id}/execute", response_model=SandboxExecutionResult)
async def execute_build_project_command(
    payload: SandboxExecutionRequest,
    project_id: str = ProjectIdParam,
) -> SandboxExecutionResult:
    return await build_project_service.execute_command(project_id, payload)


@router.get("/projects/{project_id}/history", response_model=BuildHistoryPayload)
async def get_build_project_history(project_id: str = ProjectIdParam) -> BuildHistoryPayload:
    return await build_project_service.get_history(project_id)


@router.put("/projects/{project_id}/history", response_model=BuildHistoryPayload)
async def save_build_project_history(
    payload: BuildHistoryPayload,
    project_id: str = ProjectIdParam,
) -> BuildHistoryPayload:
    return await build_project_service.save_history(project_id, payload)


@router.get("/projects/{project_id}/preview/status", response_model=BuildPreviewStatusResponse)
async def get_build_preview_status(
    project_id: str = ProjectIdParam,
    port: int = Query(3000, ge=1, le=65535),
) -> BuildPreviewStatusResponse:
    return await build_project_service.get_preview_status(project_id, port=port)


@router.api_route(
    "/projects/{project_id}/preview",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
@router.api_route(
    "/projects/{project_id}/preview/{rel_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def proxy_build_preview(
    request: Request,
    project_id: str = ProjectIdParam,
    rel_path: str = "",
    port: int = Query(3000, ge=1, le=65535),
):
    return await build_project_service.proxy_preview(project_id, rel_path, request, port=port)
