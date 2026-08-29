import logging
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.core.config import settings
from app.services.search_service import searxng_service

logger = logging.getLogger(__name__)

# FastMCP server instance
mcp_server = FastMCP(
    name=settings.mcp_server_name,
    instructions="Buddhi AI Studio Search MCP server providing live web search via SearXNG.",
)


@mcp_server.tool(
    name="search_web",
    description="Execute a web search using the self-hosted SearXNG engine to retrieve web pages, articles, and documentation.",
)
async def search_web(
    query: str,
    max_results: int = 5,
    categories: list[str] | None = None,
    language: str = "auto",
) -> list[dict[str, Any]]:
    """Execute a web search and return structured summary items (title, url, snippet)."""
    try:
        response = await searxng_service.search(
            query=query,
            max_results=max_results,
            categories=categories,
            language=language,
        )
        return [
            {
                "title": r.title,
                "url": r.url,
                "snippet": r.snippet,
                "published_date": r.published_date,
                "engine": r.engine,
            }
            for r in response.results
        ]
    except Exception as exc:
        logger.warning("Error executing search_web tool: %s", exc)
        return [
            {
                "error": f"Search execution failed: {exc}",
                "query": query,
            }
        ]


def run_stdio() -> None:
    """Entrypoint for desktop MCP clients using stdio transport."""
    # Ensure stdout is reserved exclusively for JSON-RPC MCP messages
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    mcp_server.run(transport="stdio")


if __name__ == "__main__":
    run_stdio()
