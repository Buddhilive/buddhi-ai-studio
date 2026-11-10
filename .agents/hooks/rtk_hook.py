#!/usr/bin/env python3
"""RTK PreToolUse lifecycle hook for Google Antigravity.

Intercepts tool execution requests, rewrites supported command lines to route
through `buddhi scripts rtk run -- <cmd>` for 60-90% token reduction, and outputs
an overwrite payload. Always fail-open and exits 0 on any condition.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure local src/ is accessible if buddhi is not installed in system Python
_repo_root = Path(__file__).resolve().parent.parent.parent
_src_dir = _repo_root / "src"
if _src_dir.is_dir() and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))


def main() -> None:
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            print(json.dumps({}))
            return

        payload = json.loads(raw_input)
        from buddhi.scripts.rtk.hook_handler import handle_hook_payload

        response = handle_hook_payload(payload)
        print(json.dumps(response))
    except Exception:  # noqa: BLE001 - must never block tool use on this hook's own bugs
        # Strict fail-open: Never break tool execution on hook failure
        print(json.dumps({}))


if __name__ == "__main__":
    main()
