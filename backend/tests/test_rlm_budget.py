import pytest
import time
from app.services.rlm.budget import (
    DepthLimitExceeded,
    RlmBudgetTracker,
    SubcallLimitExceeded,
    TokenBudgetExceeded,
    WallClockTimeoutExceeded,
)


def test_budget_depth_limit():
    tracker = RlmBudgetTracker(max_depth=2)
    tracker.check_depth(1)
    tracker.check_depth(2)
    with pytest.raises(DepthLimitExceeded) as exc_info:
        tracker.check_depth(3)
    assert "exceeds maximum limit of 2" in str(exc_info.value)
    assert tracker.exceeded_limit == "max_depth"


def test_budget_subcall_limit():
    tracker = RlmBudgetTracker(max_subcalls=3)
    for _ in range(3):
        tracker.check_subcall()
        tracker.record_subcall(input_tokens=100, output_tokens=50)

    assert tracker.subcall_count == 3
    with pytest.raises(SubcallLimitExceeded):
        tracker.check_subcall()


def test_budget_snippet_token_limit():
    tracker = RlmBudgetTracker(per_subcall_token_budget=2048)
    tracker.validate_snippet_tokens(1024)
    with pytest.raises(TokenBudgetExceeded):
        tracker.validate_snippet_tokens(2049)


def test_budget_wall_clock_timeout():
    tracker = RlmBudgetTracker(wall_clock_timeout_s=0.05)
    time.sleep(0.06)
    with pytest.raises(WallClockTimeoutExceeded):
        tracker.check_subcall()


def test_budget_telemetry():
    tracker = RlmBudgetTracker(max_depth=2, max_subcalls=10)
    tracker.record_subcall(input_tokens=500, output_tokens=100, current_depth=1)
    tracker.record_subcall(input_tokens=400, output_tokens=80, current_depth=2)
    telemetry = tracker.get_telemetry()

    assert telemetry.subcall_count == 2
    assert telemetry.max_depth_reached == 2
    assert telemetry.total_input_tokens == 900
    assert telemetry.total_output_tokens == 180
    assert telemetry.total_tokens == 1080
    assert telemetry.elapsed_seconds >= 0.0
