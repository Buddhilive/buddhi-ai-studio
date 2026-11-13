from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


class RlmLimitError(Exception):
    """Base class for RLM budget and limit errors."""
    def to_payload(self) -> dict[str, Any]:
        return {
            "error_type": self.__class__.__name__,
            "message": str(self),
            "recoverable": True,
        }


class DepthLimitExceeded(RlmLimitError):
    """Raised when recursive depth exceeds maximum allowed."""


class TokenBudgetExceeded(RlmLimitError):
    """Raised when snippet or subtask exceeds per-call token budget."""


class SubcallLimitExceeded(RlmLimitError):
    """Raised when total number of subcalls in a task exceeds limit."""


class WallClockTimeoutExceeded(RlmLimitError):
    """Raised when task run exceeds wall-clock timeout."""


@dataclass
class RlmBudgetTelemetry:
    subcall_count: int
    max_depth_reached: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    elapsed_seconds: float
    exceeded_limit: str | None = None


@dataclass
class RlmBudgetTracker:
    max_depth: int = 2
    max_subcalls: int = 32
    per_subcall_token_budget: int = 2048
    wall_clock_timeout_s: float = 300.0

    subcall_count: int = 0
    max_depth_observed: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    started_at: float = field(default_factory=time.monotonic)
    exceeded_limit: str | None = None

    def check_depth(self, depth: int) -> None:
        """Validates recursion depth."""
        if depth > self.max_depth_observed:
            self.max_depth_observed = depth

        if depth > self.max_depth:
            self.exceeded_limit = "max_depth"
            raise DepthLimitExceeded(
                f"Requested recursion depth {depth} exceeds maximum limit of {self.max_depth}."
            )

    def check_subcall(self, current_depth: int = 1) -> None:
        """Validates timeout, subcall count, and depth before executing a subcall."""
        elapsed = time.monotonic() - self.started_at
        if elapsed > self.wall_clock_timeout_s:
            self.exceeded_limit = "wall_clock_timeout"
            raise WallClockTimeoutExceeded(
                f"Task exceeded wall-clock timeout of {self.wall_clock_timeout_s:.1f}s (elapsed: {elapsed:.1f}s)."
            )

        self.check_depth(current_depth)

        if self.subcall_count >= self.max_subcalls:
            self.exceeded_limit = "max_subcalls"
            raise SubcallLimitExceeded(
                f"Maximum subcall limit ({self.max_subcalls}) reached."
            )

    def record_subcall(self, input_tokens: int, output_tokens: int, current_depth: int = 1) -> None:
        """Records subcall completion and increments counters."""
        self.subcall_count += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        if current_depth > self.max_depth_observed:
            self.max_depth_observed = current_depth

    def validate_snippet_tokens(self, token_count: int) -> None:
        """Validates that a snippet does not exceed the per-subcall token budget."""
        if token_count > self.per_subcall_token_budget:
            self.exceeded_limit = "token_budget"
            raise TokenBudgetExceeded(
                f"Snippet has {token_count} tokens, which exceeds per-subcall budget of {self.per_subcall_token_budget}."
            )

    def get_telemetry(self) -> RlmBudgetTelemetry:
        """Returns snapshot of current budget usage."""
        elapsed = time.monotonic() - self.started_at
        return RlmBudgetTelemetry(
            subcall_count=self.subcall_count,
            max_depth_reached=self.max_depth_observed,
            total_input_tokens=self.total_input_tokens,
            total_output_tokens=self.total_output_tokens,
            total_tokens=self.total_input_tokens + self.total_output_tokens,
            elapsed_seconds=round(elapsed, 2),
            exceeded_limit=self.exceeded_limit,
        )
