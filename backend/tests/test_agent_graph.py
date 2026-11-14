import asyncio
import sys
import uuid
from unittest.mock import patch
import pytest

from app.schemas.chat import ChatMessage
from app.services.agent.events import AgentEventEmitter
from app.services.agent.graph import agent_graph
from app.services.agent.state import AgentState
from tests.conftest_agent import ScriptedInferenceEngine, create_mock_sandbox

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def test_agent_graph_full_cycle():
    async def _run():
        engine = ScriptedInferenceEngine()
        mock_sandbox = create_mock_sandbox()

        run_id = f"test_run_{uuid.uuid4().hex}"
        emitter = AgentEventEmitter(run_id)

        initial_state: AgentState = {
            "run_id": run_id,
            "messages": [ChatMessage(role="user", content="Create hello.py and run it")],
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
            "is_egm_mode": False,
            "is_rlm_mode": False,
        }

        with patch("app.services.agent.nodes.inference_engine_manager.generate_stream", engine.generate_stream), \
             patch("app.services.agent.tools.sandbox_service", mock_sandbox):

            result = await agent_graph.ainvoke(
                initial_state,
                config={"configurable": {"emitter": emitter, "thread_id": run_id}},
            )

            assert result["status"] == "completed"
            assert result["step"] >= 4
            assert len(result["plan"]) >= 2
            assert result["plan"][0].title == "Write hello.py script"
            assert result["verdict"] == "pass"

    asyncio.run(_run())


def test_agent_graph_max_steps_termination():
    async def _run():
        mock_sandbox = create_mock_sandbox()

        # Engine that always retries to trigger max steps
        class InfiniteRetryEngine(ScriptedInferenceEngine):
            async def generate_stream(self, messages, *args, **kwargs):
                prompt = " ".join(str(m.content) for m in messages if hasattr(m, "content"))
                if "PHASE: ACT" in prompt:
                    from app.schemas.chat import ChatCompletionChunkDelta
                    yield ChatCompletionChunkDelta(content='<|tool_call>call:run_command{"command": "python retry.py"}<tool_call|>')
                elif "PHASE: REVIEW" in prompt:
                    from app.schemas.chat import ChatCompletionChunkDelta
                    yield ChatCompletionChunkDelta(content="Review: Retry needed.\nVERDICT: retry")
                else:
                    async for chunk in super().generate_stream(messages, *args, **kwargs):
                        yield chunk

        engine = InfiniteRetryEngine()
        run_id = f"test_loop_{uuid.uuid4().hex}"
        emitter = AgentEventEmitter(run_id)

        initial_state: AgentState = {
            "run_id": run_id,
            "messages": [ChatMessage(role="user", content="Loop forever")],
            "plan": [],
            "pending_tool_calls": [],
            "observations": [],
            "verdict": None,
            "step": 0,
            "max_steps": 3,
            "recent_actions": [],
            "status": "running",
            "session_id": "test_sess_1",
            "final_output": None,
            "error": None,
            "is_egm_mode": False,
            "is_rlm_mode": False,
        }

        with patch("app.services.agent.nodes.inference_engine_manager.generate_stream", engine.generate_stream), \
             patch("app.services.agent.tools.sandbox_service", mock_sandbox):

            result = await agent_graph.ainvoke(
                initial_state,
                config={"configurable": {"emitter": emitter, "thread_id": run_id}},
            )

            # Must terminate strictly at max_steps budget (SC-002)
            assert result["status"] == "max_steps_reached"
            assert result["step"] >= 3

    asyncio.run(_run())
