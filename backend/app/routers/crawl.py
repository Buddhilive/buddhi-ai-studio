import logging
from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.routers.metrics import REQUESTS
from app.schemas.crawl import (
    CrawlBatchRequest,
    CrawlHealthStatus,
    CrawlJobResponse,
    CrawlRequest,
    CrawlResult,
)
from app.services.crawl_service import (
    CrawlError,
    CrawlTimeoutError,
    CrawlUnavailableError,
    crawl_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["crawl"])


def _track_request(status_code: str) -> None:
    if settings.enable_prometheus_metrics:
        try:
            REQUESTS.labels(endpoint="/v1/crawl", status=status_code).inc()
        except Exception:
            pass


@router.get(
    "/crawl/health",
    response_model=CrawlHealthStatus,
    summary="Check Crawl4AI service health",
    description="Check connectivity and health of the upstream Crawl4AI container.",
)
async def get_crawl_health() -> CrawlHealthStatus:
    health = await crawl_service.check_health()
    if health.status == "unhealthy":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health.model_dump(),
        )
    return health


@router.post(
    "/crawl",
    response_model=CrawlResult,
    summary="Crawl webpage for clean LLM markdown",
    description="Crawl a single webpage using headless browser automation and extract clean markdown.",
)
async def crawl_url_endpoint(request: CrawlRequest) -> CrawlResult:
    try:
        result = await crawl_service.crawl(request)
        _track_request("200")
        logger.info(
            "Crawl executed url='%s' status=%s duration=%.2fms",
            request.url,
            result.status,
            result.execution_duration_ms,
        )
        return result
    except ValueError as exc:
        _track_request("400")
        logger.warning("Crawl invalid request url='%s': %s", request.url, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except (CrawlUnavailableError, CrawlTimeoutError) as exc:
        _track_request("503")
        logger.warning("Crawl service unavailable url='%s': %s", request.url, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Crawl service unavailable: {exc}",
        ) from exc
    except CrawlError as exc:
        _track_request("502")
        logger.error("Crawl upstream error url='%s': %s", request.url, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream crawl error: {exc}",
        ) from exc
    except Exception as exc:
        _track_request("500")
        logger.exception("Unexpected crawl error url='%s': %s", request.url, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Crawl execution failed: {exc}",
        ) from exc


@router.post(
    "/crawl/jobs",
    response_model=CrawlJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit async batch crawl job",
    description="Queue an asynchronous batch crawl job for multiple URLs.",
)
async def create_crawl_job(request: CrawlBatchRequest) -> CrawlJobResponse:
    try:
        job = await crawl_service.create_job(request)
        _track_request("202")
        logger.info("Created crawl job %s for %d urls", job.job_id, len(request.urls))
        return job
    except Exception as exc:
        _track_request("500")
        logger.exception("Failed to create crawl job: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit crawl job: {exc}",
        ) from exc


@router.get(
    "/crawl/jobs/{job_id}",
    response_model=CrawlJobResponse,
    summary="Get status of crawl job",
    description="Poll the status and retrieve results of an asynchronous crawl job.",
)
async def get_crawl_job(job_id: str) -> CrawlJobResponse:
    job = await crawl_service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Crawl job {job_id} not found.",
        )
    return job
