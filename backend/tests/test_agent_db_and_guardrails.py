from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.sandbox import SandboxExecutionResult
from app.services.agent.harness.models import ProvisionedDatabase
from app.services.agent.tools import ToolGuardrailContext, execute_tool


@pytest.mark.asyncio
async def test_guardrail_blocks_pages_router_and_banned_packages() -> None:
    status, out, code, _ = await execute_tool(
        "write_file",
        {"path": "pages/index.tsx", "content": "export default function Home() { return null; }"},
        session_id="sess_1",
    )
    assert status == "error"
    assert code == 1
    assert "App Router" in out

    status2, out2, code2, _ = await execute_tool(
        "write_file",
        {"path": "tailwind.config.js", "content": "module.exports = {}"},
        session_id="sess_1",
    )
    assert status2 == "error"
    assert code2 == 1
    assert "Tailwind CSS v4" in out2

    status3, out3, code3, _ = await execute_tool(
        "run_command",
        {"command": "npm install prisma @prisma/client"},
        session_id="sess_1",
    )
    assert status3 == "error"
    assert code3 == 1
    assert "drizzle-orm" in out3

    status4, out4, code4, _ = await execute_tool(
        "write_file",
        {"path": "package.json", "content": '{"dependencies": {"next-auth": "^4.0.0"}}'},
        session_id="sess_1",
    )
    assert status4 == "error"
    assert code4 == 1
    assert "blocked" in out4


@pytest.mark.asyncio
async def test_provision_postgres_db_identifier_sanitization() -> None:
    status, out, code, _ = await execute_tool(
        "provision_postgres_db",
        {"db_name": "app; DROP DATABASE postgres;--"},
        session_id="sess_1",
        guardrail_ctx=ToolGuardrailContext(workspace_id="ws_1"),
    )
    assert status == "error"
    assert code == 1
    assert "Identifier validation error" in out


@pytest.mark.asyncio
async def test_provision_postgres_db_idempotent_and_masked_env() -> None:
    import sys
    import types

    mock_cursor = MagicMock()
    mock_cursor.execute = AsyncMock()
    mock_cursor.fetchone = AsyncMock(side_effect=[None, None])
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=None)

    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()
    mock_conn.cursor = MagicMock(return_value=mock_cursor)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    fake_psycopg = types.ModuleType("psycopg")
    fake_async_conn = MagicMock()
    fake_async_conn.connect = AsyncMock(return_value=mock_conn)
    fake_psycopg.AsyncConnection = fake_async_conn

    fake_sql = types.ModuleType("psycopg.sql")
    fake_sql.Identifier = lambda x: x
    fake_sql.Literal = lambda x: x
    fake_sql.SQL = lambda s: MagicMock(format=lambda *a: s)
    fake_psycopg.sql = fake_sql

    with (
        patch.dict(sys.modules, {"psycopg": fake_psycopg, "psycopg.sql": fake_sql}),
        patch("app.services.agent.vibe_tools.sandbox_service.read_session_file", new=AsyncMock(side_effect=FileNotFoundError)),
        patch("app.services.agent.vibe_tools.sandbox_service.write_session_file", new=AsyncMock(return_value=True)) as mock_write,
        patch("app.services.agent.harness.storage.harness_storage_service.upsert_provisioned_database") as mock_upsert,
    ):
        status, out, code, _ = await execute_tool(
            "provision_postgres_db",
            {"db_name": "my_vibe_app", "dialect": "postgresql"},
            session_id="sess_1",
            guardrail_ctx=ToolGuardrailContext(workspace_id="ws_pg_1"),
        )

    assert status == "completed"
    assert code == 0
    assert "buddhi_app_my_vibe_app" in out
    assert "[REDACTED]" in out
    assert mock_write.called
    env_written = mock_write.call_args.args[2]
    assert "DB_DIALECT=postgresql" in env_written
    assert "BETTER_AUTH_SECRET=" in env_written
    assert mock_upsert.called


@pytest.mark.asyncio
async def test_provision_sqlite_and_query_database() -> None:
    sqlite_res = SandboxExecutionResult(
        status="completed",
        stdout='{"columns": ["name"], "rows": [["user"]]}',
        stderr="",
        exit_code=0,
        execution_time_ms=15.0,
    )
    with (
        patch("app.services.agent.vibe_tools.sandbox_service.read_session_file", new=AsyncMock(return_value="")),
        patch("app.services.agent.vibe_tools.sandbox_service.write_session_file", new=AsyncMock(return_value=True)),
        patch("app.services.agent.harness.storage.harness_storage_service.upsert_provisioned_database"),
    ):
        status, out, code, _ = await execute_tool(
            "provision_postgres_db",
            {"dialect": "sqlite"},
            session_id="sess_1",
            guardrail_ctx=ToolGuardrailContext(workspace_id="ws_sq_1"),
        )
    assert status == "completed"
    assert code == 0
    assert "DB_DIALECT=sqlite" in out

    with patch("app.services.agent.vibe_tools.sandbox_service.execute_in_session", new=AsyncMock(return_value=sqlite_res)):
        q_status, q_out, q_code, _ = await execute_tool(
            "query_database",
            {"sql": "SELECT name FROM sqlite_master WHERE type='table'", "dialect": "sqlite"},
            session_id="sess_1",
            guardrail_ctx=ToolGuardrailContext(workspace_id="ws_sq_1"),
        )
    assert q_status == "completed"
    assert q_code == 0
    assert '"user"' in q_out


@pytest.mark.asyncio
async def test_query_database_postgres_blocks_privileged_and_enforces_workspace() -> None:
    status, out, code, _ = await execute_tool(
        "query_database",
        {"sql": "SELECT pg_read_file('/etc/passwd')", "dialect": "postgresql"},
        session_id="sess_1",
        guardrail_ctx=ToolGuardrailContext(workspace_id="ws_1"),
    )
    assert status == "error"
    assert code == 1
    assert "Security Guardrail" in out

    with patch("app.services.agent.harness.storage.harness_storage_service.get_provisioned_database", return_value=None):
        s2, o2, c2, _ = await execute_tool(
            "query_database",
            {"sql": "SELECT 1", "dialect": "postgresql"},
            session_id="sess_1",
            guardrail_ctx=ToolGuardrailContext(workspace_id="ws_unprovisioned"),
        )
    assert s2 == "error"
    assert c2 == 1
    assert "provision_postgres_db" in o2


@pytest.mark.asyncio
async def test_drizzle_kit_deterministic_execution() -> None:
    ok_res = SandboxExecutionResult(status="completed", stdout="Changes applied", stderr="", exit_code=0, execution_time_ms=20.0)
    with patch("app.services.agent.vibe_tools.sandbox_service.execute_in_session", new=AsyncMock(return_value=ok_res)) as mock_exec:
        status, out, code, _ = await execute_tool(
            "drizzle_kit",
            {"action": "push"},
            session_id="sess_1",
            guardrail_ctx=ToolGuardrailContext(workspace_id="ws_1", spec_approved=True),
        )
    assert status == "completed"
    assert code == 0
    assert "drizzle-kit push" in mock_exec.call_args.args[1].code
