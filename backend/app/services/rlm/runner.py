from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Callable

from app.core import settings_store
from app.schemas.chat import ChatMessage
from app.services.rlm.bridge import RlmSpoolBridge
from app.services.rlm.budget import RlmBudgetTelemetry, RlmBudgetTracker
from app.services.rlm.session import RlmSession, RlmSessionManager
from app.services.sandbox_service import sandbox_service, SandboxService

logger = logging.getLogger(__name__)

RLM_ROOT_SYSTEM_PROMPT = """You are an Autonomous Software Engineer executing under the Recursive Language Model (RLM) context scaling paradigm.
The codebase is too large to fit in your prompt. Instead, you have access to a sandboxed Python REPL environment with a helper library `rlm_helpers`.

Available helper functions in `rlm_helpers`:
- `chunk_file(path: str, max_chars: int = 7000, overlap_chars: int = 200) -> list[dict]`:
  Chunks a file into snippets bounded by token limits.
- `grep_repo(pattern: str, file_pattern: str = "*", root_dir: str = ".") -> list[dict]`:
  Fast search across the repository.
- `llm_query(snippet: str, subtask: str, depth: int = 1) -> str`:
  Executes a focused subcall query against the local LiteRT model to analyze a specific snippet.
- `llm_query_batch(items: list[dict], depth: int = 1) -> list[str]`:
  Executes parallel subcall queries on multiple snippets.

Rules:
1. Write concise Python scripts using `rlm_helpers` to inspect, grep, chunk, and summarize target modules.
2. Never try to print entire massive files into your terminal output.
3. Once you have enough context to answer the user's objective, provide the final answer clearly with the prefix:
   FINAL_ANSWER: <your synthesized conclusion or plan>
"""


@dataclass
class RlmExecutionResult:
    status: str
    final_answer: str
    telemetry: RlmBudgetTelemetry
    steps_taken: int
    error: str | None = None


class RlmTaskRunner:
    def __init__(
        self,
        sandbox_svc: SandboxService = sandbox_service,
        generate_fn: Callable[[list[ChatMessage]], Any] | None = None,
        bridge: RlmSpoolBridge | None = None,
    ) -> None:
        self.sandbox_svc = sandbox_svc
        self.session_mgr = RlmSessionManager(service=sandbox_svc)
        self.generate_fn = generate_fn
        self.bridge = bridge or RlmSpoolBridge()

    async def _default_root_generate(self, messages: list[ChatMessage]) -> str:
        from app.services.inference_service import inference_engine_manager
        ans, _ = await inference_engine_manager.generate(messages=messages)
        return ans

    async def run(
        self,
        task_prompt: str,
        max_steps: int = 8,
        repo_mount_path: str | None = None,
    ) -> RlmExecutionResult:
        """Executes an RLM task inside an ephemeral OpenSandbox session."""
        rlm_conf = settings_store.get_rlm_settings()
        budget = RlmBudgetTracker(
            max_depth=rlm_conf.get("max_depth", 2),
            max_subcalls=rlm_conf.get("max_subcalls", 32),
            per_subcall_token_budget=rlm_conf.get("snippet_tokens", 2048),
        )

        root_gen = self.generate_fn or self._default_root_generate

        session: RlmSession = await self.session_mgr.create_session(repo_mount_path=repo_mount_path)
        stop_event = asyncio.Event()
        poll_task = asyncio.create_task(
            self.bridge.poll_and_serve_session(
                self.sandbox_svc,
                session.session_id,
                budget,
                stop_event,
            )
        )

        history: list[ChatMessage] = [
            ChatMessage(role="system", content=RLM_ROOT_SYSTEM_PROMPT),
            ChatMessage(role="user", content=f"Objective: {task_prompt}\nWrite Python code to explore and analyze."),
        ]

        steps = 0
        final_answer = ""
        status = "completed"
        error_msg = None

        try:
            async with session:
                while steps < max_steps:
                    steps += 1
                    logger.debug("RLM step %d/%d", steps, max_steps)

                    # Root model generates next action/code
                    resp_text = await root_gen(history)
                    history.append(ChatMessage(role="assistant", content=resp_text))

                    if "FINAL_ANSWER:" in resp_text:
                        final_answer = resp_text.split("FINAL_ANSWER:", 1)[1].strip()
                        break

                    # Extract code block if model wrapped it in markdown
                    code_to_run = resp_text
                    if "```python" in resp_text:
                        code_to_run = resp_text.split("```python", 1)[1].split("```", 1)[0].strip()
                    elif "```" in resp_text:
                        code_to_run = resp_text.split("```", 1)[1].split("```", 1)[0].strip()

                    # Execute in sandbox
                    exec_result = await session.execute_code(code_to_run, timeout_s=45)

                    output_text = (
                        f"STDOUT:\n{exec_result.stdout}\nSTDERR:\n{exec_result.stderr}\n"
                        f"(exit_code={exec_result.exit_code})"
                    )

                    history.append(ChatMessage(
                        role="user",
                        content=f"Execution Result:\n{output_text}\nContinue analysis or conclude with FINAL_ANSWER: ...",
                    ))

                if not final_answer and steps >= max_steps:
                    final_answer = "[RLM completed max steps without explicit FINAL_ANSWER marker]"

        except Exception as exc:
            logger.exception("Error executing RLM task: %s", exc)
            status = "failed"
            error_msg = str(exc)
        finally:
            stop_event.set()
            try:
                await poll_task
            except asyncio.CancelledError:
                pass

        telemetry_data = budget.get_telemetry()

        # Emit telemetry event to metrics store
        try:
            from app.services.metrics import metrics_writer, LLMEvent
            import time, uuid
            metrics_writer.record(LLMEvent(
                request_id=f"rlm-{uuid.uuid4().hex[:8]}",
                ts=time.time(),
                model_name=rlm_conf.get("model", "gemma-4-e4b"),
                endpoint="/rlm",
                prompt_tokens=telemetry_data.total_input_tokens,
                completion_tokens=telemetry_data.total_output_tokens,
                total_tokens=telemetry_data.total_tokens,
                latency_ms=telemetry_data.elapsed_seconds * 1000,
                status=status,
                metadata={
                    "subcall_count": telemetry_data.subcall_count,
                    "max_depth_reached": telemetry_data.max_depth_reached,
                    "exceeded_limit": telemetry_data.exceeded_limit,
                    "steps_taken": steps,
                },
            ))
        except Exception as metric_err:
            logger.debug("Failed recording RLM metrics: %s", metric_err)

        return RlmExecutionResult(
            status=status,
            final_answer=final_answer,
            telemetry=telemetry_data,
            steps_taken=steps,
            error=error_msg,
        )
