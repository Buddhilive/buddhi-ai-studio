from __future__ import annotations

import logging
from typing import Any, Literal
from fastapi import APIRouter, HTTPException, Path, Query, status
from fastapi.responses import StreamingResponse

from app.core.openai_errors import openai_error
from app.routers.chat import _validate_model
from app.schemas.agent import AgentRunRequest, EgmArtifactsResponse, EgmResolveRequest
from app.schemas.chat import ChatCompletionRequest
from app.services.agent.runs import AgentConcurrencyLimitError, agent_run_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/agent", tags=["agent"])


@router.post("/runs")
async def create_agent_run(request: AgentRunRequest):
    # Reuse model validation logic from chat router
    dummy_chat_req = ChatCompletionRequest(
        model=request.model,
        messages=request.messages,
    )
    _validate_model(dummy_chat_req)

    try:
        run_id, emitter = await agent_run_manager.start_run(request)
    except AgentConcurrencyLimitError as exc:
        raise openai_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            str(exc),
            "rate_limit_exceeded",
        ) from exc

    return StreamingResponse(
        emitter.stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Run-Id": run_id,
        },
    )


@router.delete("/runs/{run_id}")
async def cancel_agent_run(run_id: str):
    cancelled = await agent_run_manager.cancel_run(run_id)
    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found or already completed",
        )
    return {"status": "cancelled", "run_id": run_id}


@router.get("/runs/{run_id}/trajectory")
async def get_agent_trajectory(
    run_id: str = Path(..., pattern=r"^[a-zA-Z0-9_-]{1,64}$"),
    after_seq: int = Query(0, ge=0),
    format: Literal["json", "jsonl"] = Query("json"),
):
    from app.services.agent.trajectory import trajectory_store

    events = await trajectory_store.list_events_after(run_id, after_seq=after_seq)
    if not events and after_seq == 0 and agent_run_manager.get_active_run(run_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trajectory for run {run_id} not found",
        )

    if format == "jsonl":
        headers = {
            "Content-Disposition": f'attachment; filename="trajectory-{run_id}.jsonl"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        }
        return StreamingResponse(
            trajectory_store.stream_export(run_id, fmt="jsonl", after_seq=after_seq),
            media_type="application/x-ndjson; charset=utf-8",
            headers=headers,
        )

    last_seq = events[-1]["seq"] if events else after_seq
    return {
        "run_id": run_id,
        "last_seq": last_seq,
        "events": events,
    }


@router.post("/runs/{run_id}/resolve")
async def resolve_agent_run(run_id: str, request: EgmResolveRequest):
    from app.services.agent.graph import agent_graph
    config = {"configurable": {"thread_id": run_id, "checkpoint_ns": ""}}

    try:
        current_state = await agent_graph.aget_state(config)
        if not current_state or not current_state.values:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run {run_id} checkpoint not found",
            )

        # Update state with user triage decisions
        state_updates: dict[str, Any] = {
            "resolution_decisions": [d.model_dump() for d in request.decisions],
            "egm_approved": request.approve_for_implementation,
        }

        if request.edited_spec_content:
            spec_contract = current_state.values.get("spec_contract") or {}
            spec_contract["content"] = request.edited_spec_content
            from app.services.agent.egm.nodes import extract_target_scope_files
            spec_contract["target_scope_files"] = extract_target_scope_files(request.edited_spec_content)
            state_updates["spec_contract"] = spec_contract

        updated_config = await agent_graph.aupdate_state(config, state_updates)

        # Resume execution through graph
        res = await agent_graph.ainvoke(None, config=updated_config)
        return {
            "status": "resumed",
            "run_id": run_id,
            "egm_phase": res.get("egm_phase"),
            "egm_round": res.get("egm_round"),
            "state_status": res.get("status"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to resolve run %s: %s", run_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve run {run_id}: {str(exc)}",
        )


@router.get("/runs/{run_id}/artifacts", response_model=EgmArtifactsResponse)
async def get_agent_artifacts(run_id: str):
    from app.services.agent.graph import agent_graph
    config = {"configurable": {"thread_id": run_id, "checkpoint_ns": ""}}

    try:
        snapshot = await agent_graph.aget_state(config)
        if not snapshot or not snapshot.values:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run {run_id} not found",
            )

        vals = snapshot.values
        return EgmArtifactsResponse(
            run_id=run_id,
            status=vals.get("status", "running"),
            egm_phase=vals.get("egm_phase"),
            egm_round=vals.get("egm_round", 1),
            spec_contract=vals.get("spec_contract"),
            review_report=vals.get("review_report"),
            concepts_brief=vals.get("concepts_brief"),
            drift_report=vals.get("drift_report"),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to fetch artifacts for run %s: %s", run_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch artifacts for {run_id}: {str(exc)}",
        )


