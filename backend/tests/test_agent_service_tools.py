from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.crawl import CrawlResult
from app.schemas.search import SearchResponse, SearchResultItem
from app.services.agent.events import AgentEventEmitter
from app.services.agent.tools import AGENT_TOOL_DEFINITIONS, ToolGuardrailContext, execute_tool
from app.services.crawl_service import CrawlUnavailableError
from app.services.search_service import SearxngUnavailableError


def test_service_tools_registered_in_agent_definitions() -> None:
    names = {t.function.name for t in AGENT_TOOL_DEFINITIONS}
    assert {"search_web", "crawl_url", "crawl_page_content", "crawl_batch_urls"}.issubset(names)


@pytest.mark.asyncio
async def test_execute_search_web_success() -> None:
    mock_response = SearchResponse(
        query="better-auth drizzle adapter",
        results=[
            SearchResultItem(
                title="Better Auth Drizzle",
                url="https://www.better-auth.com/docs/adapters/drizzle",
                snippet="Use drizzleAdapter(db, { provider: 'pg' }).",
                engine="google",
            )
        ],
        total_results=1,
        engines_used=["google"],
        search_duration_ms=42.0,
        cached=False,
    )
    with patch("app.services.agent.vibe_tools.searxng_service.search", new=AsyncMock(return_value=mock_response)):
        status, output, exit_code, truncated = await execute_tool(
            "search_web",
            {"query": "better-auth drizzle adapter", "max_results": 3},
            session_id="sess_1",
        )
    assert status == "completed"
    assert exit_code == 0
    assert truncated is False
    assert "Better Auth Drizzle" in output
    assert "https://www.better-auth.com/docs/adapters/drizzle" in output


@pytest.mark.asyncio
async def test_execute_crawl_url_and_page_content_success() -> None:
    mock_crawl = CrawlResult(
        url="https://nextjs.org/docs",
        status="completed",
        title="Next.js Docs",
        markdown="# Next.js App Router\nUse Server Components by default.",
        status_code=200,
        links_count=4,
        media_count=0,
        execution_duration_ms=120.0,
    )
    with patch("app.services.agent.vibe_tools.crawl_service.crawl", new=AsyncMock(return_value=mock_crawl)) as mock_fn:
        status, output, exit_code, _ = await execute_tool(
            "crawl_url",
            {"url": "https://nextjs.org/docs"},
            session_id="sess_1",
        )
        assert status == "completed"
        assert exit_code == 0
        assert "Next.js App Router" in output
        assert mock_fn.call_args.args[0].only_main_content is True

        status2, output2, exit_code2, _ = await execute_tool(
            "crawl_page_content",
            {"url": "https://nextjs.org/docs", "wait_for": ".docs-content", "js_code": "window.scrollTo(0, 100);"},
            session_id="sess_1",
        )
        assert status2 == "completed"
        assert exit_code2 == 0
        assert "Next.js Docs" in output2


@pytest.mark.asyncio
async def test_execute_crawl_batch_urls_caps_and_aggregates() -> None:
    async def _fake_crawl(req):
        return CrawlResult(
            url=req.url,
            status="completed",
            title=f"Title for {req.url}",
            markdown=f"Markdown for {req.url}",
            status_code=200,
            execution_duration_ms=50.0,
        )

    urls = [f"https://example.com/page-{i}" for i in range(12)]
    with patch("app.services.agent.vibe_tools.crawl_service.crawl", side_effect=_fake_crawl) as mock_fn:
        status, output, exit_code, _ = await execute_tool(
            "crawl_batch_urls",
            {"urls": urls},
            session_id="sess_1",
        )
    assert status == "completed"
    assert exit_code == 0
    assert mock_fn.call_count == 10
    assert "page-0" in output
    assert "page-9" in output


@pytest.mark.asyncio
async def test_service_tools_output_truncation_and_emitter_events() -> None:
    huge_markdown = "# Big Doc\n" + ("A" * 10000)
    mock_crawl = CrawlResult(
        url="https://nextjs.org/docs/large",
        status="completed",
        title="Large Doc",
        markdown=huge_markdown,
        status_code=200,
        execution_duration_ms=90.0,
    )
    emitter = AgentEventEmitter(run_id="run_test_1")
    with patch("app.services.agent.vibe_tools.crawl_service.crawl", new=AsyncMock(return_value=mock_crawl)):
        status, output, exit_code, truncated = await execute_tool(
            "crawl_url",
            {"url": "https://nextjs.org/docs/large"},
            session_id="sess_1",
            guardrail_ctx=ToolGuardrailContext(workspace_id="ws_1"),
            emitter=emitter,
            tool_call_id="tc_crawl_1",
        )

    assert status == "completed"
    assert exit_code == 0
    assert truncated is True
    assert "characters omitted" in output

    events = []
    while not emitter._queue.empty():
        ev = emitter._queue.get_nowait()
        if ev is not None:
            events.append(ev)
    event_types = [e.event for e in events]
    assert "tool.start" in event_types
    assert "tool.end" in event_types
    end_ev = next(e for e in events if e.event == "tool.end")
    assert end_ev.data["tool_name"] == "crawl_url"
    assert end_ev.data["truncated"] is True


@pytest.mark.asyncio
async def test_search_and_crawl_offline_fallback() -> None:
    with patch(
        "app.services.agent.vibe_tools.searxng_service.search",
        new=AsyncMock(side_effect=SearxngUnavailableError("Connection refused")),
    ):
        status, output, exit_code, _ = await execute_tool(
            "search_web",
            {"query": "drizzle orm postgres"},
            session_id="sess_1",
        )
    assert status == "error"
    assert exit_code == 1
    assert "load_skill" in output

    with patch(
        "app.services.agent.vibe_tools.crawl_service.crawl",
        new=AsyncMock(side_effect=CrawlUnavailableError("Connection refused")),
    ):
        status2, output2, exit_code2, _ = await execute_tool(
            "crawl_url",
            {"url": "https://orm.drizzle.team/docs/overview"},
            session_id="sess_1",
        )
    assert status2 == "error"
    assert exit_code2 == 1
    assert "load_skill" in output2
