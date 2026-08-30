import pytest
from unittest.mock import AsyncMock, patch
import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.services.search_service import (
    SearxngError,
    SearxngService,
    SearxngTimeoutError,
    SearxngUnavailableError,
    _clean_text,
)
from app.schemas.search import SearchResponse, SearchResultItem


def test_clean_text():
    assert _clean_text("<b>Hello</b> &amp; world!") == "Hello & world!"
    assert _clean_text("   multi   spaces  ") == "multi spaces"
    assert _clean_text("") == ""


@pytest.mark.asyncio
async def test_searxng_service_search_success():
    mock_payload = {
        "query": "artificial intelligence",
        "results": [
            {
                "title": "<b>AI</b> Overview",
                "url": "https://example.com/ai",
                "content": "An introduction to <b>artificial intelligence</b>.",
                "publishedDate": "2026-01-01",
                "engine": "google",
                "score": 0.95,
            },
            {
                "title": "Machine Learning",
                "url": "https://example.com/ml",
                "content": "Deep learning and ML.",
                "publishedDate": None,
                "engine": "duckduckgo",
                "score": 0.8,
            },
        ],
    }

    service = SearxngService(base_url="http://mock-searxng:8080", timeout_s=5.0)
    mock_resp = httpx.Response(200, json=mock_payload, request=httpx.Request("GET", "http://mock-searxng:8080/search"))

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        res = await service.search("artificial intelligence", max_results=1)

        assert res.query == "artificial intelligence"
        assert len(res.results) == 1
        assert res.results[0].title == "AI Overview"
        assert res.results[0].url == "https://example.com/ai"
        assert res.results[0].snippet == "An introduction to artificial intelligence."
        assert res.results[0].engine == "google"


@pytest.mark.asyncio
async def test_searxng_service_empty_query():
    service = SearxngService()
    with pytest.raises(ValueError, match="cannot be empty"):
        await service.search("   ")


@pytest.mark.asyncio
async def test_searxng_service_connect_error():
    service = SearxngService(base_url="http://unreachable:8080")
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection refused")
        with pytest.raises(SearxngUnavailableError):
            await service.search("test")


@pytest.mark.asyncio
async def test_searxng_service_timeout_error():
    service = SearxngService(base_url="http://mock-searxng:8080")
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.TimeoutException("Read timeout")
        with pytest.raises(SearxngTimeoutError):
            await service.search("test")


def test_rest_search_endpoints():
    client = TestClient(app)
    mock_response = SearchResponse(
        query="test",
        results=[
            SearchResultItem(
                title="Test Title",
                url="https://example.com/test",
                snippet="Test snippet",
                engine="google",
            )
        ],
        total_results=1,
        search_duration_ms=12.5,
    )

    with patch("app.routers.search.searxng_service.search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_response

        # Test GET /v1/search
        resp = client.get("/v1/search?q=test&max_results=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "test"
        assert len(data["results"]) == 1
        assert data["results"][0]["url"] == "https://example.com/test"

        # Test POST /v1/search
        resp_post = client.post("/v1/search", json={"query": "test", "max_results": 5})
        assert resp_post.status_code == 200
        data_post = resp_post.json()
        assert data_post["query"] == "test"
        assert len(data_post["results"]) == 1


def test_rest_search_unavailable_handling():
    client = TestClient(app)
    with patch("app.routers.search.searxng_service.search", new_callable=AsyncMock) as mock_search:
        mock_search.side_effect = SearxngUnavailableError("SearXNG unreachable")

        resp = client.get("/v1/search?q=test")
        assert resp.status_code == 503
        data = resp.json()
        error_msg = data.get("error", {}).get("message") or data.get("detail", "")
        assert "unavailable" in error_msg.lower()


def test_health_endpoint_with_search():
    client = TestClient(app)
    from app.schemas.search import SearchHealthStatus

    with patch("app.routers.health.searxng_service.check_health", new_callable=AsyncMock) as mock_health:
        mock_health.return_value = SearchHealthStatus(
            status="healthy",
            service="searxng",
            base_url="http://localhost:8080",
        )

        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "search" in data
        assert data["search"]["status"] == "healthy"
        assert data["search"]["service"] == "searxng"