@router.get("/harness/{workspace_id}")
async def get_harness_state(workspace_id: str):
    from app.services.agent.harness.storage import harness_storage_service
    from app.services.agent.harness.validator import validate_workspace_id

    if not validate_workspace_id(workspace_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid workspace_id")

    active = harness_storage_service.get_active_overlay(workspace_id)
    history = harness_storage_service.list_overlay_history(workspace_id, limit=20)
    experiences = harness_storage_service.get_active_experiences(workspace_id, limit=50)
    return {
        "workspace_id": workspace_id,
        "active_overlay": active.model_dump(mode="json") if active else None,
        "history": [h.model_dump(mode="json") for h in history],
        "experiences": [e.model_dump(mode="json") for e in experiences],
    }


@router.post("/harness/{workspace_id}/rollback")
async def rollback_harness_overlay(workspace_id: str, body: dict):
    from app.services.agent.harness.storage import harness_storage_service
    from app.services.agent.harness.validator import validate_workspace_id

    version_id = str((body or {}).get("version_id") or "")
    if not validate_workspace_id(workspace_id) or not validate_workspace_id(version_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid workspace_id or version_id")
    try:
        restored = harness_storage_service.rollback_overlay(workspace_id, version_id)
        return {"workspace_id": workspace_id, "active_overlay": restored.model_dump(mode="json")}
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/harness/{workspace_id}/reset")
async def reset_harness_overlay(workspace_id: str):
    from app.services.agent.harness.storage import harness_storage_service
    from app.services.agent.harness.validator import validate_workspace_id

    if not validate_workspace_id(workspace_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid workspace_id")
    harness_storage_service.reset_workspace(workspace_id)
    return {"workspace_id": workspace_id, "status": "reset"}


@router.patch("/harness/{workspace_id}/experience/{entry_id}")
async def pin_harness_experience(workspace_id: str, entry_id: str, body: dict):
    from app.services.agent.harness.storage import harness_storage_service
    from app.services.agent.harness.validator import validate_workspace_id

    if not validate_workspace_id(workspace_id) or not validate_workspace_id(entry_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid workspace_id or entry_id")
    pinned = bool((body or {}).get("pinned", True))
    ok = harness_storage_service.set_experience_pin(workspace_id, entry_id, pinned)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Experience {entry_id} not found")
    return {"workspace_id": workspace_id, "entry_id": entry_id, "is_pinned": pinned}


@router.delete("/harness/{workspace_id}/experience/{entry_id}")
async def delete_harness_experience(workspace_id: str, entry_id: str):
    from app.services.agent.harness.storage import harness_storage_service
    from app.services.agent.harness.validator import validate_workspace_id

    if not validate_workspace_id(workspace_id) or not validate_workspace_id(entry_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid workspace_id or entry_id")
    ok = harness_storage_service.delete_experience(workspace_id, entry_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Experience {entry_id} not found")
    return {"workspace_id": workspace_id, "entry_id": entry_id, "deleted": True}
