from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class RlmReachEstimate:
    context_window: int
    usable_window: int
    snippet_tokens: int
    fan_out: int
    max_depth: int
    max_subcalls: int
    effective_reach_tokens: int
    bounded_by_budget: bool


def compute_fan_out(usable_window: int, snippet_tokens: int) -> int:
    """Computes how many snippets can fit in the model's usable context window."""
    if snippet_tokens <= 0:
        return 1
    return max(1, usable_window // snippet_tokens)


def compute_effective_reach(
    context_window: int,
    snippet_tokens: int = 2048,
    max_depth: int = 2,
    max_subcalls: int = 32,
    prompt_reserve_tokens: int = 2048,
) -> RlmReachEstimate:
    """
    Estimates the effective token reach of Recursive Language Modeling.
    Formula:
      usable_window = max(512, context_window - prompt_reserve_tokens)
      fan_out = usable_window // snippet_tokens
      unbounded_reach = usable_window * (fan_out ** max_depth) if max_depth > 0 else usable_window
      budget_bound = max_subcalls * snippet_tokens
      effective_reach = min(unbounded_reach, budget_bound) if max_depth > 0 else usable_window
    """
    usable_window = max(512, context_window - prompt_reserve_tokens)
    fan_out = compute_fan_out(usable_window, snippet_tokens)

    if max_depth <= 0:
        effective_reach = usable_window
        bounded = False
    else:
        # Fan-out expansion across tree recursion
        # At depth d, we can theoretically summarize fan_out^d snippets of size snippet_tokens
        theoretical_reach = (fan_out**max_depth) * snippet_tokens
        budget_bound = max_subcalls * snippet_tokens

        if theoretical_reach > budget_bound:
            effective_reach = budget_bound
            bounded = True
        else:
            effective_reach = theoretical_reach
            bounded = False

    return RlmReachEstimate(
        context_window=context_window,
        usable_window=usable_window,
        snippet_tokens=snippet_tokens,
        fan_out=fan_out,
        max_depth=max_depth,
        max_subcalls=max_subcalls,
        effective_reach_tokens=effective_reach,
        bounded_by_budget=bounded,
    )
