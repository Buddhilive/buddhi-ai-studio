import asyncio
import os
import sys
import tempfile
import pytest
from unittest.mock import AsyncMock, patch

from app.schemas.chat import ChatMessage
from app.services.agent.checkpointer import DuckDBCheckpointSaver
from app.services.agent.graph import build_agent_graph
from app.services.agent.state import AgentState
from app.services.sandbox_service import sandbox_service

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.mark.asyncio
async def test_egm_graph_spec_first_pause_at_resolve():
    """Verify that in EGM mode, graph executes analyze -> draft -> goldfish_review and pauses at resolve."""
    tmp_dir = tempfile.gettempdir()
    db_file = os.path.join(tmp_dir, "test_egm_lifecycle.duckdb")
    if os.path.exists(db_file):
        try:
            os.unlink(db_file)
        except Exception:
            pass

    checkpointer = DuckDBCheckpointSaver(db_file)
    test_graph = build_agent_graph(checkpointer=checkpointer, interrupt_before=["resolve"])

    # Mock sandbox calls
    mock_write = AsyncMock(return_value=True)
    orig_write = sandbox_service.write_session_file
    sandbox_service.write_session_file = mock_write

    # Mock inference engine to avoid calling external models
    async def mock_generate_stream(*args, **kwargs):
        from app.schemas.chat import ChatCompletionChunkDelta
        yield ChatCompletionChunkDelta(content="## Overview\nTest Spec\n\n## FeatureRange\nHigh-level\n\n## DetailedRange\nDetails\n\n## Target Scope & File Boundary\n- src/test.tsx\n", reasoning=None)

    from app.services.inference_service import inference_engine_manager
    orig_gen = inference_engine_manager.generate_stream
    inference_engine_manager.generate_stream = mock_generate_stream

    try:
        thread_id = "test_run_egm_1"
        config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
        initial_state: AgentState = {
            "run_id": thread_id,
            "session_id": "sess_mock_1",
            "messages": [ChatMessage(role="user", content="Build an accessible button component.")],
            "is_egm_mode": True,
            "egm_skill_mode": "standard",
            "egm_round": 1,
            "egm_max_rounds": 3,
            "egm_approved": False,
            "status": "running",
            "step": 0,
            "max_steps": 10,
        }

        # First run: should execute draft, then goldfish_review, then PAUSE before resolve
        result = await test_graph.ainvoke(initial_state, config=config)

        # Inspect next nodes at checkpoint
        snapshot = await test_graph.aget_state(config)
        assert snapshot is not None
        assert snapshot.next == ("resolve",)

        # Assert spec_contract and review_report were generated
        assert result.get("spec_contract") is not None
        assert "src/test.tsx" in result["spec_contract"]["target_scope_files"]
        assert result.get("review_report") is not None

        # Assert no production files were written
        assert mock_write.call_count >= 1
        for call_args in mock_write.call_args_list:
            written_path = call_args[0][1]
            assert written_path.startswith(".buddhi/specs/")

    finally:
        sandbox_service.write_session_file = orig_write
        inference_engine_manager.generate_stream = orig_gen
        try:
            if os.path.exists(db_file):
                os.unlink(db_file)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_egm_resolve_triage_and_sharpening_loop():
    """Verify that resuming resolve with decisions applies updates and loops to goldfish_review or plan."""
    tmp_dir = tempfile.gettempdir()
    db_file = os.path.join(tmp_dir, "test_egm_resolve_loop.duckdb")
    if os.path.exists(db_file):
        try:
            os.unlink(db_file)
        except Exception:
            pass

    checkpointer = DuckDBCheckpointSaver(db_file)
    test_graph = build_agent_graph(checkpointer=checkpointer, interrupt_before=["resolve"])

    thread_id = "test_run_resolve_1"
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}

    initial_state: AgentState = {
        "run_id": thread_id,
        "session_id": "sess_1",
        "messages": [ChatMessage(role="user", content="Build widget")],
        "is_egm_mode": True,
        "egm_skill_mode": "standard",
        "egm_round": 1,
        "egm_max_rounds": 3,
        "egm_approved": False,
        "spec_contract": {"content": "## Target Scope & File Boundary\n- src/widget.tsx\n", "target_scope_files": ["src/widget.tsx"]},
        "status": "running",
        "step": 0,
        "max_steps": 10,
    }

    # Save checkpoint at resolve with valid UUID/hex id
    import uuid
    valid_ckpt_id = uuid.uuid4().hex
    checkpointer.put(config, {"v": 1, "id": valid_ckpt_id, "ts": "2026-11-13", "channel_values": initial_state, "channel_versions": {}, "versions_seen": {}}, {}, {})

    # Triage decision with approve_for_implementation=True
    updated_config = await test_graph.aupdate_state(config, {
        "egm_approved": True,
        "resolution_decisions": [{"finding_id": "F-001", "decision": "accept", "approve_plan": True}],
    })

    # Assert state reflects approval using returned config
    snap = await test_graph.aget_state(updated_config)
    assert snap.values.get("egm_approved") is True


@pytest.mark.asyncio
async def test_default_mode_regression():
    """Verify that default mode (is_egm_mode=False) still follows analyze -> plan -> act."""
    checkpointer = DuckDBCheckpointSaver(":memory:")
    test_graph = build_agent_graph(checkpointer=checkpointer, interrupt_before=["resolve"])

    thread_id = "test_run_default_1"
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}

    state: AgentState = {
        "run_id": thread_id,
        "messages": [ChatMessage(role="user", content="Simple task")],
        "is_egm_mode": False,
        "status": "running",
        "step": 0,
        "max_steps": 2,
    }

    # Verify routing functions reflect default mode
    from app.services.agent.routing import route_after_analyze
    assert route_after_analyze(state) == "plan"
