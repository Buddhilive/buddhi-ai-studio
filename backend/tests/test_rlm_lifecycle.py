from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from app.core.config import settings
from app.schemas.sandbox import SandboxSessionCreateRequest
from app.services.rlm.session import RlmSessionManager
from app.services.sandbox_service import ActiveSession, SandboxService


def test_rlm_session_manager_create_and_terminate():
    mock_service = MagicMock()
    mock_resp = MagicMock()
    mock_resp.session_id = "test-rlm-session-abc"
    mock_service.create_session = AsyncMock(return_value=mock_resp)
    mock_service.write_session_file = AsyncMock()
    mock_service.terminate_session = AsyncMock(return_value=True)

    manager = RlmSessionManager(service=mock_service)

    import asyncio
    async def _test():
        async with await manager.create_session() as session:
            assert session.session_id == "test-rlm-session-abc"
            mock_service.create_session.assert_called_once()
            call_arg = mock_service.create_session.call_args[0][0]
            assert isinstance(call_arg, SandboxSessionCreateRequest)
            assert call_arg.purpose == "rlm"
            assert call_arg.memory_limit_mb == settings.sandbox_rlm_memory_mb
            mock_service.write_session_file.assert_called_once_with(
                "test-rlm-session-abc",
                "rlm_helpers.py",
                mock_service.write_session_file.call_args[0][2],
            )

        # On exit, terminate_session MUST be called
        mock_service.terminate_session.assert_called_once_with("test-rlm-session-abc")

    asyncio.run(_test())


def test_active_session_rlm_expiration_ttl():
    now = datetime.now(timezone.utc)
    mock_sandbox = MagicMock()

    # General session: timeout 1800s -> not expired after 400s
    gen_session = ActiveSession(
        session_id="gen-1",
        sandbox=mock_sandbox,
        runtime_image="python:3.11-slim",
        created_at=now - timedelta(seconds=400),
        last_activity_at=now - timedelta(seconds=400),
        timeout_s=1800,
        allow_network=False,
        purpose="general",
    )
    assert gen_session.is_expired() is False

    # RLM session: timeout 1800s, but rlm_idle_ttl_s is 300s -> expired after 400s!
    rlm_session = ActiveSession(
        session_id="rlm-1",
        sandbox=mock_sandbox,
        runtime_image="python:3.11-slim",
        created_at=now - timedelta(seconds=400),
        last_activity_at=now - timedelta(seconds=400),
        timeout_s=1800,
        allow_network=False,
        purpose="rlm",
    )
    assert rlm_session.is_expired() is True
