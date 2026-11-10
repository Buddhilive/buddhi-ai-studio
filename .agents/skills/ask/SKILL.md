---
name: ask
description: Answer user questions about the codebase using the code graph and OKF documentation, after updating the graph. Use when the user asks architecture or code queries with /ask or asks general questions about symbols and relationships.
version: 1.0.0
requires_agents: terminal-runner
requires_skills: okf-context
artifact_outputs: none
---

# /ask

$ARGUMENTS

Answer queries and explain architecture, functions, classes, and workflows in this codebase.
Grounded in Buddhi's topological code graph and OKF documentation. No code writing in this skill.

## Steps

1. **Update code graph**: Run `buddhi generate` via the `terminal-runner` agent to ensure the
   code graph (`.buddhi/graphs/tree-graph.db` and `tree-graph.json`) is fully up to date with the
   latest codebase state.
2. **Query code graph and docs**:
   - Use Buddhi MCP tools (`buddhi_search` and `buddhi_read`, see the `okf-context` skill) to find
     relevant symbols, functions, classes, and community clusters matching the user's query.
   - If MCP tools are unavailable or return no matches, query `.buddhi/graphs/tree-graph.db`
     directly using SQLite or inspect `.buddhi/docs/`.
3. **Formulate grounded answer**:
   - Provide a concise, direct explanation answering the user's question.
   - Include specific `file:line` citations (e.g. `src/module/service.py:45-60`) for every key
     claim, symbol definition, and call-site.
   - Explain interactions between components (callers, callees, dependencies) using the code
     graph structure.
   - If the user's question is ambiguous, ask a clarifying question while offering concrete
     possibilities grounded in what was found in the graph.

