# Design Provenance Ledger

Append-only record of visual-layer-adjacent extractions from external
repositories and generator outputs (frontend/UX playbook §2.2, guardrail 15).
One row per extraction; reviewers reject unclosed borrowings; the `ui-review`
skill checks PR footers against this ledger.

| Date | Source (`repo@commit/path`) | Layer mined (§2.1) | Licence | Adaptation | PR/commit |
|---|---|---|---|---|---|
| 2026-08-22 | cocodly.com public docs/about (behavior observation only) | Process layer only: loop-shape mechanics (plan checkpoint, live preview, refine-in-place) → playbook §5.0 P1–P4 | n/a — no code or values copied | Re-specified as DDE enforcement points; zero theme/layout/motion/copy transfer | playbook v1.1 |
| 2026-08-22 | anthropics/skills `web-artifacts-builder/SKILL.md` | Pattern: self-contained single-file HTML prototype discipline | MIT (observed at research time; verify at adoption) | Re-expressed as playbook §5.1a constraints + `prototype_flow.schema.json` `constraints` block | playbook v1.0 |
