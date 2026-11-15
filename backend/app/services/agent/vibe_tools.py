from __future__ import annotations

import json
import logging
import re
import secrets
import shlex
from typing import Any, Tuple

from app.core.config import settings
from app.schemas.chat import FunctionDefinition, ToolDefinition
from app.schemas.crawl import CrawlRequest
from app.schemas.sandbox import SandboxExecutionRequest
from app.services.crawl_service import CrawlError, crawl_service
from app.services.sandbox_service import sandbox_service
from app.services.search_service import SearxngError, searxng_service

logger = logging.getLogger(__name__)

_SAFE_PG_IDENT_RE = re.compile(r"^[a-z0-9_]{1,48}$")
_SAFE_SHADCN_COMP_RE = re.compile(r"^[a-z0-9-]+$")
_RESERVED_PG_NAMES = frozenset({"postgres", "template0", "template1", "buddhi_admin"})
_DANGEROUS_SQL_RE = re.compile(
    r"\b(?:pg_read_file|pg_ls_dir|lo_import|lo_export|dblink)\b|\bCOPY\b[\s\S]*\bPROGRAM\b",
    re.IGNORECASE,
)

_BLOCKED_JS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bfetch\s*\(", re.IGNORECASE),
    re.compile(r"\bXMLHttpRequest\b", re.IGNORECASE),
    re.compile(r"\bWebSocket\b", re.IGNORECASE),
    re.compile(r"\bnavigator\.sendBeacon\b", re.IGNORECASE),
)


def _truncate_vibe_output(text: str, cap: int | None = None) -> Tuple[str, bool]:
    limit = cap if cap is not None else settings.agent_tool_output_cap
    if len(text) > limit:
        return text[:limit] + f"\n... [TRUNCATED - {len(text) - limit} characters omitted]", True
    return text, False


