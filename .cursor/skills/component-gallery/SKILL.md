# Component Gallery

Load when adding or updating gallery entries or fingerprint tests. Successor
to Farm OS `gallery-curation`. Authority:
`docs/planning/dde-frontend-ux-playbook.md` §4.4, §6.4.

## Steps

1. One entry per surface × state combination. Name = `Surface_State`
   (`overview.ready`, `mission-control.paused`, `connection.unreachable`).
2. Sample data is permitted inside prototypes/gallery only, marked
   `data-sample="demo"`, and must be realistic enough to judge hierarchy,
   rhythm, and states (playbook §8.3 P4 line). Production honesty law
   (`clientHonesty.test.ts`) is unchanged.
3. Regenerate fingerprints/screenshots; confirm zero diffs beyond the intended
   change. Unexplained diff = fix or explain in the PR.
4. Regenerate `index.html` from screens + `flows.json`; never hand-edit it.
5. When introducing a new layout pattern, update the pattern map in the
   binding rule (`.cursor/rules/dde-design-guardrails.mdc`) — one surface,
   one pattern.

## Commands

- Studio suite: `npm --prefix interfaces/dde-studio test`
- Visual fingerprints only: `npm --prefix interfaces/dde-studio run test:visual`
- Lint debt check: `just design-lints`
