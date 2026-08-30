---
name: verify
description: Prove that changes work and satisfy acceptance criteria by running real build, lint, and test commands via the terminal-runner agent, mapping evidence to SDD user stories when available, and reporting genuine pass/fail evidence.
version: 2.0.0
requires_agents: terminal-runner
requires_skills: okf-context
artifact_outputs: verification-report, convergence-report
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
   project. Never guess or assume generic commands (e.g. `npm test`) without confirming them
   in the project configuration. If unclear, ask the user.
4. **Execute verification via terminal-runner**:
   Execute every verification command exclusively through the `terminal-runner` agent. Never execute
   verification commands directly in the main agent's context.
5. **Analyze and report evidence**:
   - For each executed command, report the exact command string, exit code, and a condensed summary
     of stdout/stderr (e.g. test counts, error lines, warnings) — never a paraphrase of expected behavior.
   - **In SDD Convergence Mode**: Map the test execution results directly back to each user story
     in `spec.md`. Report pass/fail status per user story with concrete evidence from the test output.
6. **Flag manual verification requirements**:
   Flag anything that could not be verified automatically (UI flows, browser interactions, third-party
   services, interactive prompts) as requiring manual testing. Never omit unverified requirements
   silently or claim they passed without evidence.
