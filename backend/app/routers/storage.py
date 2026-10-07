import logging
from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.schemas.storage import (
    BucketInfo,
    BucketListResponse,
    CreateBucketRequest,
    StorageHealthStatus,
)
from app.services.storage_service import (
    BucketAlreadyExistsError,
    StorageError,
    StorageUnavailableError,
    storage_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/storage", tags=["storage"])


@router.get(
    "/health",
    response_model=StorageHealthStatus,
    summary="Check RustFS storage service health",
    description="Check connectivity and health of upstream RustFS S3-compatible service.",
)
async def get_storage_health() -> StorageHealthStatus:
    return await storage_service.check_health()


@router.get(
    "/buckets",
    response_model=BucketListResponse,
    summary="List storage buckets",
    description="List all available buckets in RustFS and provide default bucket.",
)
async def list_buckets() -> BucketListResponse:
    try:
        buckets = await storage_service.list_buckets()
        return BucketListResponse(
            buckets=buckets,
            default_bucket=settings.site_crawler_default_bucket,
        )
    except StorageUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Storage service unavailable: {exc}",
        ) from exc
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Storage upstream error: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list buckets: {exc}",
        ) from exc


@router.post(
    "/buckets",
    response_model=BucketInfo,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new storage bucket",
    description="Create an S3-compatible storage bucket in RustFS.",
)
async def create_bucket(request: CreateBucketRequest) -> BucketInfo:
    try:
        return await storage_service.create_bucket(request.name)
    except BucketAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except StorageUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Storage service unavailable: {exc}",
        ) from exc
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create bucket: {exc}",
        ) from exc
