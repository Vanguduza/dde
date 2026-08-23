# Screen Implementation

Load before implementing or restyling any DDE surface (webview HTML/CSS in
`interfaces/dde-studio/shared/**/*.ts`). Authority:
`docs/planning/dde-frontend-ux-playbook.md` §4, §6.1.

## Steps

1. Read playbook §1 and §4. Identify the ONE declared pattern for this surface
   (dashboard `ov-*` grid; mission-control columnar shell; status/form panels;
   settings form). No pattern fits? STOP → propose an EDR. Do not improvise.
2. Produce or refresh the prototype set first (see `prototype-authoring`):
   screens × states, `flows.json`, regenerated `index.html`, motion tokens,
   reduced-motion variants.
3. Implement in `shared/ui/*.ts` composing ONLY token references
   (`tokenCssRoot()` variables) and shared primitives (`banner`, `pill`,
   `row`, `emptyState`). Declare idle/loading/empty/error/disabled for every
   interactive surface.
4. Extend/adjust the surface's fingerprint assertions in the same PR
   (`overviewVisual.test.ts` style). Run `npm test` in `interfaces/dde-studio`.
5. Self-audit against playbook §8.1; check `just design-lints` adds no debt;
   attach gallery screenshots to the PR; add a `References:` footer if any
   pattern was mined from a repo.

## Hard rules

- Never inline hex/px/motion literals — edit `schemas/design/tokens.json` and
  regenerate instead (`uv run python -m scripts.generate_design_tokens`).
- Empty states: shared stroke icon + one-line factual title. No essays.
- Copy passes the honesty gate (verb-first, sentence case, no exclamation).
- Tests green ≠ UI done: owner pixel sign-off still gates the merge.
