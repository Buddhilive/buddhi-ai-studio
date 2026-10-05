import pytest
from unittest.mock import AsyncMock, patch

from app.mcp_server import (
    crawl_batch_urls,
    crawl_page_content,
    crawl_url,
    mcp_server,
)
from app.schemas.crawl import CrawlResult


@pytest.mark.asyncio
async def test_mcp_crawl_tools_registered():
    tools = await mcp_server.list_tools()
    tool_names = [t.name for t in tools]
    assert "crawl_url" in tool_names
    assert "crawl_page_content" in tool_names
    assert "crawl_batch_urls" in tool_names

    crawl_tool = next(t for t in tools if t.name == "crawl_url")
    assert "url" in crawl_tool.inputSchema["properties"]
    assert "css_selector" in crawl_tool.inputSchema["properties"]
    assert "only_main_content" in crawl_tool.inputSchema["properties"]


@pytest.mark.asyncio
async def test_mcp_crawl_url_success():
    mock_result = CrawlResult(
        url="https://example.com",
        status="completed",
        title="Example Domain",
        markdown="# Example Domain\nContent",
        status_code=200,
        links_count=2,
        media_count=0,
        execution_duration_ms=85.0,
    )

    with patch("app.mcp_server.crawl_service.crawl", new_callable=AsyncMock) as mock_crawl:
        mock_crawl.return_value = mock_result
        res = await crawl_url(url="https://example.com")
        assert res["status"] == "completed"
        assert res["url"] == "https://example.com"
        assert res["title"] == "Example Domain"
        assert "# Example Domain" in res["markdown"]


@pytest.mark.asyncio
async def test_mcp_crawl_url_error_handling():
    with patch("app.mcp_server.crawl_service.crawl", new_callable=AsyncMock) as mock_crawl:
        mock_crawl.side_effect = RuntimeError("Container down")
        res = await crawl_url(url="https://example.com")
        assert res["status"] == "error"
        assert "Container down" in res["error"]


@pytest.mark.asyncio
async def test_mcp_crawl_page_content_success():
    mock_result = CrawlResult(
        url="https://example.com/dynamic",
        status="completed",
        title="Dynamic Page",
        markdown="Loaded content via JS",
        status_code=200,
        links_count=0,
        media_count=1,
        execution_duration_ms=120.0,
    )

    with patch("app.mcp_server.crawl_service.crawl", new_callable=AsyncMock) as mock_crawl:
        mock_crawl.return_value = mock_result
        res = await crawl_page_content(
            url="https://example.com/dynamic",
            js_code="window.scrollBy(0, 500)",
            wait_for=1.5,
        )
        assert res["status"] == "completed"
        assert res["markdown"] == "Loaded content via JS"


@pytest.mark.asyncio
async def test_mcp_crawl_batch_urls_success():
    mock_result1 = CrawlResult(
        url="https://example.com/1",
        status="completed",
        title="Page 1",
        markdown="Page 1 Content",
        status_code=200,
        links_count=0,
        media_count=0,
        execution_duration_ms=50.0,
    )
    mock_result2 = CrawlResult(
        url="https://example.com/2",
        status="completed",
        title="Page 2",
        markdown="Page 2 Content",
        status_code=200,
        links_count=0,
        media_count=0,
        execution_duration_ms=60.0,
    )

    with patch("app.mcp_server.crawl_service.crawl", new_callable=AsyncMock) as mock_crawl:
        mock_crawl.side_effect = [mock_result1, mock_result2]
        res = await crawl_batch_urls(urls=["https://example.com/1", "https://example.com/2"])
        assert len(res) == 2
        assert res[0]["title"] == "Page 1"
        assert res[1]["title"] == "Page 2"
