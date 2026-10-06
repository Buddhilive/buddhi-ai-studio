import logging
import re
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.model_catalog import DEFAULT_CHAT_MODEL_ID
from app.schemas.site_crawler import (
    CreateJobRequest,
    DiscoverRequest,
    DiscoverResponse,
    JobStatus,
    ProjectManifest,
    ProjectSummary,
    SiteCrawlerHealth,
)
from app.services.crawl_service import crawl_service
from app.services.model_download_service import model_download_manager
from app.services.site_crawler.jobs import site_crawler_jobs
from app.services.site_crawler.project_store import (
    ProjectExistsError,
    ProjectNotFoundError,
    project_store,
)
from app.services.storage_service import (
    StorageError,
    StorageUnavailableError,
    storage_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/tools/site-crawler", tags=["site-crawler"])


@router.get(
    "/health",
    response_model=SiteCrawlerHealth,
    summary="Check Site Crawler readiness",
    description="Check health of Crawl4AI, RustFS, and local chat model availability.",
)
async def get_site_crawler_health() -> SiteCrawlerHealth:
    crawl_health = await crawl_service.check_health()
    storage_health = await storage_service.check_health()
    avail = model_download_manager.check_availability(DEFAULT_CHAT_MODEL_ID)

    c4a_ok = crawl_health.status == "healthy"
    store_ok = storage_health.status == "healthy"
    model_ok = avail.available

    return SiteCrawlerHealth(
        crawl4ai=c4a_ok,
        storage=store_ok,
        model={
            "available": model_ok,
            "model_id": DEFAULT_CHAT_MODEL_ID,
            "path": avail.path,
        },
        ready=c4a_ok and store_ok and model_ok,
    )


from app.services.site_crawler.discovery import discover_all


@router.post(
    "/discover",
    response_model=DiscoverResponse,
    summary="Discover site URLs via sitemaps and links",
    description="Scan robots.txt, sitemaps, and internal links to discover same-domain pages.",
)
async def discover_site_urls(request: DiscoverRequest) -> DiscoverResponse:
    try:
        return await discover_all(request.roots, ignore_robots=request.ignore_robots)
    except Exception as exc:
        logger.exception("URL discovery failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Discovery failed: {exc}",
        ) from exc


@router.post(
    "/jobs",
    response_model=JobStatus,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a new Site Crawler extraction job",
    description="Queue an asynchronous extraction run across specified URLs.",
)
async def create_crawler_job(request: CreateJobRequest) -> JobStatus:
    # Health checks before start
    c_health = await crawl_service.check_health()
    if c_health.status != "healthy":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Crawl4AI service is unavailable: {c_health.error or 'offline'}",
        )

    s_health = await storage_service.check_health()
    if s_health.status != "healthy":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"RustFS storage service is unavailable: {s_health.error or 'offline'}",
        )

    target_model = request.model_id or DEFAULT_CHAT_MODEL_ID
    avail = model_download_manager.check_availability(target_model)
    if not avail.available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Chat model '{target_model}' is not downloaded. Please download it from Models > Download Model.",
        )

    try:
        return await site_crawler_jobs.create_job(request)
    except ProjectExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except StorageUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Storage unavailable: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Failed to start site crawler job: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start crawler job: {exc}",
        ) from exc


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatus,
    summary="Get status of Site Crawler job",
    description="Poll current progress and counts of an ongoing or completed job.",
)
async def get_crawler_job_status(
    job_id: str,
    bucket: str = Query(default=settings.site_crawler_default_bucket),
) -> JobStatus:
    status_obj = await site_crawler_jobs.get_status(job_id, bucket=bucket)
    if not status_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )
    return status_obj


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=JobStatus,
    summary="Cancel a running Site Crawler job",
    description="Signal cancellation to a running job. Partial results will be preserved.",
)
async def cancel_crawler_job(job_id: str) -> JobStatus:
    canceled = await site_crawler_jobs.cancel(job_id)
    if not canceled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found or cannot be cancelled.",
        )
    return canceled


