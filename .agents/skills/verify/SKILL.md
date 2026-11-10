---
name: verify
description: Prove that changes work and satisfy acceptance criteria by running real build, lint, and test commands via the terminal-runner agent, mapping evidence to SDD user stories when available, and reporting genuine pass/fail evidence. Use when validating changes with /verify.
version: 1.3.0
requires_agents: terminal-runner
requires_skills: okf-context
optional_skills: compare-screenshots, screenshot-critique, refactor-clean, code-review, write-docs, a11y, rtk
artifact_outputs: verification-report
---

# /verify

$ARGUMENTS

Prove that changes work by actually running real verification commands and mapping results
against acceptance criteria, rather than claiming success from static reading.

## Steps

1. **Check feature context (SDD convergence check)**:
   Run `buddhi sdd check --paths-only --json` (via the `terminal-runner` agent).
   - If a valid feature spec (`FEATURE_SPEC`) and tasks (`TASKS`) exist for the current branch,
     operate in **SDD Convergence Mode**: read `spec.md` to extract each user story's acceptance
     scenarios (Given/When/Then) and success criteria (`SC-001`...).
   - If no feature context is active, operate in **Generic Verification Mode**.
2. **Identify changed scope**:
   Run `git diff` / `git status` (via `terminal-runner`) to determine changed files, or use the
   explicit target specified in `$ARGUMENTS`.
3. **Determine project verification commands**:
   Consult `.buddhi/docs/` and query the code graph via Buddhi MCP tools (`buddhi_search`,
   `buddhi_read`, see the `okf-context` skill) plus the project's manifest/build configuration
   files to detect the exact build, lint, typecheck, and test commands genuinely used by this
   project. Never guess or assume generic commands without confirming them in project configuration.
4. **Execute verification via terminal-runner**:
   Execute every verification command exclusively through the `terminal-runner` agent. Commands
   should leverage `buddhi scripts rtk run --` to keep context lean while preserving all errors
   and saving full raw logs under `.buddhi/rtk/raw/` on failure for complete auditability.
5. **Visual & Accessibility verification gates (for UI/Visual changes)**:
   - When the feature touches UI, visual styling, or frontend templates:
     * Run `buddhi scripts verify-a11y` (or MCP `verify_a11y`) via the `terminal-runner` agent to run the static gate (anti-patterns, contrast evidence, freshness, and artifact integrity). Verify that `REPORT.md` contains fresh execution records and passes the gate.
     * Run `buddhi scripts contrast` or MCP `check_contrast` to verify all measured pairs against WCAG floors.
     * Run `/compare-screenshots` (using `buddhi scripts visual-parity-diff`) to check objective pixel, edge, and scene metrics against the reference design.
     * Run `/screenshot-critique` using a fresh, unprimed subagent to inspect the UI, and verify the report with `buddhi scripts receipts`.
6. **Code closeout verification**:
   - Run a consolidated `/review` pass (`refactor-clean` → `code-review` → `write-docs`) to ensure the codebase remains free of legacy wrappers, dead references, and stale docs.
7. **Analyze and report evidence**:
   - Map each execution outcome (command, real exit code, filtered output, and raw recovery log path if failed) to the relevant acceptance criteria in `spec.md`.
   - Never claim a requirement is verified without presenting actual execution evidence.
