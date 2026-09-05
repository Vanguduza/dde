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
