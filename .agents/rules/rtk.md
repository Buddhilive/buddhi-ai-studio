---
name: rtk
version: 1.0.0
priority: P1
trigger: always_on
---

# RTK Token-Saving Output Filter Protocol

To preserve agent context and avoid wasting tokens on verbose shell and test outputs:

1. **Automatic Filtering**:
   - High-noise CLI commands (e.g. `git status`, `git diff`, `git log`, `pytest`, `ruff`, `mypy`, `cargo`, `npm`, `docker`) are automatically intercepted and compressed by the PreToolUse RTK hook into `buddhi scripts rtk run -- <command>`.
2. **Direct CLI Invocations**:
   - When running exploratory, diagnostic, or verification commands directly, prefer invoking them via `buddhi scripts rtk run -- <command>`.
   - To bypass filtering and obtain verbatim raw output, append the `--raw` flag: `buddhi scripts rtk run --raw -- <command>`.
3. **Auditing & Raw Output Recovery**:
   - Filtering never suppresses failure lines, tracebacks, error summaries, or exit codes.
   - When a command fails (exit code != 0), the full, unmodified raw output is automatically saved to `.buddhi/rtk/raw/<timestamp>_<cmd>.log`.
   - The runner emits `[rtk: full raw output saved to <path>]` on failure. When analyzing test or build failures, refer to this path if deeper debug context is needed.
4. **Safety & Fail-Open Guarantee**:
   - The RTK hook and runner fail open. If a filter fails or is missing, output passes through safely without blocking the tool call.
