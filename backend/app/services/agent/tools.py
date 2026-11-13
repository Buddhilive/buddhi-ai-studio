from __future__ import annotations

import json
import logging
from typing import Any, Tuple

from app.core.config import settings
from app.schemas.chat import FunctionDefinition, ToolDefinition
from app.schemas.sandbox import SandboxExecutionRequest, SandboxSessionCreateRequest
from app.services.sandbox_service import sandbox_service

logger = logging.getLogger(__name__)

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
    return new_session.session_id


async def execute_tool(
    name: str,
    args: dict[str, Any] | str,
    session_id: str,
) -> tuple[str, str, int, bool]:
    """
    Execute a tool against the sandbox session.
    Returns (status, output, exit_code, truncated).
    Status is 'completed' or 'error'.
    """
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {"raw_args": args}

    try:
        if name == "run_command":
            cmd = args.get("command", "")
            if not cmd:
                return "error", "Error: 'command' argument is required", 1, False
            req = SandboxExecutionRequest(
                code=cmd,
                language="bash",
                timeout_s=settings.sandbox_default_timeout_s,
            )
            result = await sandbox_service.execute_in_session(session_id, req)
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
            await sandbox_service.write_session_file(session_id, path, content)
            return "completed", f"File '{path}' written successfully ({len(content)} bytes).", 0, False

        elif name == "read_file":
            path = args.get("path")
            if not path:
                return "error", "Error: 'path' argument is required", 1, False
            content = await sandbox_service.read_session_file(session_id, path)
            truncated_content, is_truncated = _truncate_output(content)
            return "completed", truncated_content, 0, is_truncated

        elif name == "list_files":
            path = args.get("path", ".")
            req = SandboxExecutionRequest(
                code=f"find {path} -maxdepth 3 -not -path '*/.*'",
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
            result = await sandbox_service.execute_in_session(session_id, req)
            output = result.stdout
            if result.stderr:
                output = f"{output}\n{result.stderr}" if output else result.stderr
            truncated_output, is_truncated = _truncate_output(output)
            status = "completed" if result.status == "completed" and result.exit_code == 0 else "error"
            return status, truncated_output, result.exit_code, is_truncated

        elif name == "finish_rlm_task":
            answer = args.get("final_answer", "")
            return "completed", f"FINAL_ANSWER: {answer}", 0, False

        else:
            return "error", f"Unknown tool: '{name}'", 1, False

    except Exception as exc:
        logger.exception("Error executing tool %s: %s", name, exc)
        return "error", f"Tool execution error: {str(exc)}", 1, False
