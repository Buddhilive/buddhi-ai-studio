---
name: antislop
version: 1.0.0
priority: P1
trigger: always_on
---

# Anti-slop protocol

> Adapted from antislop (MIT License, Copyright (c) 2026 Miqdad Badjuber).

You use antislop (Anti Slop: Rules for AI Coding Agents). It is a filter, not a style guide: it stops generic AI slop in generated UI, copy, and code, without prescribing aesthetics.

For UI, copy, people, mobile layout, or code comments work, consult the matching antislop skill under `.agents/skills/` before starting (read its `SKILL.md`):
- Core filter, always on: `.agents/skills/antislop/SKILL.md`
- UI / visual: `.agents/skills/antislop-ui/SKILL.md`
- Copy & text: `.agents/skills/antislop-copywriting/SKILL.md`
- People: `.agents/skills/antislop-human/SKILL.md`
- Mobile / responsive: `.agents/skills/antislop-layoutmobile/SKILL.md`
- Code comments: `.agents/skills/antislop-code/SKILL.md`

Before starting, follow the core's "Two Usage Modes" section: explicit session instruction first, then global preference, then ask. For a resolved mode, announce `antislop active: <mode> (session override).` or `antislop active: <mode> (global preference).` once, using the actual mode and source. Ask only when no mode is resolved.


When styling UI or building components, always adhere to the repository DESIGN.md design system contract and tokens when present.
