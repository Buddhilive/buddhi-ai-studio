from __future__ import annotations

import logging
from types import TracebackType
from typing import Any

from app.core.config import settings
from app.schemas.sandbox import SandboxExecutionRequest, SandboxExecutionResult, SandboxSessionCreateRequest
from app.services.rlm.helpers_src import RLM_HELPERS_CODE
from app.services.sandbox_service import sandbox_service, SandboxService

logger = logging.getLogger(__name__)


class RlmSession:
    """Encapsulates an ephemeral, network-isolated OpenSandbox session for RLM."""

    def __init__(
        self,
        session_id: str,
        service: SandboxService = sandbox_service,
        repo_mount_path: str | None = None,
    ) -> None:
        self.session_id = session_id
        self._service = service
        self.repo_mount_path = repo_mount_path

    async def initialize(self) -> None:
        """Injects helper scripts into the sandbox."""
        logger.info("Initializing RLM session %s", self.session_id)
        # Write helper library into sandbox
        await self._service.write_session_file(
            self.session_id,
            "rlm_helpers.py",
            RLM_HELPERS_CODE,
        )

    async def execute_code(self, python_code: str, timeout_s: int = 60) -> SandboxExecutionResult:
        """Executes Python code in the RLM sandbox session."""
        req = SandboxExecutionRequest(
            code=python_code,
            language="python",
            timeout_s=timeout_s,
        )
        return await self._service.execute_in_session(self.session_id, req)

    async def close(self) -> None:
        """Destroys the sandbox container and frees resources immediately."""
        logger.info("Closing and terminating RLM session %s", self.session_id)
        try:
            await self._service.terminate_session(self.session_id)
        except Exception as exc:
            logger.warning("Error terminating RLM session %s: %s", self.session_id, exc)

    async def __aenter__(self) -> RlmSession:
        await self.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()


class RlmSessionManager:
    """Factory and lifecycle coordinator for RLM sessions."""

    def __init__(self, service: SandboxService = sandbox_service) -> None:
        self._service = service

    async def create_session(
        self,
        timeout_s: int | None = None,
        repo_mount_path: str | None = None,
    ) -> RlmSession:
        ttl = timeout_s or settings.sandbox_rlm_idle_ttl_s
        req = SandboxSessionCreateRequest(
            runtime_image=settings.sandbox_default_image,
            timeout_s=ttl,
            allow_network=False,
            memory_limit_mb=settings.sandbox_rlm_memory_mb,
            purpose="rlm",
        )
        resp = await self._service.create_session(req)

        return RlmSession(
            session_id=resp.session_id,
            service=self._service,
            repo_mount_path=repo_mount_path,
        )
