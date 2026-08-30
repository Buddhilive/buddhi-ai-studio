---
name: remember
description: Explicitly capture a user-stated preference, project convention, technical decision, or piece of feedback into the matching memory topic file, adding a pointer to the memory index.
version: 1.0.0
requires_agents: none
artifact_outputs: memory-entry
---

# /remember

$ARGUMENTS

Explicit, user-invocable capture of something worth keeping across sessions
into the right memory topic file under `.agents/memory/`, with a pointer
added to `.agents/memory/MEMORY.md`'s index.

## Steps

1. Take the content to remember from `$ARGUMENTS`. If it's ambiguous what
   should be captured, ask the user to clarify rather than guessing.
2. Classify it as one of: user preference, project convention, tech
   decision, or feedback — matching `.agents/memory/user-preferences.md`,
   `.agents/memory/project-conventions.md`, `.agents/memory/tech-decisions.md`,
   and `.agents/memory/feedback-history.md`.
3. Append a concise entry to the matching topic file, creating the file if
   it's somehow missing.
4. Add a one-line pointer to `.agents/memory/MEMORY.md`'s index, under
   ~150 characters, naming the topic file it points into.
5. If `MEMORY.md`'s index is approaching ~200 lines, say so in the response
   as a warning rather than silently continuing to grow it.
6. Confirm back to the user which file the entry landed in and the one-line
   summary that was recorded.
