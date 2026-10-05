import asyncio
from datetime import datetime, timezone
import logging
import time
from typing import Any
import uuid

import httpx

from app.core.config import settings
from app.schemas.crawl import (
    CrawlBatchRequest,
    CrawlHealthStatus,
    CrawlJobResponse,
    CrawlRequest,
    CrawlResult,
)

logger = logging.getLogger(__name__)


class CrawlError(Exception):
    """Base exception for Crawl4AI service failures."""


class CrawlUnavailableError(CrawlError):
    """Raised when Crawl4AI service container cannot be reached."""


class CrawlTimeoutError(CrawlError):
    """Raised when Crawl4AI operation exceeds configured timeout."""


class CrawlService:
    def __init__(
        self,
        base_url: str | None = None,
        api_token: str | None = None,
        timeout_s: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.crawl4ai_base_url).rstrip("/")
        self.api_token = api_token or settings.crawl4ai_api_token
        self.timeout_s = timeout_s or settings.crawl4ai_timeout_s
        self._client: httpx.AsyncClient | None = None
        self._jobs: dict[str, CrawlJobResponse] = {}
        self._lock = asyncio.Lock()

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": "Buddhi-AI-Studio/1.0",
            "Content-Type": "application/json",
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    async def start(self) -> None:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_s, connect=5.0),
                follow_redirects=True,
                headers=self._get_headers(),
            )
            logger.info("CrawlService started with base_url=%s", self.base_url)

    async def stop(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
            logger.info("CrawlService client closed")

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_s, connect=5.0),
                follow_redirects=True,
                headers=self._get_headers(),
            )
        return self._client

    async def check_health(self) -> CrawlHealthStatus:
        client = self._get_client()
        health_url = f"{self.base_url}/health"
        start_time = time.perf_counter()
        try:
            res = await client.get(health_url, timeout=5.0)
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            if res.is_success:
                data = res.json() if res.content else {}
                version = data.get("version") or data.get("app_version")
                return CrawlHealthStatus(
                    status="healthy",
                    service_url=self.base_url,
                    version=version,
                    latency_ms=round(latency_ms, 2),
                )
            return CrawlHealthStatus(
                status="unhealthy",
                service_url=self.base_url,
                latency_ms=round(latency_ms, 2),
                error=f"HTTP {res.status_code}: {res.text[:200]}",
            )
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return CrawlHealthStatus(
                status="unhealthy",
                service_url=self.base_url,
                latency_ms=round(latency_ms, 2),
                error=f"Connection failed: {exc}",
            )
        except httpx.TimeoutException as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return CrawlHealthStatus(
                status="unhealthy",
                service_url=self.base_url,
                latency_ms=round(latency_ms, 2),
                error=f"Health probe timed out: {exc}",
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return CrawlHealthStatus(
                status="unhealthy",
                service_url=self.base_url,
                latency_ms=round(latency_ms, 2),
                error=str(exc),
            )

    async def crawl(self, request: CrawlRequest) -> CrawlResult:
        client = self._get_client()
        crawl_url = f"{self.base_url}/crawl"
        start_time = time.perf_counter()

        # Build payload matching Crawl4AI REST specification
        crawler_config: dict[str, Any] = {
            "browser_config": {
                "headless": True,
            },
            "page_options": {
                "only_main_content": request.only_main_content,
            },
        }

        if request.css_selector:
            crawler_config["css_selector"] = request.css_selector
        if request.wait_for:
            crawler_config["wait_for"] = request.wait_for
        if request.js_code:
            crawler_config["js_code"] = request.js_code
        if request.bypass_cache:
            crawler_config["bypass_cache"] = True

        payload = {
            "urls": [request.url],
            "crawler_config": crawler_config,
        }

        req_timeout = float(request.timeout_s) if request.timeout_s else self.timeout_s

        try:
            response = await client.post(
                crawl_url,
                json=payload,
                timeout=req_timeout,
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            if response.status_code == 401 or response.status_code == 403:
                raise CrawlUnavailableError("Crawl4AI authentication failed. Check CRAWL4AI_API_TOKEN.")
            response.raise_for_status()
            data = response.json()

            # Parse returned result item
            res_item: dict[str, Any] = {}
            if isinstance(data, list) and len(data) > 0:
                res_item = data[0]
            elif isinstance(data, dict):
                if "results" in data and isinstance(data["results"], list) and len(data["results"]) > 0:
                    res_item = data["results"][0]
                elif "result" in data and isinstance(data["result"], dict):
                    res_item = data["result"]
                else:
                    res_item = data

            # Extract markdown from primary or secondary fields
            markdown = (
                res_item.get("markdown")
                or res_item.get("fit_markdown")
                or res_item.get("markdown_v2")
                or res_item.get("extracted_content")
                or ""
            )
            title = res_item.get("title") or res_item.get("page_title") or ""
            html_content = res_item.get("html") or res_item.get("cleaned_html")
            status_code = int(res_item.get("status_code") or res_item.get("status") or 200)

            # Extract link and media counts
            links = res_item.get("links") or res_item.get("internal_links") or []
            media = res_item.get("media") or res_item.get("images") or []
            links_count = len(links) if isinstance(links, list) else int(res_item.get("links_count", 0))
            media_count = len(media) if isinstance(media, list) else int(res_item.get("media_count", 0))

            return CrawlResult(
                url=request.url,
                status="completed",
                title=str(title),
                markdown=str(markdown),
                html=str(html_content) if html_content else None,
                status_code=status_code,
                links_count=links_count,
                media_count=media_count,
                execution_duration_ms=round(elapsed_ms, 2),
            )

        except httpx.TimeoutException as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            logger.warning("Crawl4AI crawl timed out for %s: %s", request.url, exc)
            return CrawlResult(
                url=request.url,
                status="timeout",
                title="",
                markdown="",
                status_code=504,
                links_count=0,
                media_count=0,
                execution_duration_ms=round(elapsed_ms, 2),
                error=f"Crawl operation timed out after {req_timeout}s",
            )
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            logger.warning("Failed to connect to Crawl4AI at %s: %s", self.base_url, exc)
            raise CrawlUnavailableError(f"Crawl4AI service is unavailable at {self.base_url}: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error("Crawl4AI returned HTTP error %d: %s", exc.response.status_code, exc)
            raise CrawlError(f"Crawl4AI returned error HTTP {exc.response.status_code}: {exc.response.text[:200]}") from exc

    async def create_job(self, request: CrawlBatchRequest) -> CrawlJobResponse:
        job_id = str(uuid.uuid4())
        job = CrawlJobResponse(
            job_id=job_id,
            status="pending",
            created_at=datetime.now(timezone.utc),
            total_urls=len(request.urls),
            completed_urls=0,
            results=[],
        )
        async with self._lock:
            self._jobs[job_id] = job

        # Launch background processing task
        asyncio.create_task(self._process_job(job_id, request))
        return job

    async def _process_job(self, job_id: str, request: CrawlBatchRequest) -> None:
        async with self._lock:
            if job_id not in self._jobs:
                return
            self._jobs[job_id].status = "processing"

        results: list[CrawlResult] = []
        for url in request.urls:
            req = CrawlRequest(
                url=url,
                css_selector=request.css_selector,
                only_main_content=request.only_main_content,
                wait_for=request.wait_for,
                bypass_cache=request.bypass_cache,
                timeout_s=request.timeout_s,
            )
            try:
                res = await self.crawl(req)
                results.append(res)
            except Exception as exc:
                results.append(
                    CrawlResult(
                        url=url,
                        status="failed",
                        title="",
                        markdown="",
                        status_code=500,
                        links_count=0,
                        media_count=0,
                        execution_duration_ms=0.0,
                        error=str(exc),
                    )
                )
            async with self._lock:
                if job_id in self._jobs:
                    self._jobs[job_id].completed_urls = len(results)

        async with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].status = "completed"
                self._jobs[job_id].completed_at = datetime.now(timezone.utc)
                self._jobs[job_id].results = results

    async def get_job(self, job_id: str) -> CrawlJobResponse | None:
        async with self._lock:
            return self._jobs.get(job_id)


crawl_service = CrawlService()
