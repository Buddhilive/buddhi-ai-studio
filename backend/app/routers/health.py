from fastapi import APIRouter

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

    return {
        "status": "ok",
        "search": search_info,
    }
