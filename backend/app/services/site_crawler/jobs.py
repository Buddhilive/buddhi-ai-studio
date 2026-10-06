import asyncio
from datetime import datetime, timezone
import logging
import time
from typing import Any

from app.core.config import settings
from app.schemas.crawl import CrawlRequest
from app.schemas.site_crawler import (
    CreateJobRequest,
    ExtractionSchema,
    JobCounts,
    JobStatus,
    PageResult,
    ProjectManifest,
    RecentError,
)
from app.services.crawl_service import crawl_service
from app.services.site_crawler.extraction import extract_from_markdown
from app.services.site_crawler.project_store import (
    project_store,
    url_hash,
)
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)


class JobRunner:
    def __init__(
        self,
        manifest: ProjectManifest,
        schema: ExtractionSchema,
        crawl_options: dict[str, Any],
        model_id: str | None = None,
    ) -> None:
        self.manifest = manifest
        self.schema = schema
        self.crawl_options = crawl_options
        self.model_id = model_id
        self.cancel_event = asyncio.Event()
        self.task: asyncio.Task | None = None
        self.recent_errors: list[RecentError] = []
        self._lock = asyncio.Lock()

    def to_status(self) -> JobStatus:
        elapsed = 0.0
        if self.manifest.started_at:
            try:
                start_dt = datetime.fromisoformat(self.manifest.started_at)
                elapsed = max(
                    0.0,
                    (datetime.now(timezone.utc) - start_dt).total_seconds(),
                )
            except Exception:
                pass

        return JobStatus(
            job_id=self.manifest.job_id,
            bucket=self.manifest.bucket,
            slug=self.manifest.slug,
            status=self.manifest.status,
            counts=self.manifest.counts,
            current_url=self.manifest.current_url,
            started_at=self.manifest.started_at,
            elapsed_s=round(elapsed, 1),
            cap_applied=self.manifest.settings.get("cap_applied", False),
            recent_errors=list(self.recent_errors[-5:]),
        )

    async def run(self) -> None:
        self.manifest.status = "running"
        self.manifest.started_at = datetime.now(timezone.utc).isoformat()
        await project_store.save_manifest(self.manifest.bucket, self.manifest, force=True)

        bucket = self.manifest.bucket
        slug = self.manifest.slug

        # Queues
        crawl_queue: asyncio.Queue[PageResult] = asyncio.Queue()
        extract_queue: asyncio.Queue[tuple[PageResult, str, str | None]] = asyncio.Queue()

        for page in self.manifest.pages:
            await crawl_queue.put(page)

        concurrency = settings.site_crawler_crawl_concurrency
        semaphore = asyncio.Semaphore(concurrency)

        async def _crawl_worker():
            while not crawl_queue.empty() and not self.cancel_event.is_set():
                try:
                    page = crawl_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                if self.cancel_event.is_set():
                    page.crawl_status = "skipped"
                    page.extraction_status = "skipped"
                    crawl_queue.task_done()
                    continue

                page.crawl_status = "crawling"
                self.manifest.current_url = page.url
                await project_store.save_manifest(bucket, self.manifest)

                start_c = time.perf_counter()
                async with semaphore:
                    try:
                        req = CrawlRequest(
                            url=page.url,
                            only_main_content=self.crawl_options.get("only_main_content", True),
                            bypass_cache=self.crawl_options.get("bypass_cache", False),
                            timeout_s=self.crawl_options.get("timeout_s", 60.0),
                        )
                        c_res = await crawl_service.crawl(req)
                        page.crawl_ms = round((time.perf_counter() - start_c) * 1000.0, 2)
                        page.http_status = c_res.status_code
                        page.title = c_res.title

                        if c_res.status == "completed" and c_res.markdown:
                            page.crawl_status = "crawled"
                            self.manifest.counts.crawled += 1
                            meta = {
                                "url": page.url,
                                "title": c_res.title,
                                "status_code": c_res.status_code,
                                "crawled_at": datetime.now(timezone.utc).isoformat(),
                            }
                            await project_store.save_raw(bucket, slug, page.hash, c_res.markdown, meta)
                            await extract_queue.put((page, c_res.markdown, c_res.title))
                        else:
                            page.crawl_status = "crawl_failed"
                            page.extraction_status = "skipped"
                            page.error = c_res.error or f"Crawl failed with status {c_res.status}"
                            self.manifest.counts.failed += 1
                            self.recent_errors.append(RecentError(url=page.url, error=page.error))
                    except Exception as exc:
                        page.crawl_ms = round((time.perf_counter() - start_c) * 1000.0, 2)
                        page.crawl_status = "crawl_failed"
                        page.extraction_status = "skipped"
                        page.error = str(exc)
                        self.manifest.counts.failed += 1
                        self.recent_errors.append(RecentError(url=page.url, error=str(exc)))

                crawl_queue.task_done()
                await project_store.save_manifest(bucket, self.manifest)

        async def _extract_worker():
            extracted_since_last_rebuild = 0
            while not self.cancel_event.is_set():
                try:
                    # Wait for items or until crawl is done
                    page, markdown, title = await asyncio.wait_for(extract_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    if crawl_queue.empty() and extract_queue.empty():
                        break
                    continue

                page.extraction_status = "extracting"
                self.manifest.current_url = page.url
                await project_store.save_manifest(bucket, self.manifest)

                start_e = time.perf_counter()
                try:
                    ext_res = await extract_from_markdown(
                        markdown=markdown,
                        url=page.url,
                        title=title,
                        schema=self.schema,
                        model_id=self.model_id,
                    )
                    page.extract_ms = round((time.perf_counter() - start_e) * 1000.0, 2)
                    page.extraction_status = ext_res.status  # "ok", "empty_content", "extraction_failed"
                    page.attempts = ext_res.attempts
                    page.record_count = len(ext_res.records)

                    if ext_res.status in ("ok", "empty_content"):
                        self.manifest.counts.extracted += 1
                        self.manifest.counts.records += len(ext_res.records)
                        if ext_res.records:
                            await project_store.save_records(bucket, slug, page.hash, ext_res.records)
                    else:
                        page.error = ext_res.error
                        self.manifest.counts.failed += 1
                        self.recent_errors.append(
                            RecentError(url=page.url, error=ext_res.error or "Extraction failed")
                        )
                except Exception as exc:
                    page.extract_ms = round((time.perf_counter() - start_e) * 1000.0, 2)
                    page.extraction_status = "extraction_failed"
                    page.error = str(exc)
                    self.manifest.counts.failed += 1
                    self.recent_errors.append(RecentError(url=page.url, error=str(exc)))

                extract_queue.task_done()
                extracted_since_last_rebuild += 1

                if extracted_since_last_rebuild >= 10:
                    await project_store.rebuild_data_json(bucket, slug, self.schema, self.manifest)
                    extracted_since_last_rebuild = 0

                await project_store.save_manifest(bucket, self.manifest)

        # Run crawl workers
        crawl_tasks = [asyncio.create_task(_crawl_worker()) for _ in range(concurrency)]
        extract_task = asyncio.create_task(_extract_worker())

        await asyncio.gather(*crawl_tasks)
        await extract_task

        # Finalize
        if self.cancel_event.is_set():
            self.manifest.status = "cancelled"
        else:
            self.manifest.status = "completed"

        self.manifest.current_url = None
        self.manifest.finished_at = datetime.now(timezone.utc).isoformat()
        await project_store.rebuild_data_json(bucket, slug, self.schema, self.manifest)
        await project_store.save_manifest(bucket, self.manifest, force=True)


class SiteCrawlerJobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRunner] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, request: CreateJobRequest) -> JobStatus:
        bucket = request.bucket
        await storage_service.ensure_bucket(bucket)

        # Cap URLs
        final_urls = request.urls[: request.max_pages]
        cap_applied = len(request.urls) > request.max_pages

        settings_dict = {
            "include_patterns": request.include_patterns,
            "exclude_patterns": request.exclude_patterns,
            "max_pages": request.max_pages,
            "cap_applied": cap_applied,
            "ignore_robots": request.ignore_robots,
            "model_id": request.model_id,
            "crawl_options": request.crawl_options.model_dump(),
        }

        manifest = await project_store.create_project(
            bucket=bucket,
            project_name=request.project_name,
            schema=request.extraction_schema,
            settings_dict=settings_dict,
            urls=final_urls,
            model_id=request.model_id,
        )

        runner = JobRunner(
            manifest=manifest,
            schema=request.extraction_schema,
            crawl_options=request.crawl_options.model_dump(),
            model_id=request.model_id,
        )

        async with self._lock:
            self._jobs[manifest.job_id] = runner

        # Launch background task
        runner.task = asyncio.create_task(runner.run())
        return runner.to_status()

    async def get_status(self, job_id: str, bucket: str | None = None) -> JobStatus | None:
        async with self._lock:
            if job_id in self._jobs:
                return self._jobs[job_id].to_status()

        # Fallback to storage manifest
        target_bucket = bucket or settings.site_crawler_default_bucket
        prefixes = await storage_service.list_prefixes(target_bucket)
        for p in prefixes:
            slug = p.rstrip("/")
            manifest = await project_store.load_manifest(target_bucket, slug)
            if manifest and manifest.job_id == job_id:
                elapsed = 0.0
                if manifest.started_at:
                    try:
                        start_dt = datetime.fromisoformat(manifest.started_at)
                        end_dt = (
                            datetime.fromisoformat(manifest.finished_at)
                            if manifest.finished_at
                            else datetime.now(timezone.utc)
                        )
                        elapsed = max(0.0, (end_dt - start_dt).total_seconds())
                    except Exception:
                        pass
                return JobStatus(
                    job_id=manifest.job_id,
                    bucket=manifest.bucket,
                    slug=manifest.slug,
                    status=manifest.status,
                    counts=manifest.counts,
                    current_url=manifest.current_url,
                    started_at=manifest.started_at,
                    elapsed_s=round(elapsed, 1),
                    cap_applied=manifest.settings.get("cap_applied", False),
                    recent_errors=[],
                )
        return None

    async def cancel(self, job_id: str) -> JobStatus | None:
        async with self._lock:
            runner = self._jobs.get(job_id)

        if not runner:
            return None

        runner.cancel_event.set()
        return runner.to_status()

    async def recover_interrupted(self) -> None:
        try:
            buckets = await storage_service.list_buckets()
        except Exception as exc:
            logger.info("Storage service unavailable during startup recovery: %s", exc)
            return

        for b in buckets:
            try:
                prefixes = await storage_service.list_prefixes(b.name)
                for p in prefixes:
                    slug = p.rstrip("/")
                    manifest = await project_store.load_manifest(b.name, slug)
                    if manifest and manifest.status in ("queued", "discovering", "running"):
                        logger.warning(
                            "Recovering interrupted job %s for project %s/%s",
                            manifest.job_id,
                            b.name,
                            slug,
                        )
                        manifest.status = "interrupted"
                        manifest.finished_at = datetime.now(timezone.utc).isoformat()
                        await project_store.save_manifest(b.name, manifest, force=True)
            except Exception as exc:
                logger.warning("Error checking bucket %s for interrupted jobs: %s", b.name, exc)

    async def shutdown(self) -> None:
        async with self._lock:
            for job_id, runner in self._jobs.items():
                if runner.manifest.status == "running":
                    runner.cancel_event.set()
                    runner.manifest.status = "interrupted"
                    try:
                        await project_store.save_manifest(
                            runner.manifest.bucket, runner.manifest, force=True
                        )
                    except Exception:
                        pass


site_crawler_jobs = SiteCrawlerJobManager()
