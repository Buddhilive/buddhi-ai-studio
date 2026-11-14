from __future__ import annotations

import logging
from typing import Any
from app.services.agent.state import AgentState
from app.services.sandbox_service import sandbox_service

logger = logging.getLogger(__name__)


async def sync_egm_artifact_to_sandbox(
    state: AgentState,
    filename: str,
    content: str,
    session_id: str | None = None,
) -> str:
    """Store an EGM markdown artifact in AgentState and mirror into the sandbox filesystem."""
    # 1. Update AgentState
    artifacts = state.setdefault("egm_artifacts", {})
    artifacts[filename] = content

    # 2. Mirror to sandbox workspace
    from app.services.agent.tools import ensure_sandbox_session

    sid = session_id or state.get("session_id")
    if not sid:
        try:
            sid = await ensure_sandbox_session(None)
            state["session_id"] = sid
        except Exception as exc:
            logger.warning("Could not ensure sandbox session for artifact mirroring: %s", exc)

    run_id = state.get("run_id", "default_run")
    target_rel_path = f".buddhi/specs/{run_id}/{filename}"

    if sid:
        try:
            await sandbox_service.write_session_file(sid, target_rel_path, content)
            logger.debug("Mirrored artifact %s to sandbox %s (%d bytes)", target_rel_path, sid, len(content))
        except Exception as exc:
            logger.warning("Could not mirror artifact %s to sandbox session %s: %s", target_rel_path, sid, exc)

    return target_rel_path


async def rehydrate_egm_sandbox_if_needed(state: AgentState) -> str:
    """Ensure an active sandbox session exists and contains all persisted EGM artifacts."""
    from app.services.agent.tools import ensure_sandbox_session

    sid = await ensure_sandbox_session(state.get("session_id"))
    state["session_id"] = sid

    run_id = state.get("run_id", "default_run")
    artifacts = state.get("egm_artifacts") or {}

    for fname, content in artifacts.items():
        rel_path = f".buddhi/specs/{run_id}/{fname}"
        try:
            await sandbox_service.write_session_file(sid, rel_path, content)
        except Exception as exc:
            logger.warning("Failed re-hydrating %s into sandbox %s: %s", rel_path, sid, exc)

    # Check for out-of-band user edits to spec.md in the sandbox session
    spec_path = f".buddhi/specs/{run_id}/spec.md"
    try:
        on_disk_spec = await sandbox_service.read_session_file(sid, spec_path)
        if on_disk_spec and on_disk_spec.strip() and on_disk_spec != artifacts.get("spec.md"):
            logger.info("Detected out-of-band edit to %s in sandbox; updating state", spec_path)
            artifacts["spec.md"] = on_disk_spec
            spec_contract = state.get("spec_contract") or {}
            spec_contract["content"] = on_disk_spec
            state["spec_contract"] = spec_contract
    except Exception:
        pass

    return sid
