---
name: repoagent-doc-generation
description: Generates or refreshes per-symbol codebase documentation as Open Knowledge Format (OKF) markdown, in dependency order, using buddhi's code graph.
when_to_use: "When asked to document this codebase or update its docs, when .buddhi/docs-plan.json has entries with needs_generation true, or when /document-codebase is invoked."
allowed-tools: Read, Write, Bash, Glob, Grep
version: 1.0.0
---

# RepoAgent-style OKF doc generation

This project's structural truth comes from buddhi (`buddhi init` / `buddhi docs plan`),
not from you re-deriving it. Your job is only to write the prose, in the order and with
the context buddhi already computed — mirroring RepoAgent's method: AST-derived call
graph -> bottom-up topological order -> per-symbol doc with caller/callee context.

## Steps

1. Ensure the plan is current: run `buddhi docs plan` (or `buddhi init` if `.agents/`
   or `.buddhi/` don't exist yet) in the project root. This writes/refreshes
   `.buddhi/docs-plan.json`.
2. Read `.buddhi/docs-plan.json`. It is a JSON array, **already in dependency order**
   (every `callees` entry appears earlier in the array than its caller). Each entry has:
   - `node_id`, `kind` (`module`/`class`/`function`/`method`), `name`, `qualified_name`
   - `file_path`, `start_line`, `end_line`, `snippet` — the source to document
   - `content_hash` — hash of the current snippet
   - `callers` / `callees` — `node_id`s of related symbols
   - `doc_path` — where the OKF file for this node belongs (relative to repo root)
   - `needs_generation` — `false` means an up-to-date doc already exists; skip it
3. Process entries **in array order**, skipping any with `needs_generation: false`.
   For each one you process:
   - If `callees` already have docs on disk (check `doc_path` of those entries), skim
     them for context — same as RepoAgent enriching a doc with what it calls.
   - Write the OKF file at `doc_path` following the schema in the next section.
   - Do not invent behavior you can't see in `snippet`; if the snippet is truncated or
     the logic depends on something outside it, say so plainly rather than guessing.
4. After processing all pending entries, update the OKF index for every directory that
   received a new or changed doc: create/refresh that directory's `index.md` (see
   OKF index conventions below) and append an entry to the bundle root's `.buddhi/docs/log.md`.

## OKF concept-doc schema

One file per `doc_path`. Frontmatter is YAML; keep the `content_hash` field exact —
that's how the next planning run knows this doc is current.

```yaml
---
type: Function            # or Class / Module — from the plan entry's "kind"
title: <qualified_name>
description: <one sentence, plain language>
tags: [<language>, <file_path>]
status: stable
generated: { by: antigravity/<your-model-id>, at: <ISO8601 timestamp> }
sources:
  - id: src
    resource: <file_path>#L<start_line>-L<end_line>
    content_hash: <content_hash from the plan entry, unchanged>
---

# Summary
<what this symbol does and why it exists, in plain language>

# Signature
<the declared signature/interface>

# Relationships
Calls: <qualified names of callees, or "none">
Called by: <qualified names of callers, or "none">
```

Do not add OKF's Attested Computation fields (`runtime`, `parameters`, `executor`,
`attester`) — those are for verified data-pipeline computations, not code docs.

## Index files (`index.md`)

Each directory under `.buddhi/docs/` that contains concept docs should have an
`index.md` (no frontmatter, except the bundle root's may carry `okf_version: "0.2"`)
listing its concepts:

```markdown
* [<title>](<relative-url>) - <description>
```

## Log file (`.buddhi/docs/log.md`)

Newest entries first, one heading per date:

```markdown
## 2026-08-22
**Update**: refreshed docs for 3 changed symbols in src/buddhi/graph/builder.py.
```

