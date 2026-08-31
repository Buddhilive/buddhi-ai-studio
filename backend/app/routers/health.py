from fastapi import APIRouter

from app.services.sandbox_service import sandbox_service
from app.services.search_service import searxng_service

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    search_health = await searxng_service.check_health()
    search_info: dict[str, str] = {
        "status": search_health.status,
        "service": search_health.service,
        "base_url": search_health.base_url,
    }
    if search_health.error:
        search_info["error"] = search_health.error

    sandbox_health = await sandbox_service.check_health()
    sandbox_info: dict[str, str | int | bool] = {
        "status": sandbox_health.status,
        "server_connected": sandbox_health.server_connected,
        "server_url": sandbox_health.server_url,
        "active_sessions_count": sandbox_health.active_sessions_count,
    }
    if sandbox_health.error:
        sandbox_info["error"] = sandbox_health.error

    return {
        "status": "ok",
        "search": search_info,
        "sandbox": sandbox_info,
    }
