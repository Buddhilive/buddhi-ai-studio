from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import BACKEND_ROOT
from app.schemas.sandbox import SandboxExecutionRequest
from app.services.sandbox_service import sandbox_service

logger = logging.getLogger(__name__)

_STARTER_ROOT = BACKEND_ROOT.parent / "sandbox" / "vibe-starter"


async def ensure_vibe_starter_workspace(session_id: str) -> None:
    """Hydrate /workspace in an OpenSandbox session with the Next.js 16+ Golden Starter."""
    try:
        probe = await sandbox_service.execute_in_session(
            session_id,
            SandboxExecutionRequest(
                code=(
                    "if [ -f /workspace/package.json ]; then echo 'EXISTS'; "
                    "elif [ -d /opt/vibe-starter ]; then "
                    "cp -rn /opt/vibe-starter/. /workspace/ && "
                    "ln -sfn /opt/vibe-starter/node_modules /workspace/node_modules && echo 'HYDRATED_FAST'; "
                    "else echo 'FALLBACK_NEEDED'; fi"
                ),
                language="bash",
                timeout_s=15,
            ),
        )
        status = (probe.stdout or "").strip()
        if status in ("EXISTS", "HYDRATED_FAST"):
            return
    except Exception as exc:
        logger.debug("Fast starter hydration probe failed for %s: %s", session_id, exc)
        return

    if not _STARTER_ROOT.exists():
        return

    for file_path in sorted(_STARTER_ROOT.rglob("*")):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(_STARTER_ROOT).as_posix()
        if rel.startswith("node_modules/") or rel.startswith(".next/"):
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
            await sandbox_service.write_session_file(session_id, rel, content)
        except Exception as exc:
            logger.debug("Fallback starter write skipped for %s: %s", rel, exc)
