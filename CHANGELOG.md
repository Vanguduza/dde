# Changelog

All notable integrated DDE changes are recorded here. Project Truth and accepted EDRs remain authoritative; this file is a human-readable change history, not a substitute for them.

The repository follows an `Unreleased` section until a release/version boundary is ratified. Branch-only work is never recorded as completed.

## Unreleased

### Changed

- Established `main` as the only persistent integration branch, with temporary PR branches, automatic post-merge deletion, strict Project Truth/Linux/Windows merge gates, branch-orphan auditing, changelog enforcement, and an append-only fixed-bug ledger.

## 2026-09-10 — Governance and VEKL v2 baseline

### Added

- Integrated Production VEKL Unit Knowledge Graph / GraphRAG v2 with deterministic Unit lineage/revisions, graph-bounded resource selection, foresight, Truth Challenges, immutable resolution traces, execution bindings, invalidation, Knowledge workbench topology/evidence views, and explicit PostgreSQL RLS isolation proof.
- Added protected-main Project Truth verification that treats `main` as the sole integration lineage while retaining Project Truth/accepted EDRs as architectural authority.

### Fixed

- Repaired DDE Studio Windows test execution and Playwright server startup without weakening tests.
- Aligned VEKL activation-manifest SQLAlchemy metadata with the `knowledge_context` migration/schema contract.
- Normalized UUID values inside VEKL JSONB persistence while preserving native PostgreSQL UUID columns.
- Corrected VEKL Project Truth invalidation reason codes and GraphRAG source-provenance fixture semantics.
- Removed mutable readiness/Unit-map hashes from GraphRAG node and edge identity so successful resolution cannot invalidate its own trace.
- Reworked Project Truth automation so protected `main` is verified read-only instead of attempting forbidden CI self-pushes.

> Earlier history remains available through Git and governed evidence. This changelog baseline intentionally does not reconstruct pre-baseline releases that were never previously maintained as a canonical changelog.