VIBE_TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        type="function",
        function=FunctionDefinition(
            name="search_web",
            description="Search the web via self-hosted SearXNG for up-to-date library docs, APIs, and examples.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query string."},
                    "max_results": {"type": "integer", "description": "Maximum results to return (default 5)."},
                    "categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional SearXNG categories (e.g. ['it', 'general']).",
                    },
                    "language": {"type": "string", "description": "Language code (default 'auto')."},
                },
                "required": ["query"],
            },
        ),
    ),
    ToolDefinition(
        type="function",
        function=FunctionDefinition(
            name="crawl_url",
            description="Crawl a webpage URL via self-hosted Crawl4AI and extract clean, LLM-ready markdown.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "HTTP/HTTPS URL to crawl."},
                    "css_selector": {"type": "string", "description": "Optional CSS selector to isolate content."},
                    "only_main_content": {"type": "boolean", "description": "Filter out nav/footer (default true)."},
                    "bypass_cache": {"type": "boolean", "description": "Bypass Crawl4AI cache (default false)."},
                },
                "required": ["url"],
            },
        ),
    ),
    ToolDefinition(
        type="function",
        function=FunctionDefinition(
            name="crawl_page_content",
            description="Crawl a dynamic webpage via Crawl4AI with optional wait_for selector and safe DOM js_code.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "HTTP/HTTPS URL to crawl."},
                    "js_code": {"type": "string", "description": "Optional DOM-only JS snippet before extraction."},
                    "wait_for": {"type": "string", "description": "CSS selector or seconds to wait before extraction."},
                    "css_selector": {"type": "string", "description": "Optional CSS selector."},
                    "only_main_content": {"type": "boolean", "description": "Filter out nav/footer (default true)."},
                },
                "required": ["url"],
            },
        ),
    ),
    ToolDefinition(
        type="function",
        function=FunctionDefinition(
            name="crawl_batch_urls",
            description="Crawl multiple webpage URLs (up to 10) via Crawl4AI and return aggregated markdown.",
            parameters={
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of HTTP/HTTPS URLs to crawl (max 10).",
                    },
                    "only_main_content": {"type": "boolean", "description": "Filter out nav/footer (default true)."},
                },
                "required": ["urls"],
            },
        ),
    ),
    ToolDefinition(
        type="function",
        function=FunctionDefinition(
            name="provision_postgres_db",
            description=(
                "Idempotently provision an isolated PostgreSQL database (or configure SQLite) for the workspace "
                "and inject DATABASE_URL, DB_DIALECT, and BETTER_AUTH_SECRET into /workspace/.env."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "db_name": {"type": "string", "description": "Optional lowercase alphanumeric/underscore DB slug."},
                    "dialect": {
                        "type": "string",
                        "enum": ["postgresql", "sqlite"],
                        "description": "Target database dialect (default 'postgresql').",
                    },
                },
            },
        ),
    ),
    ToolDefinition(
        type="function",
        function=FunctionDefinition(
            name="query_database",
            description="Execute a parameterized SQL query against the workspace's provisioned Postgres or SQLite database.",
            parameters={
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SQL query to execute."},
                    "dialect": {
                        "type": "string",
                        "enum": ["postgresql", "sqlite"],
                        "description": "Database dialect (default 'postgresql').",
                    },
                    "params": {"type": "array", "items": {}, "description": "Optional positional query parameters."},
                    "read_only": {"type": "boolean", "description": "Enforce read-only transaction (default true)."},
                },
                "required": ["sql"],
            },
        ),
    ),
    ToolDefinition(
        type="function",
        function=FunctionDefinition(
            name="drizzle_kit",
            description="Run Drizzle ORM schema commands (push, generate, migrate, check, introspect) inside the sandbox.",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["push", "generate", "migrate", "check", "introspect"],
                        "description": "Drizzle Kit action to run.",
                    },
                    "config_path": {
                        "type": "string",
                        "description": "Relative path to Drizzle config (default 'drizzle.config.ts').",
                    },
                },
                "required": ["action"],
            },
        ),
    ),
    ToolDefinition(
        type="function",
        function=FunctionDefinition(
            name="nextjs_devtools",
            description="Inspect Next.js 16+ routes, /_next/mcp diagnostics, or run next typegen && tsc --noEmit.",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["diagnostics", "routes", "typecheck"],
                        "description": "Diagnostic action to perform (default 'diagnostics').",
                    },
                    "route": {"type": "string", "description": "Optional route filter."},
                },
            },
        ),
    ),
    ToolDefinition(
        type="function",
        function=FunctionDefinition(
            name="shadcn_registry",
            description="Search, inspect, or install shadcn/ui components via the official Shadcn MCP/CLI.",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["add", "view", "search"],
                        "description": "Registry action to run.",
                    },
                    "components": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Component names to add or view (e.g. ['dialog', 'table']).",
                    },
                    "query": {"type": "string", "description": "Search query for shadcn registry."},
                },
                "required": ["action"],
            },
        ),
    ),
    ToolDefinition(
        type="function",
        function=FunctionDefinition(
            name="better_auth_cli",
            description="Generate or migrate BetterAuth Drizzle schemas or inspect BetterAuth integration patterns.",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["generate", "migrate", "docs"],
                        "description": "BetterAuth CLI/MCP action.",
                    }
                },
                "required": ["action"],
            },
        ),
    ),
]

VIBE_TOOL_NAMES: frozenset[str] = frozenset(t.function.name for t in VIBE_TOOL_DEFINITIONS)


async def _handle_search_web(args: dict[str, Any]) -> tuple[str, str, int, bool]:
    query = str(args.get("query") or "").strip()
    if not query:
        return "error", "Error: 'query' argument is required.", 1, False
    max_results = max(1, min(int(args.get("max_results") or 5), 15))
    categories = args.get("categories")
    language = str(args.get("language") or "auto")

    try:
        resp = await searxng_service.search(
            query=query,
            max_results=max_results,
            categories=categories,
            language=language,
        )
    except SearxngError as exc:
        return (
            "error",
            f"SearXNG search unavailable ({exc}). Fall back to load_skill() and bundled stack skills.",
            1,
            False,
        )

    if not resp.results:
        return "completed", f"No search results found for '{query}'. Try broader terms or load_skill().", 0, False

    lines = [f"Search results for '{query}' ({len(resp.results)} shown):"]
    for idx, item in enumerate(resp.results, 1):
        lines.append(f"{idx}. **{item.title}** ({item.engine})\n   URL: {item.url}\n   {item.snippet}")
    output, truncated = _truncate_vibe_output("\n".join(lines))
    return "completed", output, 0, truncated


