from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.openai_errors import openai_error
from app.routers.chat import _validate_model
from app.schemas.agent import AgentRunRequest
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


@router.post("/runs/{run_id}/resume")
async def resume_agent_run(run_id: str):
    from app.services.agent.graph import agent_graph
    config = {"configurable": {"thread_id": run_id}}
    try:
        res = await agent_graph.ainvoke(None, config=config)
        return {"status": "resumed", "run_id": run_id, "state_status": res.get("status")}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume run {run_id}: {str(exc)}",
        )
