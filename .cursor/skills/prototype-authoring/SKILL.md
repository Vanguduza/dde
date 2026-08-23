# Prototype Authoring

Load before producing or updating a workspace `prototypes/` directory.
Authority: `docs/planning/dde-frontend-ux-playbook.md` §5, §5.0 P1/P3/P4,
§6.6. Contract: `schemas/design/prototype_flow.schema.json`.

## Authoring steps

1. P1 checkpoint — if the charter declares `ui_plan_checkpoint: required`,
   publish the intended screens × states manifest as TEXT through the
   mission-plan/approval surface and let the owner comment window elapse
   BEFORE authoring pixels.
2. Enumerate surfaces × states from the charter; missing state = missing
   screen (`overview.ready.html`, `mission-control.empty.html`, ...).
3. Emit one self-contained HTML page per screen × state: viewport meta, lang,
   skip-link, focus-visible styles, inline `<style>` using ONLY token-sheet
   variables (same names/values as generated `tokens.ts`). No framework, no
   CDN, no build step. Mark sample data `data-sample="demo"` and make it
   realistic enough to judge hierarchy and rhythm (P4) — placeholder filler
   cannot be approved.
4. Wire `flows.json` to the current schema; every transition target must
   exist as a screen file.
5. Motion via tokens only; write the `prefers-reduced-motion` variant for
   every animated rule (end-states preserved); loops bounded ≤2s; no springs.
6. Regenerate `index.html` (gallery of every screen × state × flow);
   run the manifest validator; request the owner pixel-signoff approval.

## Refine-in-place protocol (P3)

Pixel feedback never opens a new mission cycle. Per round:

1. Annotate only the flagged screens/states.
2. Revise those pages IN PLACE — do not fork new filenames.
3. Regenerate `index.html`.
4. Deliver a delta summary naming each change against its annotation.
5. Request re-sign-off.

Two consecutive rounds with no delta on a flagged screen escalate to an EDR
candidate instead of silent churn. Per-round latency feeds the §8.4
sign-off-latency metric.