async def _handle_crawl_single(args: dict[str, Any], allow_js: bool = False) -> tuple[str, str, int, bool]:
    url = str(args.get("url") or "").strip()
    if not url:
        return "error", "Error: 'url' argument is required.", 1, False

    js_code = args.get("js_code") if allow_js else None
    if js_code:
        for pat in _BLOCKED_JS_PATTERNS:
            if pat.search(str(js_code)):
                return (
                    "error",
                    "Security Guardrail: js_code in crawl_page_content may not use network primitives (fetch/XHR/WebSocket).",
                    1,
                    False,
                )

    try:
        req = CrawlRequest(
            url=url,
            css_selector=args.get("css_selector"),
            only_main_content=bool(args.get("only_main_content", True)),
            wait_for=args.get("wait_for"),
            js_code=js_code,
            bypass_cache=bool(args.get("bypass_cache", False)),
        )
    except Exception as exc:
        return "error", f"Invalid crawl request: {exc}", 1, False

    try:
        res = await crawl_service.crawl(req)
    except CrawlError as exc:
        return (
            "error",
            f"Crawl4AI unavailable ({exc}). Fall back to load_skill() and bundled stack skills.",
            1,
            False,
        )

    if res.status != "completed":
        return "error", f"Crawl failed for {url}: {res.error or res.status}", 1, False

    body = f"# {res.title or url}\nSource: {res.url}\n\n{res.markdown}"
    output, truncated = _truncate_vibe_output(body)
    return "completed", output, 0, truncated


async def _handle_crawl_batch(args: dict[str, Any]) -> tuple[str, str, int, bool]:
    urls = args.get("urls") or []
    if not isinstance(urls, list) or not urls:
        return "error", "Error: 'urls' must be a non-empty list of URLs.", 1, False

    capped_urls = [str(u).strip() for u in urls[:10] if str(u).strip()]
    only_main = bool(args.get("only_main_content", True))
    sections: list[str] = []

    for url in capped_urls:
        try:
            req = CrawlRequest(url=url, only_main_content=only_main)
            res = await crawl_service.crawl(req)
            if res.status == "completed":
                sections.append(f"## {res.title or url}\nSource: {res.url}\n\n{res.markdown}")
            else:
                sections.append(f"## {url}\nError: {res.error or res.status}")
        except CrawlError as exc:
            return (
                "error",
                f"Crawl4AI unavailable ({exc}). Fall back to load_skill() and bundled stack skills.",
                1,
                False,
            )
        except Exception as exc:
            sections.append(f"## {url}\nInvalid URL or error: {exc}")

    output, truncated = _truncate_vibe_output("\n\n---\n\n".join(sections))
    return "completed", output, 0, truncated


async def _merge_sandbox_env(session_id: str, updates: dict[str, str]) -> None:
    existing_lines: list[str] = []
    try:
        raw = await sandbox_service.read_session_file(session_id, ".env")
        existing_lines = raw.splitlines()
    except Exception:
        existing_lines = []

    env_map: dict[str, str] = {}
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        k, v = stripped.split("=", 1)
        env_map[k.strip()] = v.strip()

    for k, v in updates.items():
        env_map[k] = v

    rendered = "\n".join(f"{k}={v}" for k, v in env_map.items()) + "\n"
    await sandbox_service.write_session_file(session_id, ".env", rendered)


def _normalize_pg_slug(workspace_id: str, db_name: str | None) -> str:
    raw = (db_name or workspace_id or "default").strip().lower().replace("-", "_")
    if raw.startswith("buddhi_app_"):
        raw = raw[len("buddhi_app_") :]
    if not _SAFE_PG_IDENT_RE.fullmatch(raw):
        raise ValueError(f"Invalid database identifier {raw!r}. Must match ^[a-z0-9_]{{1,48}}$.")
    if raw in _RESERVED_PG_NAMES or raw.startswith("pg_"):
        raise ValueError(f"Reserved database identifier {raw!r} is not permitted.")
    return raw


