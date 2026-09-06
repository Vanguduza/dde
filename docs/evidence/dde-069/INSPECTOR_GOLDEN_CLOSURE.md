# DDE-069 Inspector golden control-loop closure

**Date:** 2026-09-06

This evidence records the implemented Inspector tranche against the canonical
Frontend Studio §8.9 contract. It does not claim packaged VS Code-host browser
E2E where the browser suite uses the explicit TestHostBridge, and it does not
claim AD-039 pixel-reference conformance.

## Implemented surface

The Inspector now exposes the six canonical tabs: Layout, Style, Behaviour,
Responsive, Lock and Source/code. Selection remains keyed by stable `pxg_key`
and the descriptor continues to expose candidate state, source mapping,
staleness and required verification evidence.

Layout is semantic rather than CSS-literal authoring. `layout_type`, `direction`,
`gap` and `padding` are descriptor-backed controls. Gap/padding write spacing
token identities; arbitrary `24px`/`64px` writes are rejected at the server
boundary. Layout type/direction are constrained enum values.
The authoritative token sheet currently resolves `space6` to `24px` and
`space8` to `40px`. The approved visual shows a 64px Padding example, but no
64px spacing token exists in repository truth. The implementation therefore
renders `space8 · 40px` rather than fabricating a token or bypassing DDE-067
style safety. That discrepancy remains explicit until token authority changes.

Behaviour exposes governed duration/easing tokens and deliberately does not
invent the golden screen's illustrative `Fade In` preset. The row is therefore
reconciled as BOUND rather than falsely VERIFIED until a validated animation
reference contract exists.

Responsive exposes Desktop 1440, Tablet 1024 and Mobile 390 controls. Switching
a breakpoint issues `frontend.preview.start` with the exact viewport and creates
a new code-backed preview. It does not currently rewrite a responsive rule set;
that broader contract remains BOUND.

Lock is backed by real effective lock inventory and lifecycle commands. A Style
Lock becomes visible in Inspector, changes Explorer lock count, changes Current
to Current (Locked), disables affected property writes, and can be released.
Source/code exposes the mapped source path, host `revealFile`, durable
provenance and the Screen Audit accessibility dimension. Accessibility remains
honest: UNKNOWN renders `Not evaluated`; PASS may render the AA/no-current-issue
badge only when that state came from Screen Audit evidence.

## Verification

- `tests/unit/test_frontend_inspector.py`: descriptor semantics, computed token
  values, source mapping, staleness and effective lock projection.
- `tests/unit/test_frontend_canvas.py` and
  `tests/unit/test_frontend_mutation_engine.py`: semantic layout/token writes and
  fail-closed rejection of raw spacing/invalid layout values.
- `tests/unit/test_frontend_studio_domain_postgres.py`: real PostgreSQL Explorer
  lock inventory including create/release lifecycle.
- Real PostgreSQL + Redis Inspector/mutation/domain focused suite: **61 passed**.
- `interfaces/dde-studio/ui/visual/inspector-golden.spec.ts`: **7 passed**.
- Current full Frontend Studio Playwright suite after the `/design` tranche:
  **58 passed**.

Browser proof uses the explicit TestHostBridge while persistence proof runs
against real PostgreSQL/Redis. Rows whose closure rule requires one packaged
VS Code-host → Gateway → PostgreSQL browser path therefore remain BOUND at E2E.