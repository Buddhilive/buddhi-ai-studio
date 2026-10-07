import logging
from typing import Any
from fastapi import APIRouter, HTTPException, status

from app.schemas.sandbox import (
    SandboxExecutionRequest,
    SandboxExecutionResult,
    SandboxFilePayload,
    SandboxHealthStatus,
    SandboxSessionCreateRequest,
    SandboxSessionResponse,
)
from app.services.sandbox_service import sandbox_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/sandbox", tags=["Sandbox"])


@router.get("/health", response_model=SandboxHealthStatus)
async def get_sandbox_health() -> SandboxHealthStatus:
    """Check health and connectivity of the OpenSandbox server."""
    health_status = await sandbox_service.check_health()
    if health_status.status == "unhealthy":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health_status.model_dump(),
        )
    return health_status


@router.post("/execute", response_model=SandboxExecutionResult)
async def execute_code_or_command(request: SandboxExecutionRequest) -> SandboxExecutionResult:
    """Execute code or shell script in an ephemeral or session-based sandbox."""
    try:
        return await sandbox_service.execute_one_shot(request)
    except Exception as exc:
        logger.exception("Sandbox execution exception: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sandbox execution failed: {exc}",
        )


@router.post("/sessions", response_model=SandboxSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(request: SandboxSessionCreateRequest | None = None) -> SandboxSessionResponse:
    """Create a new stateful sandbox session."""
    req = request or SandboxSessionCreateRequest()
    try:
        return await sandbox_service.create_session(req)
    except Exception as exc:
        logger.exception("Failed to create sandbox session: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to create sandbox container: {exc}",
        )


@router.get("/sessions", response_model=list[SandboxSessionResponse])
async def list_sessions() -> list[SandboxSessionResponse]:
    """List all currently active sandbox sessions."""
    return await sandbox_service.list_sessions()


@router.delete("/sessions/{session_id}")
async def terminate_session(session_id: str) -> dict[str, str]:
    """Terminate and destroy an active sandbox session."""
    terminated = await sandbox_service.terminate_session(session_id)
    if not terminated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    return {"status": "terminated", "session_id": session_id}


@router.post("/sessions/{session_id}/files")
async def write_session_file(session_id: str, payload: SandboxFilePayload) -> dict[str, str]:
    """Write a file into the sandbox workspace."""
    try:
        await sandbox_service.write_session_file(
            session_id=session_id,
            path=payload.path,
            content=payload.content,
            is_base64=payload.is_base64,
        )
        return {"status": "created", "path": payload.path}
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    except Exception as exc:
        logger.exception("Failed to write file in session %s: %s", session_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File write failed: {exc}",
        )


@router.get("/sessions/{session_id}/files/{file_path:path}")
async def read_session_file(session_id: str, file_path: str) -> dict[str, Any]:
    """Read a file from the sandbox workspace."""
    try:
        content = await sandbox_service.read_session_file(session_id, file_path)
        return {"path": file_path, "content": content}
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    except Exception as exc:
        logger.exception("Failed to read file %s in session %s: %s", file_path, session_id, exc)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File {file_path} could not be read: {exc}",
        )
