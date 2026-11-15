from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.build_project_service import BuildProjectService
from app.services.build_project_storage import BuildProjectStorage


def test_build_project_storage_crud_and_history(tmp_path):
    db_file = tmp_path / "build_projects.duckdb"
    storage = BuildProjectStorage(db_path=db_file)

    created = storage.create_project(
        project_id="demo-proj-1",
        name="Demo Project",
        description="A test project",
        template="nextjs-vibe",
        db_dialect="sqlite",
        runtime_image="buddhilive/vibe-sandbox:latest",
        active_session_id="sess_1",
    )
    assert created["id"] == "demo-proj-1"
    assert created["db_dialect"] == "sqlite"
    assert created["active_session_id"] == "sess_1"

    listed = storage.list_projects()
    assert len(listed) == 1
    assert listed[0]["name"] == "Demo Project"

    storage.save_history(
        "demo-proj-1",
        messages=[{"id": "m1", "role": "user", "parts": [{"type": "text", "text": "hello"}]}],
        trajectory_events=[{"event": "run.start", "seq": 1}],
    )
    history = storage.get_history("demo-proj-1")
    assert len(history["messages"]) == 1
    assert history["messages"][0]["id"] == "m1"
    assert len(history["trajectory_events"]) == 1

    # Verify persistence across fresh storage instance
    reopened = BuildProjectStorage(db_path=db_file)
    assert reopened.get_project("demo-proj-1") is not None
    assert len(reopened.get_history("demo-proj-1")["messages"]) == 1

    assert reopened.delete_project("demo-proj-1") is True
    assert reopened.get_project("demo-proj-1") is None
    assert reopened.get_history("demo-proj-1")["messages"] == []


async def test_start_or_restore_reuses_live_session_and_restores_expired(tmp_path):
    storage = BuildProjectStorage(db_path=tmp_path / "build.duckdb")
    service = BuildProjectService(storage=storage, local_dir=tmp_path / "local_projects")

    storage.create_project(
        project_id="proj-restore",
        name="Restore Test",
        description="",
        template="python-blank",
        db_dialect="postgresql",
        runtime_image="buddhilive/vibe-sandbox:latest",
        active_session_id="sess_live",
    )

    live_sess = MagicMock()
    live_sess.is_expired.return_value = False

    with patch("app.services.build_project_service.sandbox_service") as mock_sb, patch(
        "app.services.build_project_service.storage_service"
    ) as mock_s3:
        mock_sb.get_session = AsyncMock(return_value=live_sess)
        res_live = await service.start_or_restore_project("proj-restore")
        assert res_live.session_id == "sess_live"
        assert res_live.hydrated_from == "active_session"

        # Now simulate expired session + persisted file in RustFS
        mock_sb.get_session = AsyncMock(return_value=None)
        mock_sb.create_session = AsyncMock(return_value=SimpleNamespace(session_id="sess_new"))
        mock_sb.write_session_file = AsyncMock(return_value=True)
        mock_s3.list_keys = AsyncMock(
            return_value=[
                "proj-restore/files/main.py",
                "proj-restore/files/node_modules/pkg/index.js",
            ]
        )
        mock_s3.get_text = AsyncMock(return_value="print('restored')\n")

        res_restored = await service.start_or_restore_project("proj-restore")
        assert res_restored.session_id == "sess_new"
        assert res_restored.hydrated_from == "snapshot"
        assert res_restored.restored_files_count == 1
        mock_sb.write_session_file.assert_awaited_once_with(
            "sess_new", "main.py", "print('restored')\n"
        )


def test_build_files_rejects_path_traversal():
    client = TestClient(app)

    res_write = client.put(
        "/v1/build/projects/valid_proj_1/files",
        json={"path": "../etc/passwd", "content": "x"},
    )
    assert res_write.status_code in (400, 422)

    res_read = client.get("/v1/build/projects/valid_proj_1/files/..%2F..%2Fetc%2Fshadow")
    assert res_read.status_code in (400, 404, 422)

    res_bad_id = client.get("/v1/build/projects/bad$id/files")
    assert res_bad_id.status_code == 422
