---
name: system-design
description: Use as a framework for nontrivial architecture and trade-off decisions, grounding the choice in this codebase's actual constraints rather than textbook patterns.
when_to_use: "When a request involves a nontrivial structural decision — a new service/module boundary, a storage choice, sync-vs-async, introducing a new dependency or architectural pattern. Not for routine CRUD additions or simple code changes that don't involve a real structural choice."
allowed-tools: Read, Glob, Grep
version: 1.0.0
---

# Ground architecture decisions in real constraints

Nontrivial structural decisions — a new service boundary, a storage choice,
sync-vs-async, introducing a dependency or pattern — deserve more than
improvisation. Start minimal: add complexity only when an actual, stated
constraint requires it, not a hypothetical future need. This is the same
discipline buddhi already expects of generated code; this skill just applies
it to the decision itself.

## How to use it

1. Pull the real constraints. Read `.buddhi/docs/` and query the code graph
   (see the `okf-context` skill) for the subsystem the decision touches — its
   current boundaries, what already talks to what — instead of assuming
   generic constraints that don't apply here.
2. Enumerate 2-3 real alternatives grounded in what this codebase already
   does or already depends on, not a textbook list of generic options
   unrelated to the actual stack.
3. State the trade-offs of each alternative explicitly — what it gains, what
   it costs — rather than picking one silently and presenting it as the only
   option.
4. Once a decision is made, record it: use the `/remember` workflow to write
   it into `.agents/memory/tech-decisions.md`, so the reasoning survives past
   this conversation and future specialists don't re-litigate it from
   scratch.

This skill is for the decision itself, not an invitation to redesign working
code — most requests don't need it. Reach for it only when a request
genuinely turns on a structural choice; a routine CRUD addition or a simple,
well-contained code change should proceed without it.
