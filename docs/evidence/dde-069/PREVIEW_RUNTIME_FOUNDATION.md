# DDE-069 — Preview Runtime + Inspector Foundation Evidence

**State:** IMPLEMENTED_BACKEND_BOUND, not workbench-complete.
**Date:** 2026-09-05

## What this tranche proves

- `FrontendPreviewSession` is persisted with explicit BUILDING, LOADING, LIVE, STALE, RUNTIME_ERROR, RENDER_ERROR, UNAVAILABLE and STOPPED states.
- `PrototypeHtmlPreviewAdapter` reads and mutates actual isolated candidate-workspace code; it does not use screenshots, detached fixtures or hard-coded demo apps.
- Preview instrumentation maps stable source anchors to `pxg_key`; DOM reordering does not change project identity.
- Browser `LIVE` is not trusted directly: PreviewService checks the browser content hash, candidate workspace/state, candidate effective PXG revision, accepted-base staleness and current source bytes before recording LIVE.
- Unsupported non-prototype source is typed unavailable instead of being replaced by fake HTML.
- `InspectorDescriptor` derives values, legal tokens, source mapping, operation-sensitive lock behaviour, staleness, preview invalidation and required verification from project state.
- Mutation planning now refuses a candidate whose accepted PXG base advanced, and apply-time authority rechecks accepted PXG revision inside the write transaction.
- Preview start/state/stop commands are registered on the normal Gateway command authority. Frontend snapshot, preview-document and Inspector reads are mission/tenant/project scoped Gateway GET reads.

## Verification run in this tranche

- generated-contract drift: PASS
- Ruff on changed preview/Inspector/Gateway/mutation files: PASS
- mypy on changed preview/Inspector/Gateway/read paths: PASS
- focused contracts/unit tests, including binding validator: 49 PASS before ledger projection update; binding validator subsequently 14 PASS
- stable PXG identity reflow test: PASS
- unsupported TSX source fail-closed test: PASS

## Explicit limits

This does **not** prove a complete live canvas. The React workbench still renders its pre-existing unavailable Design surface, `selectedKey` is not yet wired, Inspector controls are not yet interactive, and the VS Code host does not yet service the generic React bridge read/command envelopes. The initial runtime adapter covers admitted `prototypes/screens/*.html`; React/Vite, Expo and other product targets still require real adapters. DDE-068 evidence is invalidated by governed mutations through candidate state, but automatic visual re-verification scheduling after a rerender is not yet implemented. PostgreSQL-backed runtime execution could not be freshly exercised on this host because the required database/Redis runtime is unavailable; that is recorded as UNAVAILABLE, not PASS or FAIL.

Pixel-reference conformance remains blocked by AD-039. `/design` remains blocked on a certified DesignProvider transport and is not proxied through `capability.claude_code_invoke`.
