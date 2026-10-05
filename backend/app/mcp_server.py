import logging
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.core.config import settings
from app.schemas.crawl import CrawlRequest
from app.schemas.sandbox import SandboxExecutionRequest
from app.services.crawl_service import crawl_service
from app.services.sandbox_service import sandbox_service
from app.services.search_service import searxng_service

logger = logging.getLogger(__name__)

# FastMCP server instance
mcp_server = FastMCP(
    name=settings.mcp_server_name,
    instructions="Buddhi AI Studio MCP server providing live web search via SearXNG, web crawling & markdown extraction via Crawl4AI, and isolated code execution via OpenSandbox.",
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


@mcp_server.tool(
    name="sandbox_execute_code",
    description="Execute Python or shell code in a secure, isolated sandbox container and return stdout, stderr, and exit code.",
)
async def sandbox_execute_code(
    code: str,
    language: str = "python",
    timeout_s: int = 60,
    allow_network: bool = False,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Execute a code snippet in a sandbox container."""
    try:
        req = SandboxExecutionRequest(
            code=code,
            language=language,  # type: ignore[arg-type]
            timeout_s=timeout_s,
            allow_network=allow_network,
            session_id=session_id,
        )
        res = await sandbox_service.execute_one_shot(req)
        return res.model_dump()
    except Exception as exc:
        logger.warning("Error executing sandbox_execute_code: %s", exc)
        return {
            "status": "error",
            "error": f"Sandbox execution failed: {exc}",
            "stdout": "",
            "stderr": str(exc),
            "exit_code": 1,
        }


@mcp_server.tool(
    name="sandbox_run_command",
    description="Run a shell command inside an isolated sandbox container.",
)
async def sandbox_run_command(
    command: str,
    timeout_s: int = 60,
    allow_network: bool = False,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Execute a shell command inside a sandbox."""
    try:
        req = SandboxExecutionRequest(
            code=command,
            language="bash",
            timeout_s=timeout_s,
            allow_network=allow_network,
            session_id=session_id,
        )
        res = await sandbox_service.execute_one_shot(req)
        return res.model_dump()
    except Exception as exc:
        logger.warning("Error executing sandbox_run_command: %s", exc)
        return {
            "status": "error",
            "error": f"Command execution failed: {exc}",
            "stdout": "",
            "stderr": str(exc),
            "exit_code": 1,
        }


@mcp_server.tool(
    name="sandbox_write_file",
    description="Write text or base64 file content into an active sandbox session's workspace.",
)
async def sandbox_write_file(
    session_id: str,
    path: str,
    content: str,
    is_base64: bool = False,
) -> dict[str, Any]:
    """Write a file into the sandbox workspace."""
    try:
        await sandbox_service.write_session_file(
            session_id=session_id,
            path=path,
            content=content,
            is_base64=is_base64,
        )
        return {"status": "success", "session_id": session_id, "path": path}
    except Exception as exc:
        logger.warning("Error in sandbox_write_file: %s", exc)
        return {"status": "error", "error": str(exc), "path": path}


@mcp_server.tool(
    name="sandbox_read_file",
    description="Read file content from an active sandbox session's workspace.",
)
async def sandbox_read_file(
    session_id: str,
    path: str,
) -> dict[str, Any]:
    """Read a file from the sandbox workspace."""
    try:
        content = await sandbox_service.read_session_file(session_id=session_id, path=path)
        return {"status": "success", "session_id": session_id, "path": path, "content": content}
    except Exception as exc:
        logger.warning("Error in sandbox_read_file: %s", exc)
        return {"status": "error", "error": str(exc), "path": path}


@mcp_server.tool(
    name="crawl_url",
    description="Crawl a webpage URL using Crawl4AI headless browser and extract clean, LLM-ready markdown, title, and metadata.",
)
async def crawl_url(
    url: str,
    css_selector: str | None = None,
    only_main_content: bool = True,
    bypass_cache: bool = False,
) -> dict[str, Any]:
    """Crawl a webpage and return clean markdown and metadata."""
    try:
        req = CrawlRequest(
            url=url,
            css_selector=css_selector,
            only_main_content=only_main_content,
            bypass_cache=bypass_cache,
        )
        res = await crawl_service.crawl(req)
        return res.model_dump()
    except Exception as exc:
        logger.warning("Error in crawl_url tool: %s", exc)
        return {
            "status": "error",
            "url": url,
            "error": f"Crawl failed: {exc}",
            "markdown": "",
            "title": "",
            "status_code": 500,
        }


@mcp_server.tool(
    name="crawl_page_content",
    description="Advanced crawl tool supporting custom JavaScript execution and wait conditions before extracting markdown.",
)
async def crawl_page_content(
    url: str,
    js_code: str | None = None,
    wait_for: str | None = None,
    css_selector: str | None = None,
    only_main_content: bool = True,
) -> dict[str, Any]:
    """Execute dynamic crawl with JavaScript execution or wait conditions."""
    try:
        req = CrawlRequest(
            url=url,
            js_code=js_code,
            wait_for=wait_for,
            css_selector=css_selector,
            only_main_content=only_main_content,
        )
        res = await crawl_service.crawl(req)
        return res.model_dump()
    except Exception as exc:
        logger.warning("Error in crawl_page_content tool: %s", exc)
        return {
            "status": "error",
            "url": url,
            "error": f"Crawl failed: {exc}",
            "markdown": "",
            "title": "",
            "status_code": 500,
        }


@mcp_server.tool(
    name="crawl_batch_urls",
    description="Crawl multiple webpage URLs in batch and return aggregated markdown contents.",
)
async def crawl_batch_urls(
    urls: list[str],
    only_main_content: bool = True,
) -> list[dict[str, Any]]:
    """Batch crawl multiple URLs and return results."""
    results: list[dict[str, Any]] = []
    for u in urls[:10]:  # Limit to 10 for interactive tool invocations
        try:
            req = CrawlRequest(url=u, only_main_content=only_main_content)
            res = await crawl_service.crawl(req)
            results.append(res.model_dump())
        except Exception as exc:
            results.append({
                "status": "error",
                "url": u,
                "error": str(exc),
                "markdown": "",
                "title": "",
                "status_code": 500,
            })
    return results


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
