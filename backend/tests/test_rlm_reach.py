import pytest
from app.services.rlm.reach import compute_effective_reach, compute_fan_out


def test_compute_fan_out():
    assert compute_fan_out(14336, 2048) == 7
    assert compute_fan_out(4000, 2048) == 1
    assert compute_fan_out(1000, 2048) == 1
    assert compute_fan_out(1000, 0) == 1


def test_compute_effective_reach_depth_zero():
    est = compute_effective_reach(context_window=16384, max_depth=0)
    assert est.max_depth == 0
    assert est.effective_reach_tokens == 14336
    assert not est.bounded_by_budget


def test_compute_effective_reach_depth_two_budget_bound():
    # 16384 window - 2048 reserve = 14336 usable.
    # fan_out = 7.
    # 7^2 * 2048 = 49 * 2048 = 100,352 tokens.
    # max_subcalls = 32 -> budget bound = 32 * 2048 = 65,536 tokens.
    est = compute_effective_reach(
        context_window=16384,
        snippet_tokens=2048,
        max_depth=2,
        max_subcalls=32,
    )
    assert est.fan_out == 7
    assert est.effective_reach_tokens == 65536
    assert est.bounded_by_budget is True


def test_compute_effective_reach_higher_budget():
    # max_subcalls = 128 -> budget bound = 128 * 2048 = 262,144 tokens.
    # theoretical reach = 49 * 2048 = 100,352 tokens -> not bounded.
    est = compute_effective_reach(
        context_window=16384,
        snippet_tokens=2048,
        max_depth=2,
        max_subcalls=128,
    )
    assert est.fan_out == 7
    assert est.effective_reach_tokens == 100352
    assert est.bounded_by_budget is False


def test_compute_effective_reach_small_window():
    # 4000 window - 2048 = 1952 usable.
    # fan_out = 1952 // 2048 = 1.
    # theoretical reach = 1^2 * 2048 = 2048 tokens.
    est = compute_effective_reach(
        context_window=4000,
        snippet_tokens=2048,
        max_depth=2,
        max_subcalls=32,
    )
    assert est.fan_out == 1
    assert est.effective_reach_tokens == 2048
    assert est.bounded_by_budget is False
