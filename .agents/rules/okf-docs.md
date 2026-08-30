---
name: okf-docs
version: 1.0.0
priority: P1
trigger: always_on
---

# OKF documentation conventions

- Generated codebase documentation lives under `.buddhi/docs/`, as Open Knowledge
  Format (OKF) markdown — one concept file per module/class/function.
- Never hand-edit a generated concept file's prose without also updating its
  `sources[0].content_hash` to match the current code, or it will look fresh when
  it's actually stale.
- Never write OKF's Attested Computation fields (`runtime`, `parameters`, `executor`,
  `attester`) into these docs — that's out of scope for code documentation here.
- After a change that alters a documented symbol's behavior or signature, prefer
  running the `/document-codebase` workflow over leaving `.buddhi/docs/` stale.
- Treat `.buddhi/docs/` as a cache of understanding, not ground truth — the source
  file named in `sources[0].resource` always wins on conflict.
