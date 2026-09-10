# Production VEKL Unit Knowledge Graph v2 — 2026-09-10

## Status

`IMPLEMENTED_PARTIAL / CI_CERTIFICATION_PENDING` — the revised Unit Knowledge Graph,
deterministic GraphRAG and Target Project Truth Evolution architecture is implemented as
an additive Blueprint §26A / AD-048 extension. Existing DDE authority boundaries and
locked DDE-075/076/077/080/081/082/083 ownership are preserved.

## Architecture integrated

- Stable Unit lineage is separated from immutable Unit revision identity. Feature/facet
  lineage survives non-conceptual task churn; revision identity binds TaskGraph, current
  Project Truth/truth slice, StackFingerprint, contract/Product Experience fingerprints,
  route policy, graph/unit schema and projection compiler versions.
- Unit knowledge readiness is separate from Task status and includes explicit
  `EXEMPT_BY_POLICY`; exemptions are never rendered as `READY`.
- PostgreSQL `VEKLKnowledgeNode` / `VEKLKnowledgeEdge` rows are rebuildable typed
  projections referencing existing authoritative objects. They are not a second truth or
  task store.
- Deterministic GraphRAG pins all result-affecting classifier, route, graph, chunking,
  embedding/index, lexical/hybrid rank, hard-eligibility and tie-break identities.
- Resolution order is graph neighbourhood first, existing Source/VEKL hard eligibility
  second, then lexical/semantic ranking and deterministic contextual purpose/role slots.
- `PROJECT_TRUTH_CONFLICT` remains hard-ineligible for implementation while qualifying
  evidence may independently enter the Truth Challenge review path.
- `VEKLResolutionTrace` is immutable. Exact later activation/context admission is written
  as append-only `VEKLExecutionKnowledgeBinding` evidence, not by mutating the trace.
- Truth changes use standing-forbidden `project_truth_change` approval plus existing
  human/project authorization; there is no DIAL- or VEKL-specific canon-authority table.
  Accepted EDR evolution is supersession-only.
- Critical challenges reuse existing `BLOCKED_ON_DECISION` for affected Tasks. Accepted
  truth changes invalidate affected Unit/graph/activation knowledge and force re-resolution.
- UI-bearing Units separate deterministic Frontend Contract/PXG, Screen Audit and
  silhouette gates from qualitative `visual_critique` and bounded human pixel signoff.
- Production Studio Knowledge is enabled from the real mission-scoped VEKL projection and
  renders Unit, graph, challenge and qualified-resource state without fabricated activity.
- The Knowledge workbench now exposes Unit-neighbourhood filtering, Truth/Execution/Contract/Resource/Product overlays, relationship filtering, node authority/provenance inspection, research/invalidation evidence counts and immutable resolution-trace evidence.
- Unit-specific knowledge context is carried through resolution -> `VEKLActivationManifest` -> Context compilation; legacy manifests remain valid with an empty knowledge-context default.
- ChangePacket/contract-impact observations deterministically mark only affected Units stale without creating a second ChangePacket authority.

## Persistence and generated contracts

Migration `0039_vekl_knowledge_graph.py` extends `0038` with project-scoped/RLS tables for
Unit Maps, knowledge nodes/edges, retrieval routes, research findings, conflict
observations, Truth Challenges and finding links, graph invalidations, immutable resolution
traces and append-only execution-knowledge bindings. Stage-1 SQL and generated Pydantic
contracts are produced from the schema-first object definitions; the contract generator
now supports declared indexes including active partial indexes.

## Verification completed locally

- v2 architecture/runtime focused tests: **20/20 passed**;
- pure unit: **753 passed / 6 skipped / 563 integration deselected**;
- contract: **223/223 passed**;
- extension/shared client tests: **77/77 passed**;
- Frontend Studio TypeScript: PASS;
- desktop TypeScript: PASS;
- React/Vite production build: PASS;
- Playwright inventory: **80 tests in 7 files**, including the strengthened Knowledge topology/evidence regression; browser execution remains CI-only on this host;
- tracked Project Truth fallback guard: semantics preserved, Ruff/MyPy clean, historical
  `verify` command returns 0;
- `jsonschema` is now an explicit locked dev dependency instead of an accidental ambient
  dependency;
- repository Ruff + format: PASS across **1,075 files**;
- strict MyPy: PASS across **596 source files**;
- generated contract, design-token and binding-matrix drift checks: PASS;
- `git diff --check` and Project Truth guard verification: PASS;
- design-lint ratchet: PASS with the unchanged historical **70 DD206** baseline findings.

## Environment-deferred proof

This Oracle-admin shell has no PostgreSQL/Redis runtime. The new PostgreSQL integration
module is itself Ruff/format/MyPy/bytecode clean and covers deterministic rebuild,
resolution-to-manifest/context binding, critical challenge blocking, governed TruthService
mutation and Unit invalidation, but execution requires the normal service-capable CI job.

Playwright Chromium is downloaded, but the host lacks `libatk-1.0.so.0`, so the browser
cannot start here. The Knowledge workbench regression remains enabled and must run in the
normal CI browser environment; the host limitation is not recorded as product PASS or FAIL.

Required promotion evidence is therefore: live `0038 -> 0039 -> 0038 -> 0039` migration,
RLS/cross-project isolation, the new PostgreSQL integration module, and the Knowledge
Playwright regression in CI. Broader DDE-082 executable-adapter/authoring and DDE-083
adversarial/release work remain separately owned and are not silently claimed complete.
## Harness-boundary correction

VEKL v2 is harness-neutral but is delivered only through the certified DDE Rev 3 worker-harness set. **DeepSeek Harness is first-class under DDE-074**, alongside Codex Native and Claude Code / Claude Agent SDK. Hermes remains the separately governed research/coordination fabric. Development Prime / Prime Agent is explicitly non-canonical for DDE and is not an implementation dependency.
## Cross-project repository firewall

DDE repository capability now permanently refuses both `Vanguduza/dial-new` and superseded `Vanguduza/dial` before a Git connection can bind, across HTTPS, SSH and Git transports. The DDE checkout has only `Vanguduza/dde` configured as a remote, and the temporary DIAL audit clones used during diagnosis were deleted. The focused repository-firewall regression passes locally. DIAL repository reconciliation is outside DDE authority and must be performed only in a separately scoped DIAL workflow.
