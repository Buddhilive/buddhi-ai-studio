from __future__ import annotations

import json
import logging
import posixpath
import re
import shlex
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Literal, Tuple

from app.core.config import settings
from app.schemas.chat import FunctionDefinition, ToolDefinition
from app.schemas.sandbox import SandboxExecutionRequest, SandboxSessionCreateRequest
from app.services.agent.redaction import redact_text
from app.services.agent.skill_loader import LOAD_SKILL_TOOL_DEFINITION, execute_load_skill
from app.services.agent.vibe_starter import ensure_vibe_starter_workspace
from app.services.agent.vibe_tools import VIBE_TOOL_DEFINITIONS, VIBE_TOOL_NAMES, execute_vibe_tool
from app.services.sandbox_service import sandbox_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolGuardrailContext:
    workspace_id: str = "default"
    project_id: str | None = None
    db_dialect: str | None = None
    is_egm_mode: bool = False
    run_id: str = ""
    egm_phase: str | None = None
    spec_approved: bool = False
    target_scope_files: tuple[str, ...] = ()
    allowed_write_paths: tuple[str, ...] = ()


def validate_workspace_path(path_str: str) -> str:
    """Canonicalize a relative or absolute /workspace path and verify no path traversal."""
    if not path_str or "\x00" in path_str:
        raise ValueError("Invalid path: empty or contains null byte")

    # Reject raw unnormalized .. segments
    parts = path_str.replace("\\", "/").split("/")
    if ".." in parts:
        raise ValueError("Invalid path: traversal segment '..' is prohibited")

    p = PurePosixPath(path_str)
    if p.is_absolute():
        if not str(p).startswith("/workspace"):
            raise ValueError(f"Absolute path '{path_str}' must reside within /workspace")
        rel = posixpath.relpath(str(p), "/workspace")
    else:
        rel = str(p)

    norm = posixpath.normpath(rel)
    if norm == "." or norm.startswith("../"):
        raise ValueError(f"Path '{path_str}' escapes workspace boundary")
    return norm

# Standard tool definitions provided to agent
AGENT_TOOL_DEFINITIONS = [
    ToolDefinition(
        type="function",
        function=FunctionDefinition(
            name="run_command",
            description="Execute a bash shell command inside the isolated sandbox container.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The exact shell command to execute.",
                    }
                },
                "required": ["command"],
            },
        ),
    ),
    ToolDefinition(
        type="function",
        function=FunctionDefinition(
            name="write_file",
            description="Create or overwrite a file in the sandbox workspace.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file in /workspace.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content of the file to write.",
                    },
                },
                "required": ["path", "content"],
            },
        ),
    ),
    ToolDefinition(
        type="function",
        function=FunctionDefinition(
            name="read_file",
            description="Read the contents of a file in the sandbox workspace.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file in /workspace.",
                    }
                },
                "required": ["path"],
            },
        ),
    ),
    ToolDefinition(
        type="function",
        function=FunctionDefinition(
            name="list_files",
            description="List files and directories in the sandbox workspace.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list (default is current directory '.').",
                    }
                },
            },
        ),
    ),
    ToolDefinition(
        type="function",
        function=FunctionDefinition(
            name="run_python_repl",
            description="Execute Python code in the isolated OpenSandbox REPL with rlm_helpers preloaded.",
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The Python code to execute in the sandbox REPL.",
                    }
                },
                "required": ["code"],
            },
        ),
    ),
    ToolDefinition(
        type="function",
        function=FunctionDefinition(
            name="finish_rlm_task",
            description="Conclude the RLM exploration and report the final findings or code solution.",
            parameters={
                "type": "object",
                "properties": {
                    "final_answer": {
                        "type": "string",
                        "description": "The final synthesized conclusion, analysis, or resolution.",
                    }
                },
                "required": ["final_answer"],
            },
        ),
    ),
    LOAD_SKILL_TOOL_DEFINITION,
    *VIBE_TOOL_DEFINITIONS,
]


def _truncate_output(text: str, cap: int | None = None) -> Tuple[str, bool]:
    limit = cap if cap is not None else settings.agent_tool_output_cap
    if len(text) > limit:
        truncated = text[:limit] + f"\n... [TRUNCATED - {len(text) - limit} characters omitted]"
        return truncated, True
    return text, False


