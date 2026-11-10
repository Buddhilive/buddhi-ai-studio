---
name: rtk
description: Use the RTK token-saving command runner, inspect compression gains, manage filters, and audit raw execution logs.
version: 1.0.0
requires_agents: terminal-runner
artifact_outputs: none
---

# /rtk

$ARGUMENTS

Manage and execute token-saving filtered commands using `buddhi scripts rtk`.

## Subcommands

1. **Run a command through RTK**:
   ```bash
   buddhi scripts rtk run -- <command...>
   ```
   - Filters noise, progress indicators, and redundant lines.
   - Retains all error, failure, traceback, and summary lines.
   - Preserves the exact process exit code.
   - If the command fails, the full raw log is saved under `.buddhi/rtk/raw/` and its path is printed.

2. **Run with raw output**:
   ```bash
   buddhi scripts rtk run --raw -- <command...>
   ```

3. **Check whether a command is rewritten**:
   ```bash
   buddhi scripts rtk rewrite <command...>
   buddhi scripts rtk rewrite --json <command...>
   ```

4. **View token savings**:
   ```bash
   buddhi scripts rtk gain
   ```

5. **List and test filters**:
   ```bash
   buddhi scripts rtk filters list
   buddhi scripts rtk filters test <filter-name>
   ```