async def _handle_provision_postgres_db(
    args: dict[str, Any],
    session_id: str,
    ctx: Any,
) -> tuple[str, str, int, bool]:
    from app.services.agent.harness.models import ProvisionedDatabase
    from app.services.agent.harness.storage import harness_storage_service

    workspace_id = str(getattr(ctx, "workspace_id", "default") or "default")
    dialect = str(args.get("dialect") or "postgresql").lower()
    if dialect not in ("postgresql", "sqlite"):
        return "error", f"Unsupported dialect '{dialect}'. Use 'postgresql' or 'sqlite'.", 1, False

    try:
        slug = _normalize_pg_slug(workspace_id, args.get("db_name"))
    except ValueError as exc:
        return "error", f"Identifier validation error: {exc}", 1, False

    auth_secret = secrets.token_urlsafe(32)

    if dialect == "sqlite":
        await _merge_sandbox_env(
            session_id,
            {
                "DB_DIALECT": "sqlite",
                "DATABASE_URL": "file:./local.db",
                "BETTER_AUTH_SECRET": auth_secret,
                "LOCAL_LLM_BASE_URL": settings.local_llm_base_url,
            },
        )
        harness_storage_service.upsert_provisioned_database(
            ProvisionedDatabase(
                workspace_id=workspace_id,
                db_name=f"sqlite_{slug}",
                role_name="",
                dialect="sqlite",
                masked_dsn="file:./local.db",
                status="active",
            )
        )
        return "completed", "Configured SQLite workspace database (DB_DIALECT=sqlite, DATABASE_URL=file:./local.db in .env).", 0, False

    safe_db_name = f"buddhi_app_{slug}"[:48]
    safe_role_name = f"role_{slug}"[:48]
    role_password = secrets.token_urlsafe(24)

    try:
        import psycopg
        from psycopg import sql as psql

        async with await psycopg.AsyncConnection.connect(
            settings.postgres_admin_dsn,
            autocommit=True,
            connect_timeout=settings.postgres_connect_timeout_s,
        ) as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (safe_role_name,))
                if await cur.fetchone() is None:
                    await conn.execute(
                        psql.SQL("CREATE ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {}").format(
                            psql.Identifier(safe_role_name),
                            psql.Literal(role_password),
                        )
                    )
                else:
                    await conn.execute(
                        psql.SQL("ALTER ROLE {} WITH PASSWORD {}").format(
                            psql.Identifier(safe_role_name),
                            psql.Literal(role_password),
                        )
                    )

                await cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (safe_db_name,))
                if await cur.fetchone() is None:
                    await conn.execute(
                        psql.SQL("CREATE DATABASE {} OWNER {}").format(
                            psql.Identifier(safe_db_name),
                            psql.Identifier(safe_role_name),
                        )
                    )
                await conn.execute(
                    psql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(psql.Identifier(safe_db_name))
                )
                await conn.execute(
                    psql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                        psql.Identifier(safe_db_name),
                        psql.Identifier(safe_role_name),
                    )
                )
    except Exception as exc:
        return (
            "error",
            f"Postgres provisioning failed ({exc}). Verify the postgres service is healthy or retry with dialect='sqlite'.",
            1,
            False,
        )

    sandbox_dsn = (
        f"postgresql://{safe_role_name}:{role_password}"
        f"@{settings.postgres_sandbox_host}:{settings.postgres_port}/{safe_db_name}"
    )
    masked_dsn = (
        f"postgresql://{safe_role_name}:[REDACTED]"
        f"@{settings.postgres_sandbox_host}:{settings.postgres_port}/{safe_db_name}"
    )
    await _merge_sandbox_env(
        session_id,
        {
            "DB_DIALECT": "postgresql",
            "DATABASE_URL": sandbox_dsn,
            "BETTER_AUTH_SECRET": auth_secret,
            "LOCAL_LLM_BASE_URL": settings.local_llm_base_url,
        },
    )
    harness_storage_service.upsert_provisioned_database(
        ProvisionedDatabase(
            workspace_id=workspace_id,
            db_name=safe_db_name,
            role_name=safe_role_name,
            dialect="postgresql",
            masked_dsn=masked_dsn,
            status="active",
        )
    )
    return (
        "completed",
        f"Provisioned isolated Postgres database '{safe_db_name}' (role '{safe_role_name}') and wrote {masked_dsn} to .env.",
        0,
        False,
    )


