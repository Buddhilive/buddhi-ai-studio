import pytest
from app.services.rlm.budget import DepthLimitExceeded, TokenBudgetExceeded, SubcallLimitExceeded


def test_error_payload_serialization():
    err1 = DepthLimitExceeded("Depth too high")
    payload1 = err1.to_payload()
    assert payload1["error_type"] == "DepthLimitExceeded"
    assert payload1["message"] == "Depth too high"
    assert payload1["recoverable"] is True

    err2 = TokenBudgetExceeded("Snippet exceeded budget")
    payload2 = err2.to_payload()
    assert payload2["error_type"] == "TokenBudgetExceeded"

    err3 = SubcallLimitExceeded("Subcall limit reached")
    payload3 = err3.to_payload()
    assert payload3["error_type"] == "SubcallLimitExceeded"
