import pytest
from unittest.mock import AsyncMock, patch

from app.main import app
from app.mcp_server import mcp_server, search_web
from app.schemas.search import SearchResponse, SearchResultItem
from app.services.search_service import SearxngUnavailableError


@pytest.mark.asyncio
async def test_mcp_tool_registered():
    tools = await mcp_server.list_tools()
    tool_names = [t.name for t in tools]
    assert "search_web" in tool_names

    tool_def = next(t for t in tools if t.name == "search_web")
    assert "SearXNG" in tool_def.description or "search" in tool_def.description.lower()
    assert "query" in tool_def.inputSchema["properties"]


@pytest.mark.asyncio
async def test_mcp_search_web_tool_execution():
    mock_response = SearchResponse(
        query="python",
        results=[
            SearchResultItem(
                title="Python Programming",
                url="https://python.org",
                snippet="Official Python website.",
                published_date="2026-01-01",
                engine="google",
            )
        ],
        total_results=1,
        search_duration_ms=5.0,
    )

    with patch("app.mcp_server.searxng_service.search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_response

        results = await search_web(query="python", max_results=3)
        assert len(results) == 1
        assert results[0]["title"] == "Python Programming"
        assert results[0]["url"] == "https://python.org"
        assert results[0]["snippet"] == "Official Python website."


@pytest.mark.asyncio
async def test_mcp_search_web_tool_error_handling():
    with patch("app.mcp_server.searxng_service.search", new_callable=AsyncMock) as mock_search:
        mock_search.side_effect = SearxngUnavailableError("SearXNG offline")

        results = await search_web(query="offline query")
        assert len(results) == 1
        assert "error" in results[0]
        assert "Search execution failed" in results[0]["error"]


def test_mcp_mount_exists():
    mount_paths = [route.path for route in app.routes if hasattr(route, "path")]
    assert "/mcp" in mount_paths
