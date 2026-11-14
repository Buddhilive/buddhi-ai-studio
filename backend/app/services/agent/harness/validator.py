from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any

from app.services.agent.harness.models import (
    HARNESS_COMPONENT_KEYS,
    HarnessComponents,
    OverlayDiff,
)

WORKSPACE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

# Per-component byte limits to prevent context bloat on small local models
COMPONENT_MAX_BYTES: dict[str, int] = {
    "system_prompt": 4096,
    "guardrails": 4096,
    "memory": 8192,
    "tool_guidance": 6144,
    "subagents": 4096,
    "skills": 16384,
    "scripts": 16384,
    "plugins": 4096,
}

# Patterns that attempt to bypass Goldfish, OpenSandbox, or file boundaries
_FORBIDDEN_INSTRUCTION_PATTERNS = (
    re.compile(r"ignore\s+(?:allowed_write_paths|target[_\s]scope|file[_\s]boundary|guardrails)", re.IGNORECASE),
    re.compile(r"skip\s+goldfish[_\s]?(?:verify|review)", re.IGNORECASE),
    re.compile(r"always\s+(?:emit|return|output)\s+VERDICT\s*:\s*pass", re.IGNORECASE),
    re.compile(r"disable\s+sandbox", re.IGNORECASE),
    re.compile(r"execute\s+on\s+(?:the\s+)?host", re.IGNORECASE),
)

_FORBIDDEN_SCRIPT_PATTERNS = (
    re.compile(r"/var/run/docker\.sock"),
    re.compile(r"localhost:8090|opensandbox_api_key|rustfs_secret_key|crawl4ai_api_token"),
    re.compile(r"\b(?:ctypes|ptrace|subprocess\.Popen\s*\(.*shell\s*=\s*True)\b"),
    re.compile(r"\b(?:curl|wget|nc|ncat)\s+https?://", re.IGNORECASE),
)

_ALLOWED_PLUGIN_KEYS = {"name", "kind", "enabled", "description", "config"}
_ALLOWED_PLUGIN_KINDS = {"mcp", "middleware", "hook", "tool_filter"}

_INJECTION_MARKERS = (
    re.compile(r"<\|tool_call>.*?<tool_call\|>", re.DOTALL),
    re.compile(r"<\|tool_call>|<tool_call\|>"),
    re.compile(r"(?im)^\s*VERDICT\s*:\s*(?:pass|retry|continue)\b.*$"),
    re.compile(r"(?im)^\s*(?:SYSTEM|ASSISTANT|DEVELOPER)\s*:\s*"),
)


@dataclass
class ValidationResult:
    valid: bool
    violations: list[str] = field(default_factory=list)


def validate_workspace_id(workspace_id: str) -> bool:
    return bool(WORKSPACE_ID_PATTERN.match(workspace_id or ""))


def sanitize_experience_text(text: str, max_chars: int = 800) -> str:
    """Strip tool-call tags, verdict markers, and role-spoofing headers from EXPERIENCE text."""
    cleaned = text or ""
    for pattern in _INJECTION_MARKERS:
        cleaned = pattern.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_chars]


class HarnessStaticValidator:
    """Pre-probe and pre-compose static guardrail gate for HarnessOverlay diffs."""

    @staticmethod
    def validate_diff(
        diff: OverlayDiff,
        baseline: HarnessComponents | None = None,
    ) -> ValidationResult:
        violations: list[str] = []

        for key, value in diff.updates.items():
            if key not in HARNESS_COMPONENT_KEYS:
                violations.append(f"Unknown harness component: {key}")
                continue

            serialized_size = len(str(value).encode("utf-8"))
            max_bytes = COMPONENT_MAX_BYTES.get(key, 4096)
            if serialized_size > max_bytes:
                violations.append(
                    f"Component '{key}' exceeds size cap ({serialized_size} > {max_bytes} bytes)"
                )

            if key == "guardrails":
                if not isinstance(value, str):
                    violations.append("guardrails must be a string")
                else:
                    if baseline and baseline.guardrails and baseline.guardrails not in value:
                        violations.append("guardrails is append-only; existing rules cannot be removed")
                    for pat in _FORBIDDEN_INSTRUCTION_PATTERNS:
                        if pat.search(value):
                            violations.append(f"guardrails contains forbidden relaxation pattern: {pat.pattern}")

            elif key in ("system_prompt", "tool_guidance", "subagents", "memory"):
                text = value if isinstance(value, str) else str(value)
                for pat in _FORBIDDEN_INSTRUCTION_PATTERNS:
                    if pat.search(text):
                        violations.append(f"{key} contains forbidden guardrail bypass directive")

            elif key == "scripts":
                if not isinstance(value, dict):
                    violations.append("scripts must be a dict[str, str]")
                else:
                    for script_name, script_body in value.items():
                        if not isinstance(script_body, str):
                            violations.append(f"Script '{script_name}' body must be string")
                            continue
                        if ".." in script_name or script_name.startswith("/"):
                            violations.append(f"Unsafe script path '{script_name}'")
                        for pat in _FORBIDDEN_SCRIPT_PATTERNS:
                            if pat.search(script_body):
                                violations.append(f"Script '{script_name}' violates sandbox isolation ({pat.pattern})")
                        if script_name.endswith(".py"):
                            try:
                                tree = ast.parse(script_body)
                                for node in ast.walk(tree):
                                    if isinstance(node, ast.Import):
                                        for alias in node.names:
                                            if alias.name in {"ctypes", "pty", "fcntl"}:
                                                violations.append(f"Forbidden import '{alias.name}' in '{script_name}'")
                                    elif isinstance(node, ast.ImportFrom) and node.module in {"ctypes", "pty", "fcntl"}:
                                        violations.append(f"Forbidden import '{node.module}' in '{script_name}'")
                            except SyntaxError as exc:
                                violations.append(f"Python syntax error in script '{script_name}': {exc.msg}")

            elif key == "plugins":
                if not isinstance(value, list):
                    violations.append("plugins must be a list of declarative dicts")
                else:
                    for idx, item in enumerate(value):
                        if not isinstance(item, dict):
                            violations.append(f"Plugin[{idx}] must be a dict")
                            continue
                        unknown_keys = set(item.keys()) - _ALLOWED_PLUGIN_KEYS
                        if unknown_keys:
                            violations.append(f"Plugin[{idx}] has disallowed keys: {sorted(unknown_keys)}")
                        kind = item.get("kind")
                        if kind not in _ALLOWED_PLUGIN_KINDS:
                            violations.append(f"Plugin[{idx}] has unsupported kind '{kind}'")

        return ValidationResult(valid=len(violations) == 0, violations=violations)
