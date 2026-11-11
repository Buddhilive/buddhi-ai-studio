import asyncio
import sys
from unittest.mock import patch
import pytest

from app.schemas.chat import ChatMessage
from app.services.agent.checkpointer import DuckDBCheckpointSaver
from app.services.agent.graph import build_agent_graph
from app.services.agent.state import AgentState
from tests.conftest_agent import ScriptedInferenceEngine, create_mock_sandbox

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


from langgraph.checkpoint.base import empty_checkpoint

def test_duckdb_checkpointer_crud(tmp_path):
    checkpointer = DuckDBCheckpointSaver(db_path=str(tmp_path / "test_cp.duckdb"))
    config = {"configurable": {"thread_id": "thread_1", "checkpoint_ns": ""}}

    cp = empty_checkpoint()
    cp["id"] = "cp_1"
    metadata = {"source": "update", "step": 2, "writes": {}, "parents": {}}

    res = checkpointer.put(config, cp, metadata, {})
    assert res["configurable"]["checkpoint_id"] == "cp_1"

    tup = checkpointer.get_tuple(config)
    assert tup is not None
    assert tup.checkpoint["id"] == "cp_1"


def test_graph_pause_and_resume(tmp_path):
    async def _run():
        checkpointer = DuckDBCheckpointSaver(db_path=str(tmp_path / "test_pause.duckdb"))
        # Graph compiled with interrupt before "act"
        g = build_agent_graph(checkpointer=checkpointer, interrupt_before=["act"])

        engine = ScriptedInferenceEngine()
        mock_sandbox = create_mock_sandbox()

        thread_id = "test_thread_pause"
        config = {"configurable": {"thread_id": thread_id}}

        initial_state: AgentState = {
            "run_id": thread_id,
            "messages": [ChatMessage(role="user", content="Test pause before act")],
            "plan": [],
            "pending_tool_calls": [],
            "observations": [],
            "verdict": None,
            "step": 0,
            "max_steps": 10,
            "recent_actions": [],
            "status": "running",
            "session_id": "test_sess_1",
            "final_output": None,
            "error": None,
        }

        with patch("app.services.agent.nodes.inference_engine_manager.generate_stream", engine.generate_stream), \
             patch("app.services.agent.tools.sandbox_service", mock_sandbox):

            # First invocation should pause before "act"
            res1 = await g.ainvoke(initial_state, config=config)
            snapshot = g.get_state(config)
            assert snapshot.next == ("act",)
            assert len(snapshot.values["plan"]) >= 1

            # Resume invocation by passing None
            res2 = await g.ainvoke(None, config=config)
            assert res2["status"] == "completed"

    asyncio.run(_run())
