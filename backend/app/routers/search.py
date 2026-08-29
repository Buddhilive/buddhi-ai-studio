import logging
from fastapi import APIRouter, HTTPException, Query, status

from app.core.config import settings
from app.routers.metrics import REQUESTS
from app.schemas.search import SearchRequest, SearchResponse
from app.services.search_service import (
    SearxngError,
    SearxngTimeoutError,
    SearxngUnavailableError,
    searxng_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["search"])


def _track_request(status_code: str) -> None:
    if settings.enable_prometheus_metrics:
        try:
            REQUESTS.labels(endpoint="/v1/search", status=status_code).inc()
        except Exception:
            pass


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Search web via SearXNG",
    description="Execute a web search using the self-hosted SearXNG search engine.",
)
async def search_get(
    q: str = Query(..., min_length=1, description="Search query"),
    max_results: int = Query(5, ge=1, le=50, description="Maximum number of search results"),
    categories: str | None = Query(None, description="Comma-separated categories (e.g. general,it)"),
    language: str = Query("auto", description="Search language code"),
) -> SearchResponse:
    category_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else None
    try:
        response = await searxng_service.search(
            query=q,
            max_results=max_results,
            categories=category_list,
            language=language,
        )
        _track_request("200")
        logger.info(
            "Search GET executed query='%s' results=%d duration=%.2fms",
            q,
            response.total_results,
            response.search_duration_ms,
        )
        return response
    except ValueError as exc:
        _track_request("400")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (SearxngUnavailableError, SearxngTimeoutError) as exc:
        _track_request("503")
        logger.warning("Search GET unavailable for query='%s': %s", q, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Search service unavailable: {exc}",
        ) from exc
    except SearxngError as exc:
        _track_request("502")
        logger.error("Search GET error for query='%s': %s", q, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream search error: {exc}",
        ) from exc


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Search web via SearXNG (POST)",
    description="Execute a web search with structured parameters in a JSON payload.",
)
async def search_post(request: SearchRequest) -> SearchResponse:
    try:
        response = await searxng_service.search(
            query=request.query,
            max_results=request.max_results,
            categories=request.categories,
            language=request.language,
        )
        _track_request("200")
        logger.info(
            "Search POST executed query='%s' results=%d duration=%.2fms",
            request.query,
            response.total_results,
            response.search_duration_ms,
        )
        return response
    except ValueError as exc:
        _track_request("400")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (SearxngUnavailableError, SearxngTimeoutError) as exc:
        _track_request("503")
        logger.warning("Search POST unavailable for query='%s': %s", request.query, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Search service unavailable: {exc}",
        ) from exc
    except SearxngError as exc:
        _track_request("502")
        logger.error("Search POST error for query='%s': %s", request.query, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream search error: {exc}",
        ) from exc