async def ensure_sandbox_session(session_id: str | None) -> str:
    """Ensure an active sandbox session exists. Creates one if needed."""
    if session_id:
        existing = await sandbox_service.get_session(session_id)
        if existing and not existing.is_expired():
            return session_id

    create_req = SandboxSessionCreateRequest(
        runtime_image=settings.sandbox_default_image,
        timeout_s=settings.sandbox_session_inactivity_ttl_s,
        allow_network=settings.sandbox_default_allow_network,
        memory_limit_mb=settings.sandbox_default_memory_mb,
    )
    new_session = await sandbox_service.create_session(create_req)
    await ensure_vibe_starter_workspace(new_session.session_id)
    return new_session.session_id


_BANNED_VIBE_PACKAGES: frozenset[str] = frozenset({
    "prisma",
    "@prisma/client",
    "typeorm",
    "sequelize",
    "mongoose",
    "next-auth",
    "@auth/core",
    "@mui/material",
    "@chakra-ui/react",
    "bootstrap",
    "styled-components",
    "express",
    "fastapi",
    "flask",
    "django",
    "vue",
    "nuxt",
    "svelte",
    "vite",
})

_BANNED_PKG_RE = re.compile(
    r"\b(?:npm|pnpm|yarn|bun)\s+(?:install|add|i|dlx)\b|\b(?:npx|pip\s+install)\b|\bcreate-(?:vite|react-app)\b",
    re.IGNORECASE,
)


def check_vibe_stack_guardrail(name: str, args: dict[str, Any]) -> str | None:
    """Enforce the locked Next.js 16+ Vibe-Coding Stack on writes and commands."""
    if name == "write_file":
        raw_path = str(args.get("path") or "").replace("\\", "/").lstrip("./")
        if raw_path.startswith("pages/") or raw_path.startswith("src/pages/"):
            return (
                f"Vibe-Stack Guardrail Violation: Pages Router path '{raw_path}' is blocked. "
                "Use Next.js App Router under 'src/app/' instead."
            )
        if re.fullmatch(r"tailwind\.config\.(?:js|cjs|mjs|ts)", raw_path):
            return (
                f"Vibe-Stack Guardrail Violation: Legacy '{raw_path}' is blocked. "
                "Use Tailwind CSS v4 CSS-first '@import \"tailwindcss\";' and '@theme inline' in 'src/app/globals.css'."
            )
        if raw_path == "prisma/schema.prisma":
            return (
                "Vibe-Stack Guardrail Violation: Prisma is blocked. "
                "Use Drizzle ORM ('src/db/schema.pg.ts' / 'src/db/schema.sqlite.ts') instead."
            )
        if raw_path == "package.json":
            try:
                pkg = json.loads(str(args.get("content") or "{}"))
            except Exception:
                return None
            for section in ("dependencies", "devDependencies"):
                deps = pkg.get(section)
                if isinstance(deps, dict):
                    for dep_name in deps:
                        if dep_name.lower() in _BANNED_VIBE_PACKAGES:
                            return (
                                f"Vibe-Stack Guardrail Violation: Package '{dep_name}' in package.json is blocked. "
                                "Use the locked stack (Next.js App Router, Tailwind v4, shadcn/ui, Drizzle ORM, BetterAuth, Vercel AI SDK)."
                            )
    elif name in ("run_command", "run_python_repl"):
        cmd = str(args.get("command" if name == "run_command" else "code") or "")
        if _BANNED_PKG_RE.search(cmd):
            for banned in _BANNED_VIBE_PACKAGES:
                if re.search(rf"(?<![\w@/-]){re.escape(banned)}(?![\w-])", cmd, re.IGNORECASE):
                    return (
                        f"Vibe-Stack Guardrail Violation: Installing/invoking '{banned}' is blocked. "
                        "Use the locked stack (drizzle-orm, better-auth, shadcn/ui, tailwindcss, ai)."
                    )
    return None


