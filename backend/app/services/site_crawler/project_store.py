import asyncio
from datetime import datetime, timezone
import hashlib
import json
import logging
import re
import tempfile
import time
from typing import Any, AsyncIterator
import uuid
import zipfile

from app.schemas.site_crawler import (
    DataFile,
    ExtractionSchema,
    JobCounts,
    PageResult,
    ProjectManifest,
    ProjectSummary,
)
from app.services.storage_service import StorageError, storage_service

logger = logging.getLogger(__name__)


class ProjectExistsError(Exception):
    """Raised when attempting to create a project with an already existing slug."""


class ProjectNotFoundError(Exception):
    """Raised when the requested project cannot be found in storage."""


def slugify(text: str) -> str:
    cleaned = text.strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned)
    cleaned = cleaned.strip("-")
    if not cleaned:
        cleaned = "project"
    return cleaned[:64]


def url_hash(url: str) -> str:
    return hashlib.sha1(url.strip().encode("utf-8")).hexdigest()[:16]


class ProjectStore:
    def __init__(self) -> None:
        self._last_manifest_save: dict[str, float] = {}
        self._lock = asyncio.Lock()

    def get_manifest_key(self, slug: str) -> str:
        return f"{slug}/project.json"

    def get_schema_key(self, slug: str) -> str:
        return f"{slug}/schema.json"

    def get_data_key(self, slug: str) -> str:
        return f"{slug}/data.json"

    def get_raw_key(self, slug: str, hash_val: str) -> str:
        return f"{slug}/raw/{hash_val}.md"

    def get_record_key(self, slug: str, hash_val: str) -> str:
        return f"{slug}/records/{hash_val}.json"

    async def create_project(
        self,
        bucket: str,
        project_name: str,
        schema: ExtractionSchema,
        settings_dict: dict[str, Any],
        urls: list[str],
        model_id: str | None = None,
    ) -> ProjectManifest:
        slug = slugify(project_name)
        manifest_key = self.get_manifest_key(slug)

        if await storage_service.exists(bucket, manifest_key):
            raise ProjectExistsError(
                f"Project with slug '{slug}' already exists in bucket '{bucket}'."
            )

        now = datetime.now(timezone.utc).isoformat()
        job_id = str(uuid.uuid4())

        pages = [
            PageResult(
                url=u,
                hash=url_hash(u),
                crawl_status="pending",
                extraction_status="pending",
            )
            for u in urls
        ]

        manifest = ProjectManifest(
            name=project_name,
            slug=slug,
            bucket=bucket,
            job_id=job_id,
            created_at=now,
            updated_at=now,
            status="queued",
            settings=settings_dict,
            counts=JobCounts(total=len(urls)),
            pages=pages,
            model_id=model_id,
        )

        await storage_service.put_json(bucket, self.get_schema_key(slug), schema.model_dump())
        await storage_service.put_json(bucket, manifest_key, manifest.model_dump())
        return manifest

    async def save_manifest(
        self, bucket: str, manifest: ProjectManifest, force: bool = False
    ) -> None:
        key = self.get_manifest_key(manifest.slug)
        manifest_id = f"{bucket}/{manifest.slug}"
        now_ts = time.monotonic()

        if not force:
            last = self._last_manifest_save.get(manifest_id, 0.0)
            if now_ts - last < 1.0:
                return

        manifest.updated_at = datetime.now(timezone.utc).isoformat()
        await storage_service.put_json(bucket, key, manifest.model_dump())
        self._last_manifest_save[manifest_id] = now_ts

    async def save_raw(
        self,
        bucket: str,
        slug: str,
        hash_val: str,
        markdown: str,
        meta: dict[str, Any],
    ) -> None:
        key = self.get_raw_key(slug, hash_val)
        frontmatter = "---\n"
        for k, v in meta.items():
            frontmatter += f"{k}: {json.dumps(v)}\n"
        frontmatter += "---\n\n"
        full_content = frontmatter + markdown
        await storage_service.put_text(bucket, key, full_content)

    async def save_records(
        self,
        bucket: str,
        slug: str,
        hash_val: str,
        records: list[dict[str, Any]],
    ) -> None:
        key = self.get_record_key(slug, hash_val)
        await storage_service.put_json(bucket, key, records)

    async def load_manifest(self, bucket: str, slug: str) -> ProjectManifest | None:
        key = self.get_manifest_key(slug)
        data = await storage_service.get_json(bucket, key)
        if not data:
            return None
        return ProjectManifest.model_validate(data)

    async def load_schema(self, bucket: str, slug: str) -> ExtractionSchema | None:
        key = self.get_schema_key(slug)
        data = await storage_service.get_json(bucket, key)
        if not data:
            return None
        return ExtractionSchema.model_validate(data)

    async def load_data(self, bucket: str, slug: str) -> DataFile | None:
        key = self.get_data_key(slug)
        data = await storage_service.get_json(bucket, key)
        if not data:
            return None
        return DataFile.model_validate(data)

    async def rebuild_data_json(
        self, bucket: str, slug: str, schema: ExtractionSchema, manifest: ProjectManifest
    ) -> DataFile:
        records_prefix = f"{slug}/records/"
        record_keys = await storage_service.list_keys(bucket, records_prefix)

        all_records: list[dict[str, Any]] = []
        for r_key in record_keys:
            try:
                page_records = await storage_service.get_json(bucket, r_key)
                if isinstance(page_records, list):
                    all_records.extend(page_records)
            except Exception as exc:
                logger.warning("Failed to read records from %s: %s", r_key, exc)

        data_file = DataFile(
            project={
                "name": manifest.name,
                "slug": manifest.slug,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "status": manifest.status,
            },
            schema=schema,
            records=all_records,
        )

        await storage_service.put_json(bucket, self.get_data_key(slug), data_file.model_dump())
        return data_file

    async def list_projects(self, bucket: str) -> list[ProjectSummary]:
        prefixes = await storage_service.list_prefixes(bucket)
        summaries: list[ProjectSummary] = []

        for prefix in prefixes:
            slug = prefix.rstrip("/")
            manifest = await self.load_manifest(bucket, slug)
            if manifest:
                summaries.append(
                    ProjectSummary(
                        name=manifest.name,
                        slug=manifest.slug,
                        bucket=manifest.bucket,
                        created_at=manifest.created_at,
                        status=manifest.status,
                        counts=manifest.counts,
                    )
                )

        summaries.sort(key=lambda p: p.created_at, reverse=True)
        return summaries

    async def load_page_detail(
        self, bucket: str, slug: str, hash_val: str
    ) -> dict[str, Any] | None:
        raw_key = self.get_raw_key(slug, hash_val)
        record_key = self.get_record_key(slug, hash_val)

        raw_text = await storage_service.get_text(bucket, raw_key)
        records = await storage_service.get_json(bucket, record_key) or []

        if raw_text is None and not records:
            return None

        markdown = raw_text or ""
        meta: dict[str, Any] = {}
        if markdown.startswith("---\n"):
            parts = markdown.split("---\n", 2)
            if len(parts) >= 3:
                for line in parts[1].splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        try:
                            meta[k.strip()] = json.loads(v.strip())
                        except Exception:
                            meta[k.strip()] = v.strip()
                markdown = parts[2].lstrip()

        return {
            "markdown": markdown,
            "meta": meta,
            "records": records,
        }

    async def delete_project(self, bucket: str, slug: str) -> int:
        prefix = f"{slug}/"
        return await storage_service.delete_prefix(bucket, prefix)

    async def stream_zip(
        self, bucket: str, slug: str, chunk_size: int = 65536
    ) -> AsyncIterator[bytes]:
        prefix = f"{slug}/"
        keys = await storage_service.list_keys(bucket, prefix)
        if not keys:
            raise ProjectNotFoundError(f"Project '{slug}' not found or empty.")

        spooled = tempfile.SpooledTemporaryFile(max_size=32 * 1024 * 1024)

        def _build_zip():
            with zipfile.ZipFile(spooled, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                client = storage_service._get_sync_client()
                for key in keys:
                    rel_name = key[len(prefix) :]
                    if not rel_name:
                        continue
                    try:
                        res = client.get_object(Bucket=bucket, Key=key)
                        data = res["Body"].read()
                        zf.writestr(rel_name, data)
                    except Exception as exc:
                        logger.warning("Failed to include %s in zip: %s", key, exc)

        await asyncio.to_thread(_build_zip)
        spooled.seek(0)

        while True:
            chunk = await asyncio.to_thread(spooled.read, chunk_size)
            if not chunk:
                break
            yield chunk

        spooled.close()


project_store = ProjectStore()
