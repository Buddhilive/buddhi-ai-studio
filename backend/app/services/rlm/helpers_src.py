"""In-sandbox helper code injected into OpenSandbox sessions for RLM execution."""

RLM_HELPERS_CODE = '''"""RLM (Recursive Language Model) In-Sandbox Helper Library."""
from __future__ import annotations

import fnmatch
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

SPOOL_DIR = Path(".rlm_spool")


def ensure_spool() -> Path:
    SPOOL_DIR.mkdir(parents=True, exist_ok=True)
    return SPOOL_DIR


def chunk_file(path: str, max_chars: int = 7000, overlap_chars: int = 200) -> list[dict[str, Any]]:
    """Chunks a file into snippets bounded by max_chars with small overlap."""
    p = Path(path)
    if not p.exists() or not p.is_file():
        return []

    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return [{"path": str(p), "index": 0, "content": f"[Error reading file: {exc}]"}]

    if not text:
        return []

    chunks = []
    start = 0
    total_len = len(text)
    chunk_idx = 0

    while start < total_len:
        end = min(start + max_chars, total_len)
        # Try to break at a newline if not at EOF
        if end < total_len:
            last_newline = text.rfind("\\n", start, end)
            if last_newline > start + (max_chars // 2):
                end = last_newline + 1

        chunk_text = text[start:end]
        chunks.append({
            "path": str(p),
            "index": chunk_idx,
            "start_char": start,
            "end_char": end,
            "content": chunk_text,
        })
        chunk_idx += 1
        if end >= total_len:
            break
        start = max(start + 1, end - overlap_chars)

    return chunks


def grep_repo(pattern: str, file_pattern: str = "*", root_dir: str = ".") -> list[dict[str, Any]]:
    """Searches for regex pattern in repository files matching file_pattern."""
    regex = re.compile(pattern, re.IGNORECASE)
    results = []
    root = Path(root_dir)

    ignore_dirs = {".git", ".next", "node_modules", ".venv", "__pycache__", ".rlm_spool"}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
        for fname in filenames:
            if not fnmatch.fnmatch(fname, file_pattern):
                continue
            file_path = Path(dirpath) / fname
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for line_no, line in enumerate(content.splitlines(), start=1):
                    if regex.search(line):
                        results.append({
                            "file": str(file_path),
                            "line": line_no,
                            "match": line.strip()[:200],
                        })
                        if len(results) >= 200:
                            return results
            except Exception:
                continue

    return results


def _submit_request(payload: dict[str, Any], timeout_s: float = 60.0) -> dict[str, Any]:
    ensure_spool()
    req_id = payload.get("req_id") or uuid.uuid4().hex[:10]
    payload["req_id"] = req_id

    req_file = SPOOL_DIR / f"req-{req_id}.json"
    res_file = SPOOL_DIR / f"res-{req_id}.json"

    # Write request
    req_file.write_text(json.dumps(payload), encoding="utf-8")

    # Poll for response
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        if res_file.exists():
            try:
                data = json.loads(res_file.read_text(encoding="utf-8"))
                # Clean up response file
                try:
                    res_file.unlink()
                except OSError:
                    pass
                return data
            except Exception:
                pass
        time.sleep(0.05)

    return {
        "status": "error",
        "error": f"Timeout waiting for subcall response after {timeout_s}s",
        "req_id": req_id,
    }


def llm_query(snippet: str, subtask: str, depth: int = 1, timeout_s: float = 60.0) -> str:
    """Executes a subcall query on a snippet against LiteRT."""
    req = {
        "type": "query",
        "snippet": snippet,
        "subtask": subtask,
        "depth": depth,
    }
    res = _submit_request(req, timeout_s=timeout_s)
    if res.get("status") == "success":
        return res.get("result", "")
    return f"[Error in llm_query: {res.get('error', 'unknown error')}]"


def llm_query_batch(items: list[dict[str, str]], depth: int = 1, timeout_s: float = 120.0) -> list[str]:
    """Executes a batch of subcall queries on snippets in parallel."""
    if not items:
        return []

    req = {
        "type": "batch_query",
        "items": items,
        "depth": depth,
    }
    res = _submit_request(req, timeout_s=timeout_s)
    if res.get("status") == "success":
        return res.get("results", [])
    err = res.get("error", "unknown error")
    return [f"[Error in llm_query_batch: {err}]" for _ in items]
'''
