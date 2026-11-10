# Skill Format Specification & Altitude Rules

This document specifies the format, altitude, and structure required for all self-learned skills.

## 1. Frontmatter
Every `SKILL.md` must open with a YAML frontmatter block:
```yaml
---
name: lowercase-hyphenated-name
description: Trigger-first description. Max 60 chars. Must contain 'when' or a quoted trigger phrase.
category: general
---
```
Allowed categories: `git`, `testing`, `debugging`, `api`, `database`, `ui`, `build`, `architecture`, `workflow`, `documentation`, `general`, `performance`, `security`.

## 2. Altitude Cap
- `SKILL.md` body must have **at most 25 non-blank lines**.
- The main file holds the durable rule, entrypoint commands, and completion criteria.
- Deep reference, bulky tables, templates, and scripts belong in subfiles (`references/`, `templates/`, `scripts/`, `assets/`).

## 3. Allowed Subfiles
Subfiles must live in:
- `references/`: Detailed reference documentation, API matrices, checklists.
- `templates/`: Boilerplate code or configuration snippets.
- `scripts/`: Executable python or shell helpers.
- `assets/`: Diagram files or data fixtures.

## 4. Pointers
Every subfile created must be referenced via markdown link in `SKILL.md`: `[guide](./references/guide.md)`.
Every pointer in `SKILL.md` must resolve to an existing subfile.

## 5. Security Invariants
- No secrets or credentials (API keys, tokens, private keys).
- No destructive or exfiltration commands.
- No placeholder tokens (`TODO`, `FIXME`, `XXX`).

