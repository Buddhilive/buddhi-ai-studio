import json
from unittest.mock import MagicMock

from app.services.rlm.bridge import RlmSpoolBridge
from app.services.rlm.budget import RlmBudgetTracker


def test_bridge_handle_single_query_success():
    mock_gen = MagicMock(return_value=("Summary of function", "Thoughts"))
    mock_count = MagicMock(return_value=120)

    bridge = RlmSpoolBridge(generate_fn=mock_gen, count_tokens_fn=mock_count)
    tracker = RlmBudgetTracker(max_depth=2, max_subcalls=10, per_subcall_token_budget=2048)

    payload = {
        "req_id": "test-1",
        "type": "query",
        "snippet": "def foo(): pass",
        "subtask": "Explain foo",
        "depth": 1,
    }

    res = bridge.handle_request_payload_sync(payload, tracker)
    assert res["status"] == "success"
    assert res["result"] == "Summary of function"
    assert res["req_id"] == "test-1"

    assert tracker.subcall_count == 1
    assert tracker.total_input_tokens == 120
    assert tracker.total_output_tokens == 120


def test_bridge_handle_batch_query():
    mock_gen = MagicMock(side_effect=[("Res 1", ""), ("Res 2", "")])
    mock_count = MagicMock(return_value=50)

    bridge = RlmSpoolBridge(generate_fn=mock_gen, count_tokens_fn=mock_count, concurrency=2)
    tracker = RlmBudgetTracker(max_depth=2, max_subcalls=10)

    payload = {
        "req_id": "batch-1",
        "type": "batch_query",
        "items": [
            {"snippet": "chunk1", "subtask": "task1"},
            {"snippet": "chunk2", "subtask": "task2"},
        ],
        "depth": 1,
    }

    res = bridge.handle_request_payload_sync(payload, tracker)
    assert res["status"] == "success"
    assert res["results"] == ["Res 1", "Res 2"]
    assert tracker.subcall_count == 2


def test_bridge_handles_budget_exceeded():
    mock_gen = MagicMock(return_value=("Ok", ""))
    mock_count = MagicMock(return_value=3000)

    bridge = RlmSpoolBridge(generate_fn=mock_gen, count_tokens_fn=mock_count)
    tracker = RlmBudgetTracker(per_subcall_token_budget=2048)

    payload = {
        "req_id": "err-1",
        "type": "query",
        "snippet": "very long snippet...",
        "subtask": "summarize",
        "depth": 1,
    }

    res = bridge.handle_request_payload_sync(payload, tracker)
    assert res["status"] == "error"
    assert "exceeds per-subcall budget" in res["error"]
    assert res["error_payload"]["error_type"] == "TokenBudgetExceeded"
    assert tracker.subcall_count == 0


def test_bridge_unknown_request_type():
    bridge = RlmSpoolBridge()
    tracker = RlmBudgetTracker()
    res = bridge.handle_request_payload_sync({"type": "invalid_action"}, tracker)
    assert res["status"] == "error"
    assert "Unknown request type" in res["error"]
