# DDE-069 M8 Source Intelligence — Checkpoint Evidence

**Date:** 2026-09-05

This document records a partial M8 checkpoint. It is evidence of implemented local/fake-transport behavior, not final DDE-069 or production-source certification.

## Implemented domain

- migration `0034_source_intelligence.py`;
- persisted DesignSource, search run, artifact, admission, provenance, template, candidate score and target-blend preference records;
- common `DesignSourceAdapter` contract;
- project-native component adapter;
- repository-backed DDE component/template library;
- Donor Lab adapter preserving existing donor licence/taint evidence;
- 21st MCP transport requiring exact certified source capability and no direct-network fallback;
- Design System Compiler admission with hard failures that cannot be averaged away;
- sandbox adaptation/validation before external reuse;
- provenance recording and carry-forward into accepted PXG after promotion;
- evidence-backed CandidateScorecard;
- actual provenance attribution separated from target source-blend preference.

## Integrated surfaces

Gateway owns explicit source initialize/search/inspect/fetch/sandbox/validate/admit/provenance/template/score/target-blend commands plus source/artifact/provenance/score/blend reads. Universal DDE Chat uses governed source search. Frontend Studio Source mode displays provider health/degradation and the explicit source lifecycle; candidate cards/source blend/Inspector consume evidence-backed score/provenance projections. Screen Audit consumes persisted provenance. Candidate promotion includes a source-provenance readiness gate.

## Focused checkpoint gates

- `scripts/generate_contracts.py --check`: PASS
- `scripts/render_binding_matrix.py --check`: PASS
- Ruff on changed M8/Chat/Gateway/Audit paths: PASS
- mypy on changed M8/Chat/Gateway/Audit paths: PASS
- focused Python: **35 passed**
- React TypeScript: PASS
- targeted M8/Screen Audit/candidate/Inspector Playwright: **14 passed**
- full workbench Playwright regression: **41 passed**
- extension TypeScript: PASS
- extension Node suite: **77 passed**
- real VSIX package: **89 files / 1.57 MB**
- `git diff --check`: PASS

## Explicitly not proven at this checkpoint

- production PostgreSQL/Redis M8 lifecycle E2E on this host;
- live certified 21st provider execution;
- final 99-control binding-ledger promotions from the new evidence;
- complete DDE-069 chapter closure;
- AD-039 pixel-reference conformance while the approved golden image is absent;
- certified Claude `/design` transport.

## Cold-start continuation verification — 2026-09-05

The checkpoint was reconstructed from repository state at `0a39299` before new work.
The following results supersede the earlier checkpoint counts only as current local
verification; they do not turn unavailable infrastructure into production evidence.

- generated contracts: PASS;
- generated binding matrix drift/integrity: PASS;
- Ruff over M8/Audit/Chat/Gateway and the new integration specification: PASS;
- mypy over M8/Audit/Chat/Gateway and the new integration specification: PASS;
- focused Python regression: **49 passed**;
- full Frontend Studio Playwright regression: **41 passed**;
- VS Code extension Node suite: **77 passed**;
- real VSIX packaging: **89 files / 1.57 MB**;
- `git diff --check`: PASS.

### PostgreSQL lifecycle specification

`tests/unit/test_source_intelligence_postgres.py` now specifies the real persisted M8
sequence: accepted PXG/audit baseline → source initialization → persisted search run →
artifact inspect/fetch → content-addressed storage → sandbox adaptation → current-byte
compiler admission → candidate provenance → evidence-backed UNSCORED behavior when
required dimensions are absent → source promotion readiness → governed promotion →
accepted-PXG provenance carry-forward → audit invalidation/re-evaluation.

The test is collected as an integration test. `DDE_DATABASE_URL` is unset on this host,
so execution is **UNAVAILABLE**. It is deliberately not reported as PASS or FAIL.

### External provider certification

The host exposes no 21st executable or 21st/MCP credential environment, and persisted
DDE endpoint certification cannot be exercised without PostgreSQL. The 21st adapter
therefore remains fail-closed as `NOT_CONFIGURED` / `NOT_CERTIFIED`; no direct-network
fallback was added. Live 21st E2E remains **BLOCKED_EXTERNAL**.

### 99-control reconciliation

M8-dependent rows were reconciled individually across DOMAIN / READ / COMMAND / STATE /
UI / WIRED / E2E / VISUAL. The derived ledger moved from **5 VERIFIED / 23 BOUND /
5 TYPED_UNAVAILABLE / 66 UNBOUND** to **5 VERIFIED / 34 BOUND / 6 TYPED_UNAVAILABLE /
54 UNBOUND**. No row was promoted to final VERIFIED from backend presence alone.

Remaining source-related non-final states are intentional: production React → Gateway →
PostgreSQL E2E is unavailable, 21st remains externally blocked, and several visible
controls still need their exact golden grammar (for example Explorer source status dots,
clickable score explanation, named-source attribution presentation, target-blend slider
grammar and the Inspector Source/code tab).

## PostgreSQL/Redis closure addendum — 2026-09-05

The earlier `UNAVAILABLE` host state above is superseded for PostgreSQL/Redis by real isolated-runtime evidence.

- PostgreSQL 16.15 and Redis 7.0.15 run in an isolated DDE-only LXD container.
- Fresh Alembic migration reaches `0034 (head)` after repairing regenerated-schema migration idempotency.
- `tests/unit/test_source_intelligence_postgres.py`: **1/1 PASS**.
- Broader DDE-069 PostgreSQL/Redis focused suite: **34/34 PASS**.
- Real Redis stream publication and Gateway Redis readiness: **PASS**.
- Real persistence exposed and closed UUID→JSONB defects in Chat turn context and the generic command-idempotency ledger.

This addendum does not certify 21st, Claude `/design`, or R2. Those remain separately gated by exact external transport/credential evidence. Full detail: `docs/evidence/dde-069/POSTGRES_REDIS_CLOSURE.md`.
