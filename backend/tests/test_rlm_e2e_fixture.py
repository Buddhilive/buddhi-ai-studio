import os
from pathlib import Path
from unittest.mock import MagicMock

from app.services.rlm.bridge import RlmSpoolBridge
from app.services.rlm.budget import RlmBudgetTracker


def test_rlm_e2e_fixture_chunking_and_query_flow(tmp_path: Path):
    # Create fixture files representing a large codebase
    repo_dir = tmp_path / "large_repo"
    repo_dir.mkdir()

    # Generate 5 modules of 1,000 lines each (~250k chars / ~60k tokens)
    for i in range(1, 6):
        mod_file = repo_dir / f"module_{i}.py"
        lines = [f"# Line {j}: Sample implementation details for module {i}\ndef func_{i}_{j}(): return {j}" for j in range(1000)]
        mod_file.write_text("\n".join(lines), encoding="utf-8")

    # Target file holding the critical answer
    secret_file = repo_dir / "security.py"
    secret_file.write_text(
        "# Authentication module\nTOKEN_SECRET = 'buddhi-local-2026'\ndef verify_token(t): return t == TOKEN_SECRET\n",
        encoding="utf-8",
    )

    # In-sandbox helper chunking test
    from app.services.rlm.helpers_src import RLM_HELPERS_CODE
    namespace: dict = {}
    exec(RLM_HELPERS_CODE, namespace)
    chunk_file = namespace["chunk_file"]
    grep_repo = namespace["grep_repo"]

    # 1. Test grep_repo finds target
    matches = grep_repo("TOKEN_SECRET", root_dir=str(repo_dir))
    assert len(matches) >= 1
    assert any("security.py" in m["file"] for m in matches)

    # 2. Test chunk_file
    chunks = chunk_file(str(repo_dir / "module_1.py"), max_chars=4000)
    assert len(chunks) > 5

    # 3. Test subcall batch processing through RlmSpoolBridge
    mock_gen = MagicMock(return_value=("Analyzed module slice: functions defined successfully", "Thoughts"))
    bridge = RlmSpoolBridge(generate_fn=mock_gen, count_tokens_fn=lambda t: len(t) // 4)
    tracker = RlmBudgetTracker(max_depth=2, max_subcalls=32, per_subcall_token_budget=2048)

    # Process first 4 chunks
    batch_items = [{"snippet": c["content"], "subtask": "Summarize functions"} for c in chunks[:4]]
    batch_req = {
        "req_id": "fixture-batch-1",
        "type": "batch_query",
        "items": batch_items,
        "depth": 1,
    }

    res = bridge.handle_request_payload_sync(batch_req, tracker)
    assert res["status"] == "success"
    assert len(res["results"]) == 4
    assert tracker.subcall_count == 4
    assert tracker.max_depth_observed == 1
    assert tracker.exceeded_limit is None