async def execute_tool(
    name: str,
    args: dict[str, Any] | str,
    session_id: str,
    guardrail_ctx: ToolGuardrailContext | None = None,
    emitter: Any = None,
    tool_call_id: str | None = None,
) -> tuple[str, str, int, bool]:
    """
    Execute a tool against the sandbox session or integrated service.
    Returns (status, output, exit_code, truncated).
    Status is 'completed' or 'error'.
    """
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {"raw_args": args}

    ctx = guardrail_ctx or ToolGuardrailContext()
    call_id = tool_call_id or f"call_{name}"

    if emitter is not None and hasattr(emitter, "emit_tool_start"):
        try:
            await emitter.emit_tool_start(call_id, name, args, node="observe")
        except Exception:
            pass

    status, output, exit_code, truncated = await _dispatch_tool(
        name=name,
        args=args,
        session_id=session_id,
        ctx=ctx,
        emitter=emitter,
        tool_call_id=call_id,
    )

    scrubbed_output = redact_text(output) if output else output
    if emitter is not None and hasattr(emitter, "emit_tool_end"):
        try:
            await emitter.emit_tool_end(
                tool_call_id=call_id,
                tool_name=name,
                status=status,
                output=scrubbed_output,
                exit_code=exit_code,
                truncated=truncated,
                node="observe",
            )
        except Exception:
            pass

    return status, scrubbed_output, exit_code, truncated


