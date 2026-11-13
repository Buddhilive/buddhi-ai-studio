from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine
from pathlib import Path

from opensandbox.models.filesystem import DirectoryListEntry

from app.services.rlm.budget import RlmBudgetTracker, RlmLimitError

logger = logging.getLogger(__name__)

# Default prompt wrapper for snippet subcalls
SUBTASK_SYSTEM_PROMPT = (
    "You are a precise code analysis subagent. Analyze the given code snippet according "
    "to the requested subtask. Answer clearly and concisely without unnecessary chit-chat."
)


class RlmSpoolBridge:
    def __init__(
        self,
        generate_fn: Callable[[str, str], Coroutine[Any, Any, tuple[str, str]]] | None = None,
        count_tokens_fn: Callable[[str], int] | None = None,
        concurrency: int = 2,
    ) -> None:
        self._generate_fn = generate_fn
        self._count_tokens_fn = count_tokens_fn
        self._concurrency = max(1, concurrency)
        self._semaphore: asyncio.Semaphore | None = None

    def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._concurrency)
        return self._semaphore

    async def _default_generate(self, prompt: str, system_prompt: str) -> tuple[str, str]:
        from app.services.inference_service import inference_engine_manager
        from app.schemas.chat import ChatMessage
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=prompt),
        ]
        return await inference_engine_manager.generate(messages=messages)

    def _default_count_tokens(self, text: str) -> int:
        try:
            from app.services.inference_service import inference_engine_manager
            return inference_engine_manager.count_tokens(text)
        except Exception:
            # Fallback estimation: ~4 chars per token
            return max(1, len(text) // 4)

    def generate_subcall_sync(self, prompt: str, system_prompt: str = SUBTASK_SYSTEM_PROMPT) -> tuple[str, str]:
        """Synchronous version for direct callers or test environments."""
        if self._generate_fn:
            import inspect
            res = self._generate_fn(prompt, system_prompt)
            if inspect.isawaitable(res):
                # Run coroutine manually without loopback socket
                try:
                    res.send(None)
                except StopIteration as exc:
                    return exc.value
            return res
        return ("[Mock subcall result]", "")

    async def generate_subcall(self, prompt: str, system_prompt: str = SUBTASK_SYSTEM_PROMPT) -> tuple[str, str]:
        gen = self._generate_fn or self._default_generate
        async with self._get_semaphore():
            return await gen(prompt, system_prompt)

    def handle_request_payload_sync(
        self,
        payload: dict[str, Any],
        budget_tracker: RlmBudgetTracker,
    ) -> dict[str, Any]:
        """Synchronous dispatch for spool payloads (useful in tests & sync runners)."""
        req_id = payload.get("req_id", "unknown")
        req_type = payload.get("type", "query")
        depth = int(payload.get("depth", 1))

        try:
            if req_type == "query":
                snippet = payload.get("snippet", "")
                subtask = payload.get("subtask", "")

                budget_tracker.check_subcall(current_depth=depth)
                token_count = self.count_tokens(snippet)
                budget_tracker.validate_snippet_tokens(token_count)

                prompt = f"Subtask: {subtask}\n\nCode Snippet:\n```\n{snippet}\n```"
                answer, reasoning = self.generate_subcall_sync(prompt)
                out_tokens = self.count_tokens(answer)
                budget_tracker.record_subcall(input_tokens=token_count, output_tokens=out_tokens, current_depth=depth)

                return {
                    "req_id": req_id,
                    "status": "success",
                    "result": answer,
                    "reasoning": reasoning,
                }

            elif req_type == "batch_query":
                items = payload.get("items", [])
                results = []
                for item in items:
                    snip = item.get("snippet", "")
                    task = item.get("subtask", "")
                    budget_tracker.check_subcall(current_depth=depth)
                    tokens = self.count_tokens(snip)
                    budget_tracker.validate_snippet_tokens(tokens)

                    p = f"Subtask: {task}\n\nCode Snippet:\n```\n{snip}\n```"
                    ans, _ = self.generate_subcall_sync(p)
                    out_t = self.count_tokens(ans)
                    budget_tracker.record_subcall(input_tokens=tokens, output_tokens=out_t, current_depth=depth)
                    results.append(ans)

                return {
                    "req_id": req_id,
                    "status": "success",
                    "results": results,
                }

            else:
                return {
                    "req_id": req_id,
                    "status": "error",
                    "error": f"Unknown request type '{req_type}'",
                }

        except RlmLimitError as exc:
            logger.warning("RLM budget limit hit on req %s: %s", req_id, exc)
            return {
                "req_id": req_id,
                "status": "error",
                "error": str(exc),
                "error_payload": exc.to_payload(),
            }
        except Exception as exc:
            logger.exception("Error processing RLM spool request %s: %s", req_id, exc)
            return {
                "req_id": req_id,
                "status": "error",
                "error": str(exc),
            }

    def count_tokens(self, text: str) -> int:
        counter = self._count_tokens_fn or self._default_count_tokens
        return counter(text)

    async def handle_request_payload(
        self,
        payload: dict[str, Any],
        budget_tracker: RlmBudgetTracker,
    ) -> dict[str, Any]:
        req_id = payload.get("req_id", "unknown")
        req_type = payload.get("type", "query")
        depth = int(payload.get("depth", 1))

        try:
            if req_type == "query":
                snippet = payload.get("snippet", "")
                subtask = payload.get("subtask", "")

                budget_tracker.check_subcall(current_depth=depth)
                token_count = self.count_tokens(snippet)
                budget_tracker.validate_snippet_tokens(token_count)

                prompt = f"Subtask: {subtask}\n\nCode Snippet:\n```\n{snippet}\n```"
                answer, reasoning = await self.generate_subcall(prompt)
                out_tokens = self.count_tokens(answer)
                budget_tracker.record_subcall(input_tokens=token_count, output_tokens=out_tokens, current_depth=depth)

                return {
                    "req_id": req_id,
                    "status": "success",
                    "result": answer,
                    "reasoning": reasoning,
                }

            elif req_type == "batch_query":
                items = payload.get("items", [])
                results = []

                async def _proc_item(item: dict[str, Any]) -> str:
                    snip = item.get("snippet", "")
                    task = item.get("subtask", "")
                    budget_tracker.check_subcall(current_depth=depth)
                    tokens = self.count_tokens(snip)
                    budget_tracker.validate_snippet_tokens(tokens)

                    p = f"Subtask: {task}\n\nCode Snippet:\n```\n{snip}\n```"
                    ans, _ = await self.generate_subcall(p)
                    out_t = self.count_tokens(ans)
                    budget_tracker.record_subcall(input_tokens=tokens, output_tokens=out_t, current_depth=depth)
                    return ans

                results = await asyncio.gather(*[_proc_item(it) for it in items])
                return {
                    "req_id": req_id,
                    "status": "success",
                    "results": results,
                }

            else:
                return {
                    "req_id": req_id,
                    "status": "error",
                    "error": f"Unknown request type '{req_type}'",
                }

        except RlmLimitError as exc:
            logger.warning("RLM budget limit hit on req %s: %s", req_id, exc)
            return {
                "req_id": req_id,
                "status": "error",
                "error": str(exc),
                "error_payload": exc.to_payload(),
            }
        except Exception as exc:
            logger.exception("Error processing RLM spool request %s: %s", req_id, exc)
            return {
                "req_id": req_id,
                "status": "error",
                "error": str(exc),
            }

    async def poll_and_serve_session(
        self,
        sandbox_service: Any,
        session_id: str,
        budget_tracker: RlmBudgetTracker,
        stop_event: asyncio.Event,
        poll_interval_s: float = 0.1,
    ) -> None:
        """Polls the sandbox session's .rlm_spool directory and processes requests."""
        while not stop_event.is_set():
            try:
                session = await sandbox_service.get_session(session_id)
                if not session:
                    break

                try:
                    entries = await session.sandbox.files.list_directory(
                        DirectoryListEntry(path=".rlm_spool")
                    )
                except Exception:
                    # Directory might not be created yet by in-sandbox script
                    await asyncio.sleep(poll_interval_s)
                    continue

                for entry in entries:
                    path_str = getattr(entry, "path", "")
                    file_name = Path(path_str).name
                    if file_name.startswith("req-") and file_name.endswith(".json"):
                        try:
                            raw_bytes = await session.sandbox.files.read_bytes(path_str)
                            req_data = json.loads(raw_bytes.decode("utf-8"))
                        except Exception as read_err:
                            logger.debug("Could not read spool request %s: %s", path_str, read_err)
                            continue

                        # Process request
                        response_data = await self.handle_request_payload(req_data, budget_tracker)
                        req_id = response_data.get("req_id", "unknown")
                        res_path = f".rlm_spool/res-{req_id}.json"

                        # Write response and remove request
                        try:
                            await session.sandbox.files.write_file(
                                res_path,
                                json.dumps(response_data).encode("utf-8"),
                            )
                            await session.sandbox.files.delete_files([path_str])
                        except Exception as write_err:
                            logger.warning("Failed writing spool response %s: %s", res_path, write_err)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("Error in spool poll loop: %s", exc)

            await asyncio.sleep(poll_interval_s)