async def _handle_query_database(
    args: dict[str, Any],
    session_id: str,
    ctx: Any,
) -> tuple[str, str, int, bool]:
    from app.services.agent.harness.storage import harness_storage_service

    query = str(args.get("sql") or "").strip()
    if not query:
        return "error", "Error: 'sql' argument is required.", 1, False
    if _DANGEROUS_SQL_RE.search(query):
        return "error", "Security Guardrail: Privileged Postgres filesystem/COPY PROGRAM functions are blocked.", 1, False

    workspace_id = str(getattr(ctx, "workspace_id", "default") or "default")
    dialect = str(args.get("dialect") or "postgresql").lower()
    params = args.get("params") or []
    read_only = bool(args.get("read_only", True))

    if dialect == "sqlite":
        py_script = (
            "import json, sqlite3\n"
            f"uri = 'file:/workspace/local.db?mode=ro' if {read_only!r} else '/workspace/local.db'\n"
            f"conn = sqlite3.connect(uri, uri={read_only!r})\n"
            "cur = conn.cursor()\n"
            f"cur.execute({query!r}, {list(params)!r})\n"
            "rows = cur.fetchmany(100) if cur.description else []\n"
            "cols = [d[0] for d in cur.description] if cur.description else []\n"
            "if not " + repr(read_only) + ": conn.commit()\n"
            "print(json.dumps({'columns': cols, 'rows': rows}))\n"
        )
        res = await sandbox_service.execute_in_session(
            session_id,
            SandboxExecutionRequest(code=py_script, language="python", timeout_s=15),
        )
        out = res.stdout or res.stderr
        truncated_out, is_trunc = _truncate_vibe_output(out)
        status = "completed" if res.status == "completed" and res.exit_code == 0 else "error"
        return status, truncated_out, res.exit_code, is_trunc

    prov = harness_storage_service.get_provisioned_database(workspace_id)
    target_db = prov.db_name if prov and prov.dialect == "postgresql" else None
    if not target_db:
        return (
            "error",
            f"No provisioned Postgres database found for workspace '{workspace_id}'. Call provision_postgres_db first.",
            1,
            False,
        )

    try:
        import psycopg

        dsn = (
            f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
            f"@{settings.postgres_host}:{settings.postgres_port}/{target_db}"
        )
        async with await psycopg.AsyncConnection.connect(
            dsn,
            connect_timeout=settings.postgres_connect_timeout_s,
        ) as conn:
            if read_only:
                await conn.set_read_only(True)
            async with conn.cursor() as cur:
                await cur.execute("SET LOCAL statement_timeout = '5000ms'")
                await cur.execute(query, list(params))
                rows = await cur.fetchmany(100) if cur.description else []
                cols = [d.name for d in cur.description] if cur.description else []
            if not read_only:
                await conn.commit()
    except Exception as exc:
        return "error", f"Postgres query error: {exc}", 1, False

    payload = json.dumps({"columns": cols, "rows": [list(r) for r in rows]}, default=str)
    output, truncated = _truncate_vibe_output(payload)
    return "completed", output, 0, truncated


async def _run_sandbox_cli(session_id: str, cmd: str, timeout_s: int = 60) -> tuple[str, str, int, bool]:
    res = await sandbox_service.execute_in_session(
        session_id,
        SandboxExecutionRequest(code=cmd, language="bash", timeout_s=timeout_s),
    )
    out = res.stdout
    if res.stderr:
        out = f"{out}\n{res.stderr}" if out else res.stderr
    truncated_out, is_trunc = _truncate_vibe_output(out or "(no output)")
    status = "completed" if res.status == "completed" and res.exit_code == 0 else "error"
    return status, truncated_out, res.exit_code, is_trunc


async def _handle_drizzle_kit(args: dict[str, Any], session_id: str, ctx: Any) -> tuple[str, str, int, bool]:
    action = str(args.get("action") or "").strip().lower()
    if action not in ("push", "generate", "migrate", "check", "introspect"):
        return "error", f"Invalid drizzle_kit action '{action}'.", 1, False
    if getattr(ctx, "is_egm_mode", False) and not getattr(ctx, "spec_approved", False) and action in ("push", "migrate", "generate"):
        return "error", "EGM Guardrail Violation: drizzle_kit mutating actions prohibited before spec approval.", 1, False

    config_path = str(args.get("config_path") or "drizzle.config.ts").strip()
    if ".." in config_path or config_path.startswith("/"):
        return "error", f"Invalid config_path '{config_path}'. Must be relative to /workspace.", 1, False
    cmd = f"npx --no-install drizzle-kit {action} --config={shlex.quote(config_path)}"
    return await _run_sandbox_cli(session_id, cmd)


async def _handle_nextjs_devtools(args: dict[str, Any], session_id: str) -> tuple[str, str, int, bool]:
    action = str(args.get("action") or "diagnostics").strip().lower()
    if action not in ("diagnostics", "routes", "typecheck"):
        return "error", f"Invalid nextjs_devtools action '{action}'.", 1, False

    if action in ("diagnostics", "routes"):
        mcp_probe = await sandbox_service.execute_in_session(
            session_id,
            SandboxExecutionRequest(
                code=(
                    "curl -fsS -X POST http://localhost:3000/_next/mcp "
                    "-H 'Content-Type: application/json' "
                    "-d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\"}' 2>/dev/null || true"
                ),
                language="bash",
                timeout_s=10,
            ),
        )
        if mcp_probe.stdout and "jsonrpc" in mcp_probe.stdout:
            truncated_out, is_trunc = _truncate_vibe_output(mcp_probe.stdout)
            return "completed", truncated_out, 0, is_trunc

    return await _run_sandbox_cli(session_id, "npx --no-install next typegen && npx --no-install tsc --noEmit", timeout_s=90)


