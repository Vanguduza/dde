# DDE-069 — React Frontend Chat Control Plane Evidence

**State:** `IMPLEMENTED_BOUND`
**Date:** 2026-09-05
**Authority:** `docs/truth/FRONTEND_STUDIO_REV3.md` §§8.6, 14, 30

## What landed

Frontend Chat is now a permanent React workbench surface backed by the existing governed DDE-069 conversation domain. It is not a local-only chat box and it does not create a second design session.

Production read/write chain:

```text
FrontendChatComposer
→ DdeHostBridge
→ central FrontendStudioWorkbenchPanel
→ StudioGatewayService / GatewayApiClient
→ mission-scoped Core frontend read + /v1/commands
→ FrontendChatService
```

The mission-scoped `frontend.chat.thread` read restores the most recently active durable `FrontendConversation` and its ordered persisted turns after workbench reload.
## One governed mutation path

`engine/studio/mutations/governed.py` centralizes the post-mutation consequences shared by Inspector, Chat and explicit revert. `MutationExecutor` remains the sole mutation-log writer.

A successful Chat edit or undo therefore performs the same governed tail as Inspector:

```text
MutationRequest / compensating mutation
→ candidate state changes
→ old code-backed preview becomes STALE
→ outstanding DDE-068 verification request becomes SUPERSEDED
→ workbench starts a new code-backed preview
→ browser re-attests the new content hash
→ a new verification request executes through DDE-068
```

A deterministic instruction such as `set the spacing to space4` never invokes a design provider. Ambiguous instructions are refused instead of guessed.

`UNDO_REVERT` resolves the latest applied candidate mutation and creates the governed compensating edit. Chat cannot revert accepted design in place.
## Context lineage and honesty

Conversation identity persists selected stable `pxg_key` values, current screen, active candidate and viewport. Explicit null context updates clear stale candidate/screen identity rather than silently retaining it.

Before routing each turn, Core resolves and persists an authority-owned context snapshot containing:

- PXG revision;
- active Frontend Contract version;
- coverage state/staleness/availability;
- active lock identities/kinds/scopes;
- active candidate/workspace identity;
- latest preview identity/state;
- current verification request state;
- currently attached VerificationRun identity/status.

These facts are read from Core services, not accepted from the React client as truth. The turn stores target/reference resolution plus this snapshot in `resolved_context`, preserving why an instruction was actionable at that point in time.
## Deterministic read/action routing

The Chat backend now answers supported read-only questions from real projections:

- coverage queries → `FrontendReadService.snapshot()`;
- QA queries → current candidate verification request/run/check/evidence;
- selected-element inspection → `InspectorService.describe()`.

Unsupported or authority-sensitive commands remain typed refusals:

- source search → `CAPABILITY_UNAVAILABLE` until M8 Source Intelligence exists;
- lock change → `EXPLICIT_CONTROL_REQUIRED` rather than inventing creator/release authority;
- promotion → `EXPLICIT_CONTROL_REQUIRED` rather than bypassing the promotion gate;
- unsupported/ambiguous query → typed refusal, never fabricated assistant prose.

`/design` is routed inside the same conversation/DesignSession. With no certified design transport, it remains an honest typed provider refusal; broad `capability.claude_code_invoke` is not used as fallback.
## React/browser evidence

The permanent composer exposes the persisted thread, send control, selection/screen/candidate/viewport chips and an explicit context-settings surface. Removing the selection chip changes Chat scope without clearing the Canvas selection.

Playwright proves:

1. the composer is permanently visible and reflects live scope;
2. deterministic Chat edit → governed mutation → rerender → LIVE → fresh DDE-068 PASSED evidence;
3. deterministic edit does not dispatch `frontend.design.request`;
4. removing Chat selection context leaves Canvas selection intact and an unscoped edit is refused;
5. coverage/QA/inspect questions return current project evidence;
6. `/design` stays in the same Chat and surfaces certified-provider unavailability;
7. Chat undo creates a compensating mutation, rerenders and reverifies;
8. the pre-existing Inspector mutation loop remains green alongside Chat.

The full visual/browser suite is 28 passed.
## Verification gates

Available gates for this tranche:

- generated-contract drift: PASS;
- Ruff: PASS;
- mypy: PASS;
- focused Frontend/Chat/Gateway Python tests: 28 PASS;
- binding-ledger tests: 14 PASS;
- React TypeScript check: PASS;
- Playwright: 28 PASS;
- VS Code extension Node tests: 75 PASS;
- binding-matrix render drift: PASS;
- `git diff --check`: PASS before truth finalization; rerun before commit.

Production VS Code → Gateway → PostgreSQL E2E remains **UNAVAILABLE** on this host because `DDE_DATABASE_URL` / `DDE_REDIS_URL` and a database runtime are absent. Chat E2E ledger layers therefore remain `BOUND`, not `VERIFIED`.
## Residuals / next dependency

This tranche does not make DDE-069 complete.

- Screen Audit-specific Chat queries and repair commands depend on the mandatory Screen Audit domain and are next.
- M8 source search/provenance remains unavailable rather than fabricated.
- No certified Claude `/design` transport exists.
- General React/Vite/Expo preview adapters, exact viewport-state semantics, resize handles and the full canonical Inspector tab hierarchy remain incomplete.
- AD-039 still blocks pixel-reference conformance because the owner-approved 1672×941 image is absent.

Binding-ledger effect: CH-01 through CH-08 now have verified React UI/wiring/structural visual evidence but production E2E remains BOUND. The 99-control totals are therefore **5 VERIFIED / 23 BOUND / 5 TYPED_UNAVAILABLE / 66 UNBOUND**.