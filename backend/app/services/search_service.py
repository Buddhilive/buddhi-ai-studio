import html
import logging
import re
import time
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.search import SearchHealthStatus, SearchRequest, SearchResponse, SearchResultItem

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(raw: str) -> str:
    if not raw:
        return ""
    # Strip HTML tags and unescape entities
    text = _TAG_RE.sub("", raw)
    text = html.unescape(text)
    return " ".join(text.split())


class SearxngError(Exception):
    """Base exception for SearXNG communication failures."""


class SearxngUnavailableError(SearxngError):
    """Raised when SearXNG service cannot be reached."""


class SearxngTimeoutError(SearxngError):
    """Raised when SearXNG query times out."""


class SearxngService:
    def __init__(self, base_url: str | None = None, timeout_s: float | None = None) -> None:
        self.base_url = (base_url or settings.searxng_base_url).rstrip("/")
        self.timeout_s = timeout_s or settings.searxng_timeout_s
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_s, connect=3.0),
                follow_redirects=True,
                headers={"User-Agent": "Buddhi-AI-Studio/1.0"},
            )

    async def stop(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_s, connect=3.0),
                follow_redirects=True,
                headers={"User-Agent": "Buddhi-AI-Studio/1.0"},
            )
        return self._client

    async def search(
        self,
        query: str,
        max_results: int = 5,
        categories: list[str] | None = None,
        language: str = "auto",
    ) -> SearchResponse:
        q = query.strip()
        if not q:
            raise ValueError("Query string cannot be empty.")

        client = self._get_client()
        params: dict[str, Any] = {
            "q": q,
            "format": "json",
            "language": language,
        }
        if categories:
            params["categories"] = ",".join(categories)

        search_url = f"{self.base_url}/search"
        start_time = time.perf_counter()

        try:
            response = await client.get(search_url, params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            logger.warning("SearXNG request timed out: %s", exc)
            raise SearxngTimeoutError(f"Search request to SearXNG timed out after {self.timeout_s}s.") from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            logger.warning("Failed to connect to SearXNG at %s: %s", self.base_url, exc)
            raise SearxngUnavailableError(f"SearXNG search service is unavailable at {self.base_url}.") from exc
        except httpx.HTTPStatusError as exc:
            logger.warning("SearXNG returned HTTP error %d: %s", exc.response.status_code, exc)
            raise SearxngError(f"SearXNG returned error HTTP {exc.response.status_code}: {exc.response.text}") from exc
        except Exception as exc:
            logger.exception("Unexpected error querying SearXNG: %s", exc)
            raise SearxngError(f"Unexpected error querying SearXNG: {exc}") from exc

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        raw_results = data.get("results", []) if isinstance(data, dict) else []
        items: list[SearchResultItem] = []

        for item in raw_results[:max_results]:
            title = _clean_text(item.get("title", ""))
            url = item.get("url", "")
            raw_snippet = item.get("content") or item.get("snippet") or ""
            snippet = _clean_text(raw_snippet)

            if not url:
                continue

            items.append(
                SearchResultItem(
                    title=title,
                    url=url,
                    snippet=snippet,
                    published_date=item.get("publishedDate"),
                    engine=item.get("engine"),
                    score=item.get("score"),
                )
            )

        return SearchResponse(
            query=q,
            results=items,
            total_results=len(items),
            search_duration_ms=round(duration_ms, 2),
        )

    async def check_health(self) -> SearchHealthStatus:
        client = self._get_client()
        try:
            resp = await client.get(
                f"{self.base_url}/search",
                params={"q": "ping", "format": "json"},
                timeout=httpx.Timeout(3.0, connect=2.0),
            )
            if resp.status_code == 200:
                return SearchHealthStatus(status="healthy", base_url=self.base_url)
            return SearchHealthStatus(
                status="degraded",
                base_url=self.base_url,
                error=f"HTTP {resp.status_code}: {resp.text[:100]}",
            )
        except Exception as exc:
            return SearchHealthStatus(
                status="unavailable",
                base_url=self.base_url,
                error=str(exc),
            )


searxng_service = SearxngService()
