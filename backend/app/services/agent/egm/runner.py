from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, AsyncGenerator

from app.core import settings_store
from app.core.config import settings
from app.schemas.chat import ChatMessage
from app.services.agent.egm.loader import load_persona, load_standard
from app.services.inference_service import inference_engine_manager

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GoldfishReviewInput:
    persona_id: str
    standard_name: str
    target_document: str
    target_range_name: str = "full"
    permitted_context: str = ""
    line_start: int = 1
    line_end: int = 1


@dataclass(frozen=True)
class GoldfishVerifyInput:
    spec_contract: str
    git_diff: str
    test_output: str
    target_scope_files: tuple[str, ...] = ()


@dataclass
class ReviewerOutput:
    persona: str
    stage: str
    status: str  # "completed" | "not run"
    raw_content: str
    findings: list[dict[str, Any]]
    retried: bool = False


class GoldfishRunner:
    """Stateless, zero-context Goldfish execution runner."""

    def __init__(self, concurrency: int = 1) -> None:
        self.concurrency = max(1, concurrency)
        self._semaphore = asyncio.Semaphore(self.concurrency)

    def calculate_token_budget(self) -> int:
        """Calculate maximum tokens for reviewer input target slice."""
        inf_settings = settings_store.get_inference_settings()
        max_num = int(inf_settings.get("max_num_token", settings.chat_max_num_tokens))
        rlm_settings = settings_store.get_rlm_settings()
        reserve = int(rlm_settings.get("prompt_reserve_tokens", 2048))
        budget = max(2048, max_num - reserve - settings.chat_max_tokens_default)
        return budget

    def slice_target_document(self, content: str, budget_tokens: int | None = None) -> list[tuple[int, int, str]]:
        """Slice large document into line-anchored chunks if exceeding budget."""
        budget = budget_tokens or self.calculate_token_budget()
        char_budget = budget * 4  # ~4 chars per token estimate

        if len(content) <= char_budget:
            lines = content.splitlines()
            return [(1, len(lines), content)]

        # Slice along line boundaries
        lines = content.splitlines()
        chunks: list[tuple[int, int, str]] = []
        current_lines: list[str] = []
        start_line = 1
        current_chars = 0

        for idx, line in enumerate(lines, start=1):
            current_lines.append(line)
            current_chars += len(line) + 1
            if current_chars >= char_budget:
                chunks.append((start_line, idx, "\n".join(current_lines)))
                current_lines = []
                current_chars = 0
                start_line = idx + 1

        if current_lines:
            chunks.append((start_line, len(lines), "\n".join(current_lines)))

        return chunks

    def build_review_messages(self, inp: GoldfishReviewInput, chunk_content: str, start_l: int, end_l: int) -> list[ChatMessage]:
        """Construct isolated zero-context prompt. Never accesses chat history."""
        persona_prompt = load_persona(inp.persona_id)
        standard_rubric = load_standard(inp.standard_name)

        system_prompt = (
            f"{persona_prompt}\n\n"
            f"=== EVALUATION STANDARD / RUBRIC ===\n"
            f"{standard_rubric}\n\n"
            f"CRITICAL: Report findings in standard markdown format with severity: 🔴 Blocker, 🟡 Major, or 🟢 Nit.\n"
            f"Always cite affected line numbers and concise rationale."
        )

        user_content = (
            f"### TARGET SPECIFICATION DOCUMENT SLICE (Lines {start_l}-{end_l})\n"
            f"```markdown\n{chunk_content}\n```\n"
        )
        if inp.permitted_context:
            user_content += f"\n### PERMITTED CODEBASE/SYSTEM CONTEXT\n{inp.permitted_context}\n"

        return [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_content),
        ]

    async def run_single_reviewer(
        self,
        inp: GoldfishReviewInput,
        stage: str,
        model_id: str = "gemma-4-e4b",
    ) -> ReviewerOutput:
        """Run an isolated reviewer with 1 automatic retry on failure."""
        chunks = self.slice_target_document(inp.target_document)
        combined_findings: list[dict[str, Any]] = []
        combined_raw: list[str] = []
        success = False
        retried = False

        async with self._semaphore:
            for attempt in range(2):
                try:
                    for start_l, end_l, chunk_text in chunks:
                        messages = self.build_review_messages(inp, chunk_text, start_l, end_l)
                        # Zero-context assertion check
                        assert len(messages) == 2
                        assert messages[0].role == "system"
                        assert messages[1].role == "user"

                        output_parts: list[str] = []
                        async for delta in inference_engine_manager.generate_stream(
                            messages=messages,
                            max_tokens=settings.chat_max_tokens_default,
                            enable_thinking=False,
                            model_id=model_id,
                            tools=None,
                        ):
                            if delta.content:
                                output_parts.append(delta.content)

                        raw_text = "".join(output_parts)
                        combined_raw.append(raw_text)

                    success = True
                    break
                except Exception as exc:
                    logger.warning("Goldfish reviewer '%s' attempt %d failed: %s", inp.persona_id, attempt + 1, exc)
                    retried = True
                    if attempt == 0:
                        await asyncio.sleep(0.5)

        if not success:
            logger.error("Goldfish reviewer '%s' failed after retry. Setting status to 'not run'.", inp.persona_id)
            return ReviewerOutput(
                persona=inp.persona_id,
                stage=stage,
                status="not run",
                raw_content="",
                findings=[],
                retried=True,
            )

        return ReviewerOutput(
            persona=inp.persona_id,
            stage=stage,
            status="completed",
            raw_content="\n\n".join(combined_raw),
            findings=combined_findings,
            retried=retried,
        )

    def build_verify_messages(self, inp: GoldfishVerifyInput) -> list[ChatMessage]:
        """Construct isolated zero-context verification prompt."""
        verifier_persona = load_persona("implementation_readiness")
        standard_rubric = load_standard("implementation-readiness-standard")

        system_prompt = (
            f"{verifier_persona}\n\n"
            f"=== GOLDFISH VERIFIER MANDATE ===\n"
            f"You are the Zero-Context Goldfish Implementation Verifier.\n"
            f"Compare the implemented Git Diff and Test Output against the Spec Contract and Target Scope & File Boundary.\n\n"
            f"Standard Rubric:\n{standard_rubric}\n\n"
            f"RULES:\n"
            f"1. You MUST conclude with exactly 'VERDICT: pass', 'VERDICT: retry', or 'VERDICT: continue' on its own line.\n"
            f"2. If ANY file modified in the git diff is outside Target Scope & File Boundary, you MUST emit a 🔴 Blocker finding and verdict MUST be 'retry'.\n"
            f"3. If tests failed or output is missing, verdict MUST be 'retry'.\n"
            f"4. Do NOT hallucinate prior conversation history."
        )

        user_content = (
            f"### APPROVED SPECIFICATION CONTRACT & TARGET SCOPE\n"
            f"Approved Target Scope Files: {list(inp.target_scope_files)}\n\n"
            f"{inp.spec_contract}\n\n"
            f"### SANDBOX GIT DIFF\n"
            f"```diff\n{inp.git_diff}\n```\n\n"
            f"### SANDBOX TEST OUTPUT\n"
            f"```text\n{inp.test_output}\n```\n"
        )

        return [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_content),
        ]
