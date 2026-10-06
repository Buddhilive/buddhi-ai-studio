import asyncio
from datetime import datetime, timezone
import json
import logging
import time
from typing import Any, AsyncIterator
import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
import httpx

from app.core.config import settings
from app.schemas.storage import BucketInfo, StorageHealthStatus

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Base exception for storage failures."""


class StorageUnavailableError(StorageError):
    """Raised when RustFS storage service is unreachable."""


class BucketAlreadyExistsError(StorageError):
    """Raised when attempting to create a bucket that already exists."""


class StorageNotFoundError(StorageError):
    """Raised when a bucket or key is not found."""


class StorageService:
    def __init__(
        self,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        region: str | None = None,
    ) -> None:
        self.endpoint_url = (endpoint_url or settings.rustfs_endpoint_url).rstrip("/")
        self.access_key = access_key or settings.rustfs_access_key
        self.secret_key = secret_key or settings.rustfs_secret_key
        self.region = region or settings.rustfs_region
        self._s3_client: Any = None
        self._lock = asyncio.Lock()

    def _get_sync_client(self) -> Any:
        if self._s3_client is None:
            self._s3_client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                config=Config(
                    s3={"addressing_style": "path"},
                    signature_version="s3v4",
                    retries={"max_attempts": 2, "mode": "standard"},
                ),
            )
        return self._s3_client

    async def start(self) -> None:
        try:
            await self.ensure_bucket(settings.site_crawler_default_bucket)
            logger.info("StorageService initialized against %s", self.endpoint_url)
        except Exception as exc:
            logger.warning("StorageService startup warning (RustFS might be offline): %s", exc)

    async def stop(self) -> None:
        self._s3_client = None
        logger.info("StorageService stopped")

    async def check_health(self) -> StorageHealthStatus:
        start_time = time.perf_counter()
        health_url = f"{self.endpoint_url}/health"

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(2.0, connect=1.0)) as http_client:
                res = await http_client.get(health_url)
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                if res.is_success:
                    return StorageHealthStatus(
                        status="healthy",
                        service_url=self.endpoint_url,
                        latency_ms=round(latency_ms, 2),
                    )
        except Exception:
            pass

        # Fallback to S3 list_buckets probe
        try:
            client = self._get_sync_client()
            await asyncio.to_thread(client.list_buckets)
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return StorageHealthStatus(
                status="healthy",
                service_url=self.endpoint_url,
                latency_ms=round(latency_ms, 2),
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return StorageHealthStatus(
                status="unhealthy",
                service_url=self.endpoint_url,
                latency_ms=round(latency_ms, 2),
                error=str(exc),
            )

    async def list_buckets(self) -> list[BucketInfo]:
        client = self._get_sync_client()

        def _call():
            try:
                res = client.list_buckets()
                buckets: list[BucketInfo] = []
                for b in res.get("Buckets", []):
                    created_at = b.get("CreationDate")
                    created_str = (
                        created_at.isoformat()
                        if isinstance(created_at, datetime)
                        else str(created_at) if created_at else None
                    )
                    buckets.append(BucketInfo(name=b["Name"], created_at=created_str))
                return buckets
            except (BotoCoreError, ClientError) as exc:
                raise StorageUnavailableError(f"Failed to list buckets: {exc}") from exc

        return await asyncio.to_thread(_call)

    async def create_bucket(self, bucket_name: str) -> BucketInfo:
        client = self._get_sync_client()

        def _call():
            try:
                client.create_bucket(Bucket=bucket_name)
                return BucketInfo(
                    name=bucket_name,
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
            except client.exceptions.BucketAlreadyExists as exc:
                raise BucketAlreadyExistsError(f"Bucket '{bucket_name}' already exists.") from exc
            except client.exceptions.BucketAlreadyOwnedByYou:
                return BucketInfo(
                    name=bucket_name,
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in ("BucketAlreadyExists", "BucketAlreadyOwnedByYou"):
                    raise BucketAlreadyExistsError(f"Bucket '{bucket_name}' already exists.") from exc
                raise StorageError(f"Failed to create bucket '{bucket_name}': {exc}") from exc
            except BotoCoreError as exc:
                raise StorageUnavailableError(f"Failed to reach storage service: {exc}") from exc

        return await asyncio.to_thread(_call)

    async def ensure_bucket(self, bucket_name: str) -> None:
        client = self._get_sync_client()

        def _call():
            try:
                client.head_bucket(Bucket=bucket_name)
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code", "")
                if error_code in ("404", "NoSuchBucket"):
                    try:
                        client.create_bucket(Bucket=bucket_name)
                    except Exception as create_exc:
                        logger.warning("Could not create bucket %s: %s", bucket_name, create_exc)
                else:
                    logger.warning("head_bucket %s returned error: %s", bucket_name, exc)
            except Exception as exc:
                logger.warning("ensure_bucket %s check failed: %s", bucket_name, exc)

        await asyncio.to_thread(_call)

    async def put_text(
        self,
        bucket: str,
        key: str,
        text: str,
        content_type: str = "text/plain; charset=utf-8",
    ) -> None:
        client = self._get_sync_client()
        body = text.encode("utf-8")

        def _call():
            try:
                client.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=body,
                    ContentType=content_type,
                )
            except (BotoCoreError, ClientError) as exc:
                raise StorageError(f"Failed to write '{key}' to bucket '{bucket}': {exc}") from exc

        await asyncio.to_thread(_call)

    async def put_json(self, bucket: str, key: str, data: Any) -> None:
        payload = json.dumps(data, indent=2, ensure_ascii=False)
        await self.put_text(bucket, key, payload, content_type="application/json")

    async def get_text(self, bucket: str, key: str) -> str | None:
        client = self._get_sync_client()

        def _call():
            try:
                res = client.get_object(Bucket=bucket, Key=key)
                content = res["Body"].read()
                return content.decode("utf-8")
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in ("NoSuchKey", "404"):
                    return None
                raise StorageError(f"Failed to read '{key}' from bucket '{bucket}': {exc}") from exc
            except BotoCoreError as exc:
                raise StorageUnavailableError(f"Storage connection failed: {exc}") from exc

        return await asyncio.to_thread(_call)

    async def get_json(self, bucket: str, key: str) -> Any | None:
        text = await self.get_text(bucket, key)
        if text is None:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise StorageError(f"Malformed JSON in '{key}': {exc}") from exc

    async def exists(self, bucket: str, key: str) -> bool:
        client = self._get_sync_client()

        def _call():
            try:
                client.head_object(Bucket=bucket, Key=key)
                return True
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in ("NoSuchKey", "404"):
                    return False
                return False
            except BotoCoreError:
                return False

        return await asyncio.to_thread(_call)

    async def list_keys(self, bucket: str, prefix: str = "") -> list[str]:
        client = self._get_sync_client()

        def _call():
            try:
                paginator = client.get_paginator("list_objects_v2")
                keys: list[str] = []
                for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                    for obj in page.get("Contents", []):
                        keys.append(obj["Key"])
                return keys
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in ("NoSuchBucket", "404"):
                    return []
                raise StorageError(f"Failed to list keys in bucket '{bucket}': {exc}") from exc
            except BotoCoreError as exc:
                raise StorageUnavailableError(f"Storage service connection failed: {exc}") from exc

        return await asyncio.to_thread(_call)

    async def list_prefixes(self, bucket: str, prefix: str = "") -> list[str]:
        client = self._get_sync_client()

        def _call():
            try:
                paginator = client.get_paginator("list_objects_v2")
                prefixes: list[str] = []
                for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
                    for cp in page.get("CommonPrefixes", []):
                        prefixes.append(cp["Prefix"])
                return prefixes
            except Exception as exc:
                logger.warning("Failed to list prefixes in %s: %s", bucket, exc)
                return []

        return await asyncio.to_thread(_call)

    async def delete_prefix(self, bucket: str, prefix: str) -> int:
        client = self._get_sync_client()

        def _call() -> int:
            try:
                keys_to_delete = []
                paginator = client.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                    for obj in page.get("Contents", []):
                        keys_to_delete.append({"Key": obj["Key"]})

                if not keys_to_delete:
                    return 0

                deleted_count = 0
                for i in range(0, len(keys_to_delete), 1000):
                    batch = keys_to_delete[i : i + 1000]
                    res = client.delete_objects(
                        Bucket=bucket,
                        Delete={"Objects": batch, "Quiet": True},
                    )
                    deleted_count += len(batch)
                return deleted_count
            except ClientError as exc:
                raise StorageError(f"Failed to delete prefix '{prefix}' in bucket '{bucket}': {exc}") from exc
            except BotoCoreError as exc:
                raise StorageUnavailableError(f"Storage service connection failed: {exc}") from exc

        return await asyncio.to_thread(_call)

    async def iter_object_bytes(
        self, bucket: str, key: str, chunk_size: int = 65536
    ) -> AsyncIterator[bytes]:
        client = self._get_sync_client()
        try:
            res = await asyncio.to_thread(client.get_object, Bucket=bucket, Key=key)
            body = res["Body"]
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404"):
                raise StorageNotFoundError(f"Key '{key}' not found in bucket '{bucket}'.") from exc
            raise StorageError(f"Failed to read '{key}' from bucket '{bucket}': {exc}") from exc

        while True:
            chunk = await asyncio.to_thread(body.read, chunk_size)
            if not chunk:
                break
            yield chunk


storage_service = StorageService()
