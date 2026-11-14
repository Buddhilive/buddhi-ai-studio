from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, status
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
