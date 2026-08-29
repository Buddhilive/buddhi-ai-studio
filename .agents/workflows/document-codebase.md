---
name: document-codebase
description: Generate or refresh OKF codebase documentation under .buddhi/docs/, using buddhi's code graph and RepoAgent-style bottom-up doc generation.
version: 1.0.0
requires_agents: none
requires_skills: repoagent-doc-generation, okf-context
artifact_outputs: docs-plan, okf-docs
---

# /document-codebase

$ARGUMENTS

Generate or refresh this codebase's OKF documentation under `.buddhi/docs/`, using
buddhi's code graph and the RepoAgent-style bottom-up doc-generation method.

## Steps

1. Run `buddhi docs plan` in the project root (use `buddhi init` instead if
   `.buddhi/` or `.agents/` don't exist yet). This refreshes `.buddhi/docs-plan.json`
   against the current source tree.
2. Apply the `repoagent-doc-generation` skill: read the plan, process every entry
   with `needs_generation: true` in the order given, write each OKF concept doc,
   and update the affected `index.md` / `log.md` files.
3. Report a summary: how many entries were in the plan, how many were already
   current and skipped, and how many were (re)generated this run.
