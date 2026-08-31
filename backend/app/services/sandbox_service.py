import asyncio
import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from opensandbox import Sandbox
from opensandbox.config.connection import ConnectionConfig
from opensandbox.models.execd import RunCommandOpts

from app.core.config import settings
from app.schemas.sandbox import (
    SandboxExecutionRequest,
    SandboxExecutionResult,
    SandboxHealthStatus,
    SandboxSessionCreateRequest,
    SandboxSessionResponse,
)

logger = logging.getLogger(__name__)


@dataclass
class ActiveSession:
    session_id: str
    sandbox: Sandbox
    runtime_image: str
    created_at: datetime
    last_activity_at: datetime
    timeout_s: int
    allow_network: bool

    @property
    def expires_at(self) -> datetime:
        return self.last_activity_at + timedelta(seconds=self.timeout_s)

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    def touch(self) -> None:
        self.last_activity_at = datetime.now(timezone.utc)


class SandboxService:
    def __init__(self) -> None:
        self._http_client: httpx.AsyncClient | None = None
        self._active_sessions: dict[str, ActiveSession] = {}
        self._reaper_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    def _get_connection_config(self) -> ConnectionConfig:
        parsed = urlparse(settings.opensandbox_server_url)
        protocol = parsed.scheme or "http"
        domain = parsed.netloc or parsed.path or "localhost:8090"
        return ConnectionConfig(
            domain=domain,
            protocol=protocol,
            request_timeout=timedelta(seconds=settings.sandbox_default_timeout_s + 10),
        )

    async def start(self) -> None:
        self._http_client = httpx.AsyncClient(timeout=10.0)
        self._reaper_task = asyncio.create_task(self._reaper_loop())
        logger.info("SandboxService started with control plane at %s", settings.opensandbox_server_url)

    async def stop(self) -> None:
        if self._reaper_task:
            self._reaper_task.cancel()
            try:
                await self._reaper_task
            except asyncio.CancelledError:
                pass
            self._reaper_task = None

        async with self._lock:
            for session_id, session in list(self._active_sessions.items()):
                try:
                    await session.sandbox.destroy()
                except Exception as exc:
                    logger.warning("Error destroying sandbox session %s on shutdown: %s", session_id, exc)
            self._active_sessions.clear()

        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        logger.info("SandboxService stopped")

    async def check_health(self) -> SandboxHealthStatus:
        server_url = settings.opensandbox_server_url
        if not self._http_client:
            return SandboxHealthStatus(
                status="unhealthy",
                server_connected=False,
                server_url=server_url,
                active_sessions_count=len(self._active_sessions),
                error="HTTP client not initialized",
            )
        try:
            resp = await self._http_client.get(f"{server_url.rstrip('/')}/health")
            if resp.status_code < 400:
                return SandboxHealthStatus(
                    status="healthy",
                    server_connected=True,
                    server_url=server_url,
                    active_sessions_count=len(self._active_sessions),
                )
            return SandboxHealthStatus(
                status="degraded",
                server_connected=False,
                server_url=server_url,
                active_sessions_count=len(self._active_sessions),
                error=f"Server returned status {resp.status_code}",
            )
        except Exception as exc:
            return SandboxHealthStatus(
                status="unhealthy",
                server_connected=False,
                server_url=server_url,
                active_sessions_count=len(self._active_sessions),
                error=str(exc),
            )

    async def execute_one_shot(self, request: SandboxExecutionRequest) -> SandboxExecutionResult:
        """Execute code or shell command in an ephemeral sandbox and destroy it immediately."""
        # If an existing session_id is provided, run within that session instead
        if request.session_id:
            return await self.execute_in_session(request.session_id, request)

        start_time = time.perf_counter()
        conn_config = self._get_connection_config()
        sandbox: Sandbox | None = None
        try:
            sandbox = await Sandbox.create(
                image=settings.sandbox_default_image,
                timeout=timedelta(seconds=request.timeout_s + 15),
                connection_config=conn_config,
            )

            result = await self._run_in_sandbox(sandbox, request)
            return result
        except asyncio.TimeoutError:
            elapsed = (time.perf_counter() - start_time) * 1000
            return SandboxExecutionResult(
                status="timeout",
                stdout="",
                stderr=f"Execution timed out after {request.timeout_s}s",
                exit_code=124,
                execution_time_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.warning("Error executing one-shot sandbox: %s", exc)
            return SandboxExecutionResult(
                status="error",
                stdout="",
                stderr=f"Sandbox execution failed: {exc}",
                exit_code=1,
                execution_time_ms=elapsed,
            )
        finally:
            if sandbox:
                try:
                    await sandbox.destroy()
                except Exception as exc:
                    logger.debug("Failed to destroy ephemeral sandbox: %s", exc)

    async def _run_in_sandbox(self, sandbox: Sandbox, request: SandboxExecutionRequest) -> SandboxExecutionResult:
        start_time = time.perf_counter()
        if request.language == "python":
            command = ["python", "-c", request.code]
        elif request.language == "bash":
            command = ["bash", "-c", request.code]
        else:
            command = ["sh", "-c", request.code]

        opts = RunCommandOpts(
            timeout=timedelta(seconds=request.timeout_s),
            env=request.env_vars,
        )

        try:
            exec_result = await asyncio.wait_for(
                sandbox.commands.run(command, opts=opts),
                timeout=request.timeout_s + 2.0,
            )
        except asyncio.TimeoutError:
            elapsed = (time.perf_counter() - start_time) * 1000
            return SandboxExecutionResult(
                status="timeout",
                stdout="",
                stderr=f"Execution timed out after {request.timeout_s}s",
                exit_code=124,
                execution_time_ms=elapsed,
            )

        elapsed = (time.perf_counter() - start_time) * 1000
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []

        if exec_result.logs and exec_result.logs.content:
            for msg in exec_result.logs.content:
                if getattr(msg, "is_error", False):
                    stderr_parts.append(msg.text)
                else:
                    stdout_parts.append(msg.text)

        status_str = "completed" if (exec_result.exit_code == 0) else "error"
        if exec_result.error:
            stderr_parts.append(str(exec_result.error))

        return SandboxExecutionResult(
            status=status_str,
            stdout="".join(stdout_parts),
            stderr="".join(stderr_parts),
            exit_code=exec_result.exit_code if exec_result.exit_code is not None else 0,
            execution_time_ms=elapsed,
        )

    # Session Management
    async def create_session(self, request: SandboxSessionCreateRequest) -> SandboxSessionResponse:
        conn_config = self._get_connection_config()
        sandbox = await Sandbox.create(
            image=request.runtime_image,
            timeout=timedelta(seconds=request.timeout_s),
            connection_config=conn_config,
        )
        session_id = sandbox.id
        now = datetime.now(timezone.utc)
        session = ActiveSession(
            session_id=session_id,
            sandbox=sandbox,
            runtime_image=request.runtime_image,
            created_at=now,
            last_activity_at=now,
            timeout_s=request.timeout_s,
            allow_network=request.allow_network,
        )
        async with self._lock:
            self._active_sessions[session_id] = session

        return SandboxSessionResponse(
            session_id=session_id,
            runtime_image=session.runtime_image,
            status="running",
            created_at=session.created_at,
            last_activity_at=session.last_activity_at,
            expires_at=session.expires_at,
            allow_network=session.allow_network,
        )

    async def list_sessions(self) -> list[SandboxSessionResponse]:
        async with self._lock:
            return [
                SandboxSessionResponse(
                    session_id=s.session_id,
                    runtime_image=s.runtime_image,
                    status="running" if not s.is_expired() else "idle",
                    created_at=s.created_at,
                    last_activity_at=s.last_activity_at,
                    expires_at=s.expires_at,
                    allow_network=s.allow_network,
                )
                for s in self._active_sessions.values()
            ]

    async def get_session(self, session_id: str) -> ActiveSession | None:
        async with self._lock:
            return self._active_sessions.get(session_id)

    async def terminate_session(self, session_id: str) -> bool:
        async with self._lock:
            session = self._active_sessions.pop(session_id, None)
        if not session:
            return False
        try:
            await session.sandbox.destroy()
            return True
        except Exception as exc:
            logger.warning("Error destroying session %s: %s", session_id, exc)
            return True

    async def execute_in_session(self, session_id: str, request: SandboxExecutionRequest) -> SandboxExecutionResult:
        session = await self.get_session(session_id)
        if not session:
            return SandboxExecutionResult(
                status="error",
                stdout="",
                stderr=f"Session {session_id} not found or expired",
                exit_code=1,
                execution_time_ms=0.0,
            )
        session.touch()
        return await self._run_in_sandbox(session.sandbox, request)

    async def write_session_file(self, session_id: str, path: str, content: str, is_base64: bool = False) -> bool:
        session = await self.get_session(session_id)
        if not session:
            raise KeyError(f"Session {session_id} not found")
        session.touch()
        file_bytes = base64.b64decode(content) if is_base64 else content.encode("utf-8")
        await session.sandbox.files.write_file(path, file_bytes)
        return True

    async def read_session_file(self, session_id: str, path: str) -> str:
        session = await self.get_session(session_id)
        if not session:
            raise KeyError(f"Session {session_id} not found")
        session.touch()
        data = await session.sandbox.files.read_bytes(path)
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return base64.b64encode(data).decode("ascii")

    async def _reaper_loop(self) -> None:
        """Background loop sweeping expired sessions every 30 seconds."""
        while True:
            try:
                await asyncio.sleep(30)
                expired_ids: list[str] = []
                async with self._lock:
                    for s_id, s in self._active_sessions.items():
                        if s.is_expired():
                            expired_ids.append(s_id)

                for s_id in expired_ids:
                    logger.info("Reaping expired sandbox session %s", s_id)
                    await self.terminate_session(s_id)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Error in sandbox reaper loop: %s", exc)


sandbox_service = SandboxService()
