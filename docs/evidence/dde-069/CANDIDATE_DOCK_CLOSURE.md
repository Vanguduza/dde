# DDE-069 Candidate Dock Functional Closure Evidence

**Date:** 2026-09-05

This packet closes the candidate-review interactions that are independently available without a certified `/design` provider or production PostgreSQL browser path. It does not convert external/provider gaps into PASS.

## Implemented

- accepted-current revision card backed by the durable PXG revision;
- explicit unknown lock state when effective lock inventory is not projected;
- exact code-backed `PreviewDocument` miniature per candidate rather than a fake screenshot;
- real `APPLIED` mutation count from candidate mutation history;
- evidence-backed score/classification with clickable dimensions/evidence/hard-failure explanation;
- hard-failure visibility that prevents a reassuring numeric score from masking a block;
- existing-candidate **Try Live** action that opens its exact code-backed preview;
- compare mode requiring two independently available `LIVE` preview documents;
- explicit governed Promote action routed through `frontend.candidate.promote`;
- promotion refreshes accepted revision/audit state; failures stay visible;
- Universal DDE Chat was moved above the permanent dock so it cannot intercept dock actions.

## Evidence

- TypeScript check: PASS.
- Candidate-dock Playwright: **5/5 passed**.
- Full Frontend Studio Playwright: **46/46 passed**.
- Extension Node suite: **77/77 passed**.
- Binding/chat focused Python: **21/21 passed**.
- Binding matrix generation/integrity: PASS.
- `git diff --check`: PASS.

## Binding reconciliation

The 99-control ledger now derives **5 VERIFIED / 39 BOUND / 6 TYPED_UNAVAILABLE / 49 UNBOUND**.

The packet intentionally does **not** call `CA-07` fully bound: canonical `frontend.design.try_live` means converting a governed `DesignArtifact` into an isolated candidate. The dock's existing-candidate Try Live action is useful and real, but it is not a substitute for the blocked certified `/design` artifact path.

`CA-06` also remains BOUND rather than VERIFIED because the accepted-current card cannot honestly say `Current (Locked)` until effective lock inventory is projected.

Production React → Gateway → PostgreSQL E2E remains unavailable until the database-backed host path is exercised.
