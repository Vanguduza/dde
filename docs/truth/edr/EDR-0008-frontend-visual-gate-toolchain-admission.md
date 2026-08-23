# EDR-0008 — Frontend/UX playbook Phase 1 visual-gate toolchain: adopt Playwright
# and axe-core behind one dependency-admission decision

> **Location note.** Per Chapter 3.6, an EDR is a row in the `edrs` table,
> written only by `engine/truth/`. Following the convention established in
> `EDR-0001`–`EDR-0007`, this file is a **markdown pre-image** of the eventual
> `edrs` row, filed as the proposal itself (AGENTS.md forbids editing
> `docs/truth/**` as a side effect). **This file is not itself an accepted
> EDR.** `status` is `proposed`; only a human decision can move it to
> `accepted`.

- **slug:** `EDR-0008` (provisional)
- **status:** `proposed`
- **supersedes:** none
- **affected_requirement_slugs:** none filed yet
- **raised during:** operationalization of
  `docs/planning/dde-frontend-ux-playbook.md` (v1.1). Phase 0 (token SSOT +
  codegen + drift gate, design lints with shrink-only budget, studio client
  tests PR-blocking, prototype contract) is landed without new dependencies;
  this EDR covers Phase 1 only.

## Context

Playbook guardrail 4.4 (screenshot-evidence gate, Phase B) and 4.9
(accessibility floor automation) require two capabilities no existing repo
toolchain provides:

1. Pixel-level screenshot goldens over gallery/prototype pages — DOM string
   fingerprints (`overviewVisual.test.ts`) pin structure and token usage but
   cannot see rendered geometry, contrast failures, or layout collapse at
   viewport extremes.
2. Automated WCAG 2.x A/AA evaluation of shipped surfaces — manual keyboard
   walks and contrast math in the token sheet cover design-time, not
   regression-time enforcement.

AGENTS.md Chapter 9.6 admits a new dependency only with licence, maintenance
signal, and why the stdlib/existing toolchain is insufficient.

## Decision (proposed)

Adopt exactly two dependencies, nothing else:

| Dependency | Role | Licence | Maintenance signal | Why stdlib is insufficient |
|---|---|---|---|---|
| Playwright (`@playwright/test`, Apache-2.0) | `expect(page).toHaveScreenshot()` goldens over Prototype Gallery pages: light/dark/high-contrast × reduced-motion on/off × widths 320/900/1280; baselines generated in CI container, updated only in owning PRs | Apache-2.0 | Microsoft-backed; among the most actively maintained OSS test frameworks; VS Code/Cursor ecosystem standard | Node stdlib and `node:test` have no browser runtime; rendered-pixel capture is the entire point of guardrail 4.4 |
| `@axe-core/playwright` (MPL-2.0) | WCAG scan per gallery page, tags `wcag2a,wcag2aa,wcag22aa`, zero critical/serious violations gating the PR, target-size rule enabled | MPL-2.0 (file-level copyleft; used as dependency, not modified) | Deque Systems; axe-core is the industry-standard rules engine consumed by major CI platforms | Accessibility rule evaluation against live DOM cannot be reproduced from static strings |

Explicitly rejected (recorded to stop re-litigation): Storybook/Ladle (no
component framework or bundler), Chromatic/Percy/Lost Pixel (SaaS cost,
Storybook-centric), stylelint plugins (DDE styles live in TS strings),
Rive/Lottie/Figma Motion (CSP + admission bar).

Scope when accepted: one new `visual` job in `.github/workflows/dde-studio.yml`
running after the compile job; screenshots attached as VerificationRun/Evidence
artifact refs (playbook §5.3 row 3); baselines never updated by CI itself.

## Consequences

- `node_modules` footprint grows materially (browser binaries); CI cache key
  must include the Playwright version.
- Flaky-diff risk managed via `maxDiffPixels` budgets per element class;
  threshold tuning documented in the playbook §4.4 sources.
- Rejection keeps screenshot/a11y gates at their current Phase-A state:
  fingerprints + manual review remain the enforcement, and the playbook's
  Phase-B rows stay marked deferred.
