from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.agent.harness.calibrator import HarnessCalibrator
from app.services.agent.harness.models import ExperienceEntry
from app.services.agent.harness.storage import HarnessStorageService


@pytest.mark.asyncio
async def test_experience_distillation_bounded_retention_and_pin_delete(tmp_path: Path) -> None:
    store = HarnessStorageService(db_path=str(tmp_path / "harness.duckdb"), mirror_root=tmp_path / "mirror")
    calibrator = HarnessCalibrator(storage=store, sandbox_svc=MagicMock())

    # Seed 4 unpinned entries with cap=3 -> lowest confidence evicted
    for idx, conf in enumerate([0.2, 0.9, 0.8, 0.7]):
        store.upsert_experience(
            ExperienceEntry(
                entry_id=f"exp_{idx}",
                workspace_id="ws_exp",
                task_signature=f"sig_{idx}",
                lesson=f"Lesson {idx}",
                evidence_run_id=f"run_{idx}",
                confidence_score=conf,
            ),
            max_entries=3,
        )

    active = store.get_active_experiences("ws_exp", limit=10)
    ids = {e.entry_id for e in active}
    assert len(active) == 3
    assert "exp_0" not in ids  # lowest confidence (0.2) was evicted

    # Pin and delete
    assert store.set_experience_pin("ws_exp", "exp_1", True) is True
    assert store.delete_experience("ws_exp", "exp_2") is True
    remaining = store.get_active_experiences("ws_exp", limit=10)
    assert {e.entry_id for e in remaining} == {"exp_1", "exp_3"}

    # Distill via calibrator
    async def _fake_stream(messages, **kwargs):
        yield type(
            "Delta",
            (),
            {"reasoning": "", "content": "VERDICT: pass\nRun uv run pytest -q for fast feedback."},
        )()

    with patch("app.services.agent.harness.calibrator.inference_engine_manager.generate_stream", _fake_stream):
        distilled = await calibrator.distill(
            workspace_id="ws_exp",
            run_id="run_distill",
            task_prompt="Run backend tests",
            adopted_components=["tool_guidance"],
            observations=[{"name": "run_command", "status": "completed", "exit_code": 0}],
        )

    assert "VERDICT:" not in distilled.lesson
    assert "Run uv run pytest -q" in distilled.lesson
    assert (tmp_path / "mirror" / "ws_exp" / "EXPERIENCE.md").exists()