async def _dispatch_tool(
    name: str,
    args: dict[str, Any],
    session_id: str,
    ctx: ToolGuardrailContext,
    emitter: Any = None,
    tool_call_id: str | None = None,
) -> tuple[str, str, int, bool]:
    try:
        vibe_violation = check_vibe_stack_guardrail(name, args)
        if vibe_violation:
            return "error", vibe_violation, 1, False

        # Phase 1-4 Guardrail check for mutating commands/REPL
        if ctx.is_egm_mode and not ctx.spec_approved:
            if name in ("run_command", "run_python_repl"):
                # Check for obvious file mutation attempts in bash/python commands
                cmd_content = args.get("command", "") if name == "run_command" else args.get("code", "")
                mutation_patterns = [r">\s*[^&]", r"\brm\b", r"\bmv\b", r"\bcp\b", r"\btouch\b", r"\bmkdir\b", r"\bopen\s*\([^)]*['\"][w|a]"]
                for pat in mutation_patterns:
                    if re.search(pat, cmd_content):
                        return (
                            "error",
                            "EGM Guardrail Violation: mutating shell commands or code execution prohibited before spec approval in Phase 1-4.",
                            1,
                            False,
                        )

        if name == "run_command":
            cmd = args.get("command", "")
            if not cmd:
                return "error", "Error: 'command' argument is required", 1, False
            req = SandboxExecutionRequest(
                code=cmd,
                language="bash",
                timeout_s=settings.sandbox_default_timeout_s,
            )
            chunk_idx = 0

            async def _on_chunk(stream_name: str, delta: str) -> None:
                nonlocal chunk_idx
                if emitter is not None and hasattr(emitter, "emit_tool_output_delta"):
                    stream_lit = "stderr" if stream_name == "stderr" else "stdout"
                    await emitter.emit_tool_output_delta(
                        tool_call_id=tool_call_id or "call_stream",
                        tool_name=name,
                        stream=stream_lit,
                        delta=delta,
                        chunk_index=chunk_idx,
                        node="observe",
                    )
                    chunk_idx += 1

            result = await sandbox_service.execute_in_session_stream(
                session_id,
                req,
                on_chunk=_on_chunk if emitter is not None else None,
            )
            output = result.stdout
            if result.stderr:
                output = f"{output}\n{result.stderr}" if output else result.stderr
            truncated_output, is_truncated = _truncate_output(output)
            status = "completed" if result.status == "completed" and result.exit_code == 0 else "error"
            return status, truncated_output, result.exit_code, is_truncated

        elif name == "write_file":
            path = args.get("path")
            content = args.get("content", "")
            if not path:
                return "error", "Error: 'path' argument is required", 1, False

            try:
                norm_path = validate_workspace_path(path)
            except ValueError as ve:
                return "error", f"EGM Path Validation Error: {str(ve)}", 1, False

            # Harness2 Protection: never allow agent writes to .buddhi/harness/
            if norm_path == ".buddhi/harness" or norm_path.startswith(".buddhi/harness/"):
                return (
                    "error",
                    f"Harness2 Guardrail Violation: '.buddhi/harness/' is immutable to agent tools. Attempted write to '{norm_path}'.",
                    1,
                    False,
                )

            # EGM Write Boundary Enforcement
            if ctx.is_egm_mode:
                if not ctx.spec_approved:
                    # Phases 1-4: strictly restrict writes to .buddhi/specs/
                    allowed_prefix = f".buddhi/specs/{ctx.run_id}" if ctx.run_id else ".buddhi/specs"
                    if not (norm_path == allowed_prefix or norm_path.startswith(f"{allowed_prefix}/") or norm_path.startswith(".buddhi/specs/")):
                        return (
                            "error",
                            f"EGM Guardrail Violation: Phases 1-4 restrict writes strictly to '.buddhi/specs/'. Attempted write to '{norm_path}'.",
                            1,
                            False,
                        )
                else:
                    # Phase 5: enforce Target Scope & File Boundary (exact match or normalized directory prefix)
                    allowed = {p.rstrip("/") for p in (set(ctx.target_scope_files) | set(ctx.allowed_write_paths)) if p}
                    is_in_scope = (
                        norm_path in allowed
                        or any(norm_path.startswith(f"{p}/") for p in allowed)
                        or norm_path.startswith(".buddhi/specs/")
                    )
                    if not is_in_scope:
                        return (
                            "error",
                            f"EGM Boundary Violation: Path '{norm_path}' is outside approved Target Scope & File Boundary: {sorted(allowed)}",
                            1,
                            False,
                        )

            await sandbox_service.write_session_file(session_id, norm_path, content)
            if ctx.project_id:
                try:
                    from app.services.build_project_service import build_project_service

                    await build_project_service.sync_file_to_storage(ctx.project_id, norm_path, content)
                except Exception as exc:
                    logger.warning("Snapshot sync after write_file failed for %s: %s", norm_path, exc)
            return "completed", f"File '{norm_path}' written successfully ({len(content)} bytes).", 0, False

        elif name == "read_file":
            path = args.get("path")
            if not path:
                return "error", "Error: 'path' argument is required", 1, False
            try:
                norm_path = validate_workspace_path(path)
            except ValueError as ve:
                return "error", f"EGM Path Validation Error: {str(ve)}", 1, False

            content = await sandbox_service.read_session_file(session_id, norm_path)
            truncated_content, is_truncated = _truncate_output(content)
            return "completed", truncated_content, 0, is_truncated

        elif name == "list_files":
            path = args.get("path", ".")
            safe_path = shlex.quote(path)
            req = SandboxExecutionRequest(
                code=f"find {safe_path} -maxdepth 3 -not -path '*/.*'",
                language="bash",
                timeout_s=15,
            )
            result = await sandbox_service.execute_in_session(session_id, req)
            output = result.stdout or result.stderr or "(empty directory)"
            truncated_output, is_truncated = _truncate_output(output)
            status = "completed" if result.status == "completed" else "error"
            return status, truncated_output, result.exit_code, is_truncated

        elif name == "run_python_repl":
            code = args.get("code", "")
            if not code:
                return "error", "Error: 'code' argument is required", 1, False
            req = SandboxExecutionRequest(
                code=code,
                language="python",
                timeout_s=settings.sandbox_default_timeout_s,
            )
            chunk_idx = 0

            async def _on_repl_chunk(stream_name: str, delta: str) -> None:
                nonlocal chunk_idx
                if emitter is not None and hasattr(emitter, "emit_tool_output_delta"):
                    stream_lit = "stderr" if stream_name == "stderr" else "stdout"
                    await emitter.emit_tool_output_delta(
                        tool_call_id=tool_call_id or "call_stream",
                        tool_name=name,
                        stream=stream_lit,
                        delta=delta,
                        chunk_index=chunk_idx,
                        node="observe",
                    )
                    chunk_idx += 1

            result = await sandbox_service.execute_in_session_stream(
                session_id,
                req,
                on_chunk=_on_repl_chunk if emitter is not None else None,
            )
            output = result.stdout
            if result.stderr:
                output = f"{output}\n{result.stderr}" if output else result.stderr
            truncated_output, is_truncated = _truncate_output(output)
            status = "completed" if result.status == "completed" and result.exit_code == 0 else "error"
            return status, truncated_output, result.exit_code, is_truncated

        elif name == "finish_rlm_task":
            answer = args.get("final_answer", "")
            return "completed", f"FINAL_ANSWER: {answer}", 0, False

        elif name == "load_skill":
            return await execute_load_skill(args)

        elif name in VIBE_TOOL_NAMES:
            return await execute_vibe_tool(
                name=name,
                args=args,
                session_id=session_id,
                ctx=ctx,
                emitter=emitter,
                tool_call_id=tool_call_id,
            )

        else:
            return "error", f"Unknown tool: '{name}'", 1, False

    except Exception as exc:
        logger.exception("Error executing tool %s: %s", name, exc)
        return "error", f"Tool execution error: {str(exc)}", 1, False
