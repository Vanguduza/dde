# DDE-069 Screen Audit & Experience Completeness evidence

**Date:** 2026-09-05
**Authority:** `docs/truth/SCREEN_AUDIT_ENGINE.md`
**Migration:** `0033_screen_audit_core.py` after AI Conversation Fabric `0032`

## Implemented vertical slice

The Screen Audit capability is now an executable derived-intelligence layer over the existing Frontend Contract, PXG, Coverage thinness rules, accepted verification evidence and candidate promotion lineage. It does not create a second screen graph, requirement store, coverage percentage or visual critic.

Five schema-first persistent objects are implemented: `ScreenAuditRun`, `ScreenAuditScreenRecord`, `ScreenAuditFinding`, `ScreenAuditEvidence`, and `ScreenAuditResolution`. Full and incremental runs pin the exact PXG/Contract inputs, preserve `UNKNOWN`, record evidence references, stale only affected dependencies, and include screen ancestry when a child PXG key changes.

DDE-068 authority remains intact. `silhouette` and `visual_critique` are mandatory screen bindings; candidate-origin verification evidence counts for accepted-project audit only after that exact candidate is promoted. An unpromoted candidate PASS never turns accepted product state into PASS.

Accepted project changes trigger audit refresh at the accepted-state boundary: screen registration, Frontend Contract publication, PXG change and candidate promotion. Candidate-local edits do not stale accepted-project audit evidence. Prior audit evidence is staled before derived recomputation; if recomputation fails after an accepted write, the command reports audit refresh `ERRORED/UNKNOWN` rather than falsely claiming the accepted write rolled back.

## Product surfaces

Mission-scoped reads expose summary, matrix, screen, finding and evidence projections. Mutations `frontend.audit.run`, `frontend.audit.recompute_affected` and `frontend.audit.accept_exception` remain under `mission.control` and CommandLedger authority. Accepted exceptions require a durable decision reference and create `ScreenAuditResolution`; a model/chat assertion cannot resolve a finding.

The React workbench consumes one current Screen Audit matrix across Coverage, QA, Architecture and Inspector. Universal DDE Chat answers deterministic audit/QA queries without requiring an active candidate and resolves `@finding:<UUID>` through current Screen Audit evidence; stale findings fail closed.

## Dogfood reconciliation

`engine/studio/audit/dogfood.py` reconciles Screen Audit assessments with the independent 99-control golden binding ledger without changing either source. The current v2 ledger is structurally valid and remains **5 VERIFIED / 23 BOUND / 5 TYPED_UNAVAILABLE / 66 UNBOUND**. With no production PostgreSQL audit run available on this host, no self-audit control state is fabricated. Synthetic disagreement tests prove PASS/non-PASS disagreement becomes an explicit `AUDIT_LEDGER_DISAGREEMENT` finding.

## Runnable evidence on this host

- Screen Audit pure rules: 11/11 pass.
- Gateway/audit/chat focused tranche: 28/28 pass.
- Dogfood reconciler: 2/2 pass.
- React Playwright workbench: 34/34 pass, including Screen Matrix, QA findings, Architecture overlays and Inspector Audit state.
- Contract generation and binding-matrix drift: pass.
- Ruff/mypy/React TypeScript/extension TypeScript/diff hygiene: pass on changed paths.
- PostgreSQL lifecycle specification: `tests/unit/test_screen_audit_postgres.py` is present and type-clean.

## Infrastructure-unavailable evidence

This host does not expose `DDE_DATABASE_URL` or `DDE_REDIS_URL`, so the PostgreSQL-backed Screen Audit lifecycle test and production VS Code → Gateway → PostgreSQL audit E2E are **UNAVAILABLE**, not passed or failed. The code/test remains executable in an environment providing the required services.

AD-039 also remains unchanged: exact pixel-reference conformance cannot be claimed until the approved 1672×941 golden artifact is supplied.
