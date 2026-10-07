import pytest
from unittest.mock import AsyncMock, patch
import httpx
from pydantic import ValidationError

from app.schemas.crawl import CrawlRequest, validate_crawl_url
from app.services.crawl_service import (
    CrawlError,
    CrawlService,
    CrawlTimeoutError,
    CrawlUnavailableError,
)


def test_validate_crawl_url_allowed():
    assert validate_crawl_url("https://example.com") == "https://example.com"
    assert validate_crawl_url("http://docs.crawl4ai.com/page") == "http://docs.crawl4ai.com/page"


def test_validate_crawl_url_blocked_ssrf():
    with pytest.raises(ValueError, match="(?i)requests to local address"):
        validate_crawl_url("http://localhost:8080")

    with pytest.raises(ValueError, match="(?i)requests to local address"):
        validate_crawl_url("http://127.0.0.1/admin")

    with pytest.raises(ValueError, match="(?i)requests to private/internal IP"):
        validate_crawl_url("http://192.168.1.50/secret")

    with pytest.raises(ValueError, match="(?i)requests to private/internal IP"):
        validate_crawl_url("http://10.0.0.1/")

    with pytest.raises(ValueError, match="Invalid URL scheme"):
        validate_crawl_url("ftp://example.com/file.txt")



@pytest.mark.asyncio
async def test_crawl_service_success():
    service = CrawlService(base_url="http://mock-crawl4ai:11235", api_token="test-token", timeout_s=10.0)

    mock_crawl_response = {
        "results": [
            {
                "url": "https://example.com",
                "title": "Example Domain",
                "markdown": "# Example Domain\n\nThis domain is for use in illustrative examples.",
                "html": "<html><body><h1>Example Domain</h1></body></html>",
                "status_code": 200,
                "links": [{"href": "https://iana.org"}],
                "media": [],
            }
        ]
    }

    mock_resp = httpx.Response(
        200,
        json=mock_crawl_response,
        request=httpx.Request("POST", "http://mock-crawl4ai:11235/crawl"),
    )

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        req = CrawlRequest(url="https://example.com", only_main_content=True)
        res = await service.crawl(req)

        assert res.status == "completed"
        assert res.url == "https://example.com"
        assert res.title == "Example Domain"
        assert "Example Domain" in res.markdown
        assert res.status_code == 200
        assert res.links_count == 1
        assert res.media_count == 0
        assert res.execution_duration_ms >= 0


@pytest.mark.asyncio
async def test_crawl_service_timeout():
    service = CrawlService(base_url="http://mock-crawl4ai:11235", api_token="test-token", timeout_s=2.0)

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Crawl timed out")
        req = CrawlRequest(url="https://example.com")
        res = await service.crawl(req)

        assert res.status == "timeout"
        assert res.status_code == 504
        assert "timed out" in res.error.lower()


@pytest.mark.asyncio
async def test_crawl_service_connection_failure():
    service = CrawlService(base_url="http://mock-crawl4ai:11235", api_token="test-token", timeout_s=5.0)

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")
        req = CrawlRequest(url="https://example.com")
        with pytest.raises(CrawlUnavailableError):
            await service.crawl(req)


@pytest.mark.asyncio
async def test_crawl_service_check_health():
    service = CrawlService(base_url="http://mock-crawl4ai:11235")
    mock_resp = httpx.Response(
        200,
        json={"status": "ok", "version": "0.9.4"},
        request=httpx.Request("GET", "http://mock-crawl4ai:11235/health"),
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        health = await service.check_health()
        assert health.status == "healthy"
        assert health.version == "0.9.4"
        assert health.service_url == "http://mock-crawl4ai:11235"


def test_crawl_router_endpoints():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # 1. Test invalid / SSRF URL
    resp = client.post("/v1/crawl", json={"url": "http://127.0.0.1/evil"})
    assert resp.status_code == 422 or resp.status_code == 400

    # 2. Test successful crawl endpoint with mock
    mock_result = {
        "results": [
            {
                "url": "https://example.com",
                "title": "Example Page",
                "markdown": "# Header\nContent",
                "html": "<html></html>",
                "status_code": 200,
                "links": [],
                "media": [],
            }
        ]
    }
    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = httpx.Response(200, json=mock_result, request=httpx.Request("POST", "http://mock/crawl"))
        res = client.post("/v1/crawl", json={"url": "https://example.com", "only_main_content": True})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "completed"
        assert data["title"] == "Example Page"
        assert "# Header" in data["markdown"]

    # 3. Test health check endpoint with mock
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json={"status": "ok"}, request=httpx.Request("GET", "http://mock/health"))
        res = client.get("/v1/crawl/health")
        assert res.status_code == 200
        assert res.json()["status"] == "healthy"