@router.get(
    "/projects",
    response_model=list[ProjectSummary],
    summary="List Site Crawler projects",
    description="List all past and present crawler projects in the specified bucket.",
)
async def list_projects(
    bucket: str = Query(default=settings.site_crawler_default_bucket),
) -> list[ProjectSummary]:
    try:
        return await project_store.list_projects(bucket)
    except StorageUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Storage service unavailable: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list projects: {exc}",
        ) from exc


@router.get(
    "/projects/{slug}",
    summary="Get project detail",
    description="Retrieve manifest, schema, and extracted records for a project.",
)
async def get_project_detail(
    slug: str,
    bucket: str = Query(default=settings.site_crawler_default_bucket),
):
    if not re.match(r"^[a-z0-9-]{1,64}$", slug):
        raise HTTPException(status_code=400, detail="Invalid project slug format.")

    manifest = await project_store.load_manifest(bucket, slug)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found.")

    schema = await project_store.load_schema(bucket, slug)
    data = await project_store.load_data(bucket, slug)

    return {
        "manifest": manifest,
        "schema": schema,
        "records": data.records if data else [],
    }


@router.delete(
    "/projects/{slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project",
    description="Remove all project files and folders from the bucket.",
)
async def delete_project(
    slug: str,
    bucket: str = Query(default=settings.site_crawler_default_bucket),
):
    if not re.match(r"^[a-z0-9-]{1,64}$", slug):
        raise HTTPException(status_code=400, detail="Invalid project slug format.")

    manifest = await project_store.load_manifest(bucket, slug)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found.")

    if manifest.status == "running":
        raise HTTPException(status_code=409, detail="Cannot delete a running project. Cancel it first.")

    await project_store.delete_project(bucket, slug)
    return None


@router.get(
    "/projects/{slug}/data",
    summary="Download project data.json",
    description="Download the consolidated structured JSON dataset.",
)
async def download_project_data(
    slug: str,
    bucket: str = Query(default=settings.site_crawler_default_bucket),
):
    if not re.match(r"^[a-z0-9-]{1,64}$", slug):
        raise HTTPException(status_code=400, detail="Invalid project slug format.")

    data_key = project_store.get_data_key(slug)
    try:
        content_iter = storage_service.iter_object_bytes(bucket, data_key)
        filename = f"{slug}-data.json"
        return StreamingResponse(
            content_iter,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Dataset for '{slug}' not found: {exc}") from exc


@router.get(
    "/projects/{slug}/zip",
    summary="Download project zip archive",
    description="Stream the entire project directory (raw markdown, manifest, records, data.json) as a zip.",
)
async def download_project_zip(
    slug: str,
    bucket: str = Query(default=settings.site_crawler_default_bucket),
):
    if not re.match(r"^[a-z0-9-]{1,64}$", slug):
        raise HTTPException(status_code=400, detail="Invalid project slug format.")

    try:
        zip_iter = project_store.stream_zip(bucket, slug)
        filename = f"{slug}.zip"
        return StreamingResponse(
            zip_iter,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate zip: {exc}") from exc


@router.get(
    "/projects/{slug}/pages/{hash_val}",
    summary="Get raw page markdown and extracted records",
    description="Inspect raw scraped markdown and per-page extraction records.",
)
async def get_project_page_detail(
    slug: str,
    hash_val: str,
    bucket: str = Query(default=settings.site_crawler_default_bucket),
):
    if not re.match(r"^[a-z0-9-]{1,64}$", slug):
        raise HTTPException(status_code=400, detail="Invalid project slug format.")
    if not re.match(r"^[a-f0-9]{16}$", hash_val):
        raise HTTPException(status_code=400, detail="Invalid hash format.")

    detail = await project_store.load_page_detail(bucket, slug, hash_val)
    if not detail:
        raise HTTPException(status_code=404, detail="Page details not found.")
    return detail
