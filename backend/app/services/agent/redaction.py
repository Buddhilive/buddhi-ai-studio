from __future__ import annotations

import re
from typing import Any

from app.core.config import settings

_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(Authorization\s*:\s*(?:Bearer|Basic)\s+)[^\s\"']+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"\b(Bearer\s+)[A-Za-z0-9._\-]{12,}", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"\b(hf_[A-Za-z0-9]{10,})\b"), "[REDACTED_HF_TOKEN]"),
    (re.compile(r"\b(sk-[A-Za-z0-9_\-]{16,})\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\b(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"), "[REDACTED_GH_TOKEN]"),
    (re.compile(r"\b(AKIA[0-9A-Z]{16})\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r"(https?://[^:\s/@]+:)[^@\s/]+(@)"), r"\1[REDACTED]\2"),
    (
        re.compile(
            r"""((?:api_key|apikey|token|secret|password|passwd|private_key)["']?\s*[:=]\s*["']?)([^\s"',}\]]{4,})""",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]",
    ),
)

_DEFAULT_PLACEHOLDERS = {
    "changeme-opensandbox-key",
    "changeme-crawl4ai-token",
    "changeme-rustfs-secret-key",
}


def _runtime_secrets() -> list[str]:
    candidates = [
        getattr(settings, "opensandbox_api_key", ""),
        getattr(settings, "crawl4ai_api_token", ""),
        getattr(settings, "rustfs_secret_key", ""),
    ]
    try:
        from app.core.settings_store import get_hf_token

        hf_token = get_hf_token()
        if hf_token:
            candidates.append(hf_token)
    except Exception:
        pass
    return [s for s in candidates if s and len(s) >= 8 and s not in _DEFAULT_PLACEHOLDERS]


def redact_text(text: str) -> str:
    """Scrub known secret patterns and runtime credentials from text."""
    if not text:
        return text
    scrubbed = text
    for secret in _runtime_secrets():
        if secret in scrubbed:
            scrubbed = scrubbed.replace(secret, "[REDACTED]")
    for pattern, replacement in _SECRET_PATTERNS:
        scrubbed = pattern.sub(replacement, scrubbed)
    return scrubbed


def truncate_utf8_bytes(text: str, max_bytes: int) -> tuple[str, bool]:
    """Truncate text to at most max_bytes UTF-8 bytes without splitting multi-byte codepoints."""
    if max_bytes <= 0 or not text:
        return ("", bool(text)) if max_bytes <= 0 else (text, False)
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text, False
    truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
    return f"{truncated}\n...[truncated]", True


def sanitize_event_data(event_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """Redact secrets and enforce UTF-8 byte caps on high-volume event fields."""
    if not data:
        return data
    out = dict(data)
    if event_type == "tool.output.delta" and isinstance(out.get("delta"), str):
        scrubbed = redact_text(out["delta"])
        capped, was_truncated = truncate_utf8_bytes(scrubbed, 4096)
        out["delta"] = capped
        if was_truncated:
            out["truncated"] = True
    elif event_type == "tool.result" and isinstance(out.get("output"), str):
        scrubbed = redact_text(out["output"])
        capped, was_truncated = truncate_utf8_bytes(scrubbed, 16384)
        out["output"] = capped
        if was_truncated:
            out["truncated"] = True
    elif event_type == "tool.call" and "arguments" in out:
        args = out["arguments"]
        if isinstance(args, str):
            out["arguments"], _ = truncate_utf8_bytes(redact_text(args), 16384)
        elif isinstance(args, dict):
            out["arguments"] = {
                k: redact_text(v) if isinstance(v, str) else v
                for k, v in args.items()
            }
    elif event_type == "error" and isinstance(out.get("message"), str):
        out["message"], _ = truncate_utf8_bytes(redact_text(out["message"]), 8192)
    return out