async def _handle_shadcn_registry(args: dict[str, Any], session_id: str, ctx: Any) -> tuple[str, str, int, bool]:
    action = str(args.get("action") or "").strip().lower()
    if action not in ("add", "view", "search"):
        return "error", f"Invalid shadcn_registry action '{action}'.", 1, False
    if action == "add" and getattr(ctx, "is_egm_mode", False) and not getattr(ctx, "spec_approved", False):
        return "error", "EGM Guardrail Violation: shadcn_registry(action='add') prohibited before spec approval.", 1, False

    components = [str(c).strip().lower() for c in (args.get("components") or []) if str(c).strip()]
    for comp in components:
        if not _SAFE_SHADCN_COMP_RE.fullmatch(comp):
            return "error", f"Invalid component name '{comp}'. Must match ^[a-z0-9-]+$.", 1, False

    if action == "add":
        if not components:
            return "error", "Error: 'components' list is required for action='add'.", 1, False
        joined = " ".join(shlex.quote(c) for c in components)
        return await _run_sandbox_cli(session_id, f"npx --no-install shadcn@latest add {joined} --yes --overwrite")
    if action == "view":
        if not components:
            return "error", "Error: 'components' list is required for action='view'.", 1, False
        return await _run_sandbox_cli(session_id, f"npx --no-install shadcn@latest view {shlex.quote(components[0])}")

    query = shlex.quote(str(args.get("query") or "button"))
    return await _run_sandbox_cli(session_id, f"npx --no-install shadcn@latest search {query}")


async def _handle_better_auth_cli(args: dict[str, Any], session_id: str, ctx: Any) -> tuple[str, str, int, bool]:
    action = str(args.get("action") or "generate").strip().lower()
    if action not in ("generate", "migrate", "docs"):
        return "error", f"Invalid better_auth_cli action '{action}'.", 1, False
    if action in ("generate", "migrate") and getattr(ctx, "is_egm_mode", False) and not getattr(ctx, "spec_approved", False):
        return "error", "EGM Guardrail Violation: better_auth_cli mutating actions prohibited before spec approval.", 1, False

    if action == "docs":
        return (
            "completed",
            "BetterAuth Docs (Drizzle): Use betterAuth({ database: drizzleAdapter(db, { provider: 'pg' | 'sqlite' }) }), "
            "mount toNextJsHandler(auth) at src/app/api/auth/[...all]/route.ts, and createAuthClient() in src/lib/auth-client.ts.",
            0,
            False,
        )
    return await _run_sandbox_cli(session_id, f"npx --no-install @better-auth/cli {action} --yes")


async def execute_vibe_tool(
    name: str,
    args: dict[str, Any],
    session_id: str,
    ctx: Any,
    emitter: Any = None,
    tool_call_id: str | None = None,
) -> tuple[str, str, int, bool]:
    """Dispatch SearXNG, Crawl4AI, Database, and Vibe-Stack MCP/CLI tools."""
    if name == "search_web":
        return await _handle_search_web(args)
    if name == "crawl_url":
        return await _handle_crawl_single(args, allow_js=False)
    if name == "crawl_page_content":
        return await _handle_crawl_single(args, allow_js=True)
    if name == "crawl_batch_urls":
        return await _handle_crawl_batch(args)
    if name == "provision_postgres_db":
        return await _handle_provision_postgres_db(args, session_id, ctx)
    if name == "query_database":
        return await _handle_query_database(args, session_id, ctx)
    if name == "drizzle_kit":
        return await _handle_drizzle_kit(args, session_id, ctx)
    if name == "nextjs_devtools":
        return await _handle_nextjs_devtools(args, session_id)
    if name == "shadcn_registry":
        return await _handle_shadcn_registry(args, session_id, ctx)
    if name == "better_auth_cli":
        return await _handle_better_auth_cli(args, session_id, ctx)
    return "error", f"Unknown vibe tool: '{name}'", 1, False
