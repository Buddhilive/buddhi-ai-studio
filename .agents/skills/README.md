# Extending this harness with tech-stack skills

This directory holds Antigravity skills. Antigravity discovers every
`SKILL.md` under `.agents/skills/<name>/` automatically and activates it by
matching its `description` against what's being worked on — there is no
registry or manifest to update.

To add tech-stack-specific knowledge (a framework, a database, a deployment
platform), drop a new folder here:

```
.agents/skills/<stack-name>/SKILL.md
```

with frontmatter `name` (defaults to the folder name) and a `description`
written in third person, with the keywords that should trigger it — e.g.
"Next.js App Router conventions, data fetching, and rendering-mode choices
for this codebase." The specialist agents under `.agents/agents/` already
check for a matching stack skill before falling back to generic guidance, so
no changes are needed there when a new pack is added.

This file itself is plain documentation, not a skill — it has no `SKILL.md`
frontmatter and Antigravity will not load it as one.

Note that some skills under this directory, such as `system-design`, are
general and ship bundled with every harness rather than being stack-specific
packs you drop in — the "add a folder here" guidance above is for tech-stack
knowledge, not for these bundled skills.
