# DDE-069 — source workspace onboarding and verification requests

**Base:** `7a334effbb1010c6db222f4e66a20d2ded3ec42b`

## What this tranche closes

- Frontend Studio reads real project workspaces through `WorkspaceService`.
- Preview-source admission is fail-closed: only READY workspaces with a durable `current_revision` are eligible, and candidate-preview worktrees are excluded.
- Zero sources is `EMPTY`; exactly one is `UNIQUE` and may auto-select; multiple sources are `AMBIGUOUS` and require explicit workbench selection.
- A fresh candidate sends `source_workspace_id` only after that admission/selection step and then enters the same isolated PreviewService materialization path as existing candidates.
- A hash-confirmed LIVE candidate preview creates one durable `FrontendVerificationRequest`, unique by preview session.
- The request is derived from the candidate effective PXG and references the existing screen `AcceptanceOracle` version, task provenance and bound verification kinds. Missing bindings/oracle persist `BLOCKED`; nothing is guessed.
- Governed candidate mutations supersede outstanding PENDING/BLOCKED verification requests and invalidate the old preview before rerender.

## Authority boundary

`FrontendVerificationRequest` is scheduling/observability state, not evidence. Frontend Studio does not write a synthetic `VerificationRun`, does not claim PASS/FAIL, and does not fabricate a WorkerRun. Promotion continues to consume only real `VerificationRun` rows from `engine.verification`.

The remaining dependency is a candidate-compatible execution seam inside/reusing DDE-068 so requests can become real runs/evidence without duplicating the verifier.

## Evidence

- `tests/unit/test_frontend_source_workspace_inventory.py` proves EMPTY/UNIQUE/AMBIGUOUS admission semantics.
- `tests/unit/test_frontend_verification_requests.py` proves bound DDE-068 kinds become PENDING and missing screen/oracle metadata becomes BLOCKED.
- `interfaces/dde-studio/ui/visual/live-loop.spec.ts` proves an ambiguous fresh candidate cannot start until a READY source is selected, the selected workspace id crosses the command boundary, LIVE still requires browser hash attestation, and edit/rerender returns to a PENDING verification request.
- Generated contract/SQL drift remains checked by `scripts.generate_contracts --check`.

## Honest residuals

- This host has no PostgreSQL/Redis runtime, so persistence/Gateway production E2E remains BOUND rather than VERIFIED.
- PENDING requests are not yet executed into DDE-068 `VerificationRun`/`Evidence` rows.
- General React/Vite/Expo preview adapters, M8 source intelligence, React Chat, Screen Audit and AD-039 pixel-reference conformance remain open.
