---
name: harness-core
version: 1.0.0
priority: P0
trigger: always_on
---

# Harness core protocol

- Before reading raw source to understand how this codebase works, consult
  `.buddhi/docs/` (OKF docs) and use the Buddhi MCP tools (`buddhi_search`, `buddhi_read`,
  see the `okf-context` skill) for structural queries ("what calls this", "what depends on
  this", symbol search). Only fall back to direct graph queries (`.buddhi/graphs/tree-graph.db` /
  `tree-graph.json`) or grepping raw source when MCP tools or docs do not answer the question.
- A request that spans more than one domain (e.g. "add a feature" touching UI,
  an API, and a schema change) should go through the `/plan` workflow before any
  code is written, so the relevant specialist agents can ground a plan in the
  actual codebase rather than generic advice.
- Destructive operations — force-push, `git reset --hard`, dropping or truncating
  a database table, deploying to a production environment — require explicit
  user confirmation first. Never chain one of these into a larger command without
  a stop for confirmation. This is now also enforced mechanically: `.agents/hooks.json`
  registers a `PreToolUse` hook (`.agents/hooks/guard_destructive.py`) that denies
  these same categories of command outright as a backstop — the rule above still
  matters for judgment calls the hook's pattern-matching can't cover (e.g. "deploying
  to production" is not a single grep-able command). Once the user has explicitly
  confirmed a command the hook would otherwise deny, include the literal marker
  string `CONFIRMED` in the command text — that is what lets the mechanical hook
  allow it through.
- Prefer delegating verbose or exploratory shell/build/test command execution to
  the `terminal-runner` subagent instead of running it inline: it reports back a
  condensed, no-bluff summary instead of raw output, keeping the main agent's
  context lean for reasoning.
- `.agents/memory/MEMORY.md` is an index into topic files under
  `.agents/memory/` — `user-preferences.md`, `project-conventions.md`,
  `tech-decisions.md`, `feedback-history.md`. Read the index at session start
  for durable project conventions and prior decisions. When `/plan` or other
  harness work surfaces a convention or decision worth keeping across
  sessions, append it to the matching topic file and add a pointer to the
  index, rather than letting it live only in this conversation. Use the
  `/remember` workflow for the same thing when the user explicitly asks to
  capture something.
