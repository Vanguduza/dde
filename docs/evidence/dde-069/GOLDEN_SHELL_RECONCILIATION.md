# DDE-069 Golden Shell Reconciliation

Date: 2026-09-07
Mission: DDE-069 Frontend Studio V2
Status: evidence-backed partial closure; DDE-069 remains `IN_PROGRESS`.

## Scope

This tranche reconciles five golden rows without inventing new authority:
`EX-16` Style Locks, `EX-17` Section Locks, `EX-18` Component Locks,
`EX-19` Behaviour Locks, and `ST-01` Breadcrumb.

The lock domain already existed. `LockService.inventory()` is the authoritative
per-kind active-lock read and the React Explorer already renders nested
`ExplorerGroup` children. The missing production link was that
`FrontendReadService.snapshot()` discarded the per-kind inventory and projected
only the total Locks count.

The snapshot now carries the four canonical child counts while preserving the
total active-lock count and all existing mutation/lock authority boundaries.
## Verification

- Fresh PostgreSQL `alembic upgrade head` followed by
  `tests/unit/test_frontend_studio_domain_postgres.py`: **12 passed**.
- `interfaces/dde-studio/ui/visual/inspector-golden.spec.ts`: **7 passed**.
- The browser proves the four nested lock rows render, and a real governed
  Style lock changes the Style Locks count `0 -> 1 -> 0` across create/release.
- `ST-01` now derives project and screen labels from current projections and
  the selected node label from the Inspector descriptor. The live-loop browser
  suite proves `LogiFlow Marketplace / Checkout / Checkout hero` rather than
  the previous hard-coded `Project` plus raw PXG key.

## Evidence boundary

For these rows UI and structural visual behavior are verified. Their production
read/command seams exist, but this host has no installed VS Code/Cursor binary,
so a single packaged webview -> real Gateway -> PostgreSQL browser execution is
not recorded. `WIRED`/`E2E` therefore remain `BOUND` where applicable; these
rows must not be promoted to final `VERIFIED` from TestHostBridge evidence.
## Explorer QA adapter

`EX-20` and `EX-21` now derive their visible inventory from the existing
mission-scoped `frontend.audit.matrix` read: the QA group and QA Issues child
show the authoritative unresolved-finding count from the current Screen Audit
summary. No duplicate QA persistence layer was added.

`EX-22` remains intentionally typed-unavailable when current audited screens
carry `ACCESSIBILITY=UNKNOWN|UNASSESSED|NOT_EVALUATED`. In that state the
Explorer shows `—` with an explicit reason instead of a fabricated zero or AA
claim. When all current screens have an assessed accessibility dimension, the
same adapter counts unresolved ACCESSIBILITY findings.

Playwright regression across live-loop, Inspector and Source Intelligence is
**28 passed**. The QA group is also collapsible while retaining the existing
recursive Explorer hierarchy.
## Sync provenance controls

`TB-03` now renders `StudioSyncSnapshot.durable_revision_at` next to the sync
chip and keeps the empty state as `Saved —`. `ST-06` renders the DDE build
version together with the current durable PXG revision.

The Gateway now supplies `FrontendReadService.build_version` from installed DDE
package metadata instead of leaving the production snapshot permanently null.
If package metadata is unavailable the field still fails closed to null.

A fresh PostgreSQL Gateway E2E run passed **2 tests** and proves both a non-null
durable revision timestamp and `sync.build_version == version("dde")`.
The live-loop browser suite passed **15 tests** including the visible saved/build
projection.
## Full-gate confirmation

After the shell/ledger reconciliation and dogfood repair, the current repository-defined gate was rerun from a fresh PostgreSQL database through migration `0035` and completed green.

Evidence from the uninterrupted run:
- Ruff check: PASS.
- Ruff format: 1005 files already formatted.
- mypy: 551 source files, zero issues.
- unit/contract/recovery suite: 1489 passed, 6 skipped.
- generated-contract/design-token/binding drift checks: PASS; contract rerun 220/220.
- design-lints baseline: accepted with the pre-existing 70 DD206 violations still explicit.
- extension tests: 77/77.
- desktop and React TypeScript checks: PASS.
- Vite production build: PASS.
- full Playwright structural/functional visual suite: 61/61.

The desktop install still reports 15 npm audit findings (1 moderate, 13 high, 1 critical); this remains open hardening debt and is not hidden by the green functional gate. The current binding projection is 6 VERIFIED / 61 BOUND / 7 TYPED_UNAVAILABLE / 25 UNBOUND.
## Viewport and manager-chair reconciliation

`CT-01` had a contract error in the old ledger: `frontend.preview.set_state` is browser attestation only and accepts LIVE or RUNTIME_ERROR. Viewport selection must not use that command. The canonical Canvas and Inspector viewport controls now share one handler that starts a new code-backed `frontend.preview.start` session for the selected viewport, then follows the ordinary browser hash/LIVE/verification path.

Playwright proves selecting Mobile 390 sends `frontend.preview.start` with viewport `390`, renders a 390 px preview frame and returns to LIVE. The focused live-loop suite is 16/16 green.

`OR-02` was stale evidence rather than missing UI. The real Gateway snapshot carries the Manager Chair role to the React Orchestrator card. A fresh PostgreSQL Gateway E2E now asserts serving identity remains null with confidence `UNATTESTED`; no configured/desired model is laundered into a serving claim.

Focused matrix/dogfood verification and the fresh Gateway/PostgreSQL E2E are green. Current ledger: 6 VERIFIED / 62 BOUND / 8 TYPED_UNAVAILABLE / 23 UNBOUND.
## Canvas interaction and lock-chip tranche

`CT-02`, `CT-03`, `CT-05`, `CT-07` and `CT-08` now use real editor presentation state rather than static controls. Select and Pan alter iframe interaction; Pan moves the overflow surface; Grid is a local canvas overlay; Fit computes bounded zoom; Zoom is bounded to 50–200%; Fullscreen uses the host Fullscreen API and reports `HOST_UNSUPPORTED`/error explicitly. None of these presentation controls fabricates candidate/PXG mutations or reuses preview lifecycle attestation as an editor-state command.

Playwright proves these controls through the code-backed live canvas, including a zero-Gateway-command invariant for Grid/Fit/Zoom and deterministic unsupported-host Fullscreen evidence. The focused live-loop suite reached **21/21 green** for this tranche.

`CV-06` Section Lock and `CV-07` Style Lock chips now render on the selected canvas element from the existing authoritative Inspector descriptor after ordinary governed lock creation. No duplicate lock authority was added. The live-loop suite reached **22/22 green** with both chips. These two rows remain `BOUND`, not final `VERIFIED`, because the combined packaged editor-host → real Gateway → PostgreSQL browser execution remains unavailable on this host.

Current 99-control ledger: **11 VERIFIED / 64 BOUND / 8 TYPED_UNAVAILABLE / 16 UNBOUND**.
