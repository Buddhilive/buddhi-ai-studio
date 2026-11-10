---
name: ratchet-files
description: Ratchet source file size so every file stays small enough for an agent to read whole: find every file over a token budget, split oversized files by concept, and set up the pre-commit ratchet that stops them from growing. Use when a commit is blocked because a file is over the size budget, when asked to find or split oversized/long/god files, when a file you need to change is too large to read in one pass, or when asked to add a file-size limit or hook to a repository.
---

# Ratchet Files

A source file is over budget when it is past what an agent can read in one
pass (8,000 tokens, counted as bytes / 4, unless the repository sets
another). [`buddhi scripts check-file-size`](scripts/buddhi scripts check-file-size) owns
what counts as source, the budget, the ratchet, and the split rules; run it
with `--help` before anything else.

## Splitting

1. Run the script with `--all` from the repository root, passing the
   repository's `--max-tokens` if its hook sets one. Its list is the backlog.
2. Pick the files to split: the one blocking the work in front of you, or
   with no blocker, the largest ones a change is about to touch.
3. Split each one by the rules the script prints. A seam is a concept the
   file already owns, not a line count; when
   [refactor-clean](../refactor-clean/SKILL.md) is installed, use it to find
   them.
4. Prove the split changed no behaviour with the repository's own checks,
   and commit it alone, before the change that needed the room.

A file whose every split would cost more than it saves (one table or state
machine that only reads whole) may opt out instead. Put
`@ratchet-files-ignore` in a comment within its first 10 lines, in the
file's own comment syntax, followed by why splitting fails:

```js
// @ratchet-files-ignore: one opcode table; split, each half reads without the other.
```

The check then skips the file entirely, even as it grows, so opt out only
after looking for a seam and finding none worth its cost, never to get past a
refusal. Tell the user each file you opt out and why. `--all` counts
opted-out files so they stay visible.

Done when every file you picked is under budget in its own commit, the
behaviour checks pass, and `--all` no longer lists those files.

## Setting up the ratchet

Never install the hook without the user's explicit yes, even when they asked
to set up the repository. Installing it freezes every file already over
budget, so audit first and leave the repository untouched while you do:

1. Run `buddhi scripts check-file-size --all` from the repository root.
2. Ask once, with everything the user is agreeing to: how many files the hook
   would freeze and which are largest, leaving out generated or vendored ones
   you will mark below (name those); the budget, 8,000 tokens unless they want
   another; and which pre-commit runner you will wire it into.
