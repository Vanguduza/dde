# Production VEKL Unit Knowledge Graph v2 — 2026-09-10

## Status

`IMPLEMENTED / CI_CERTIFIED` — the revised Unit Knowledge Graph, deterministic GraphRAG
and Target Project Truth Evolution architecture is implemented and service/browser certified
as an additive Blueprint §26A / AD-048 extension. Existing DDE authority boundaries and
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

- v2 architecture/runtime focused tests: **22/22 passed**;
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

## CI certification

Core CI run `34497981504` on isolation-certification commit `e2bc027c556115a968a38895a32151b4a6c3b415` is **PASS**. It proves Linux lint/typecheck/contract/design gates, PostgreSQL migration/schema provisioning, accepted Project Truth provisioning, **1576 passed / 7 skipped** Linux tests, **755 passed / 6 skipped / 563 deselected** Windows pure-unit tests, **223/223** contract tests, **8/8** PostgreSQL integration tests, and generated-drift cleanliness. The migration gate executed `upgrade head -> downgrade base -> upgrade head` and explicitly traversed `0038 -> 0039` and `0039 -> 0038`. The eighth PostgreSQL integration executes through the dedicated `dde_rls_probe` role (`NOSUPERUSER NOBYPASSRLS`) and proves that a Unit Map visible in its owning project is invisible when the same tenant is bound to a different project.

DDE Studio CI run `34491084691` on `1c1b49a6c35998d75e6f1c44e3d278f88aecf9c0` is **PASS**. It proves design gates, cross-platform client compile/tests, the Knowledge workbench structural suite at **80/80 passed** on the canonical `1672x941` viewport, and the separate visual/golden/accessibility job. Subsequent commits through `e2bc027` changed backend VEKL determinism/persistence/isolation contracts only, not the certified Studio UI.

The Oracle-admin shell still lacks local PostgreSQL/Redis and the Chromium `libatk-1.0.so.0` host library, but those host limitations are now superseded by the successful service-capable and browser-capable CI evidence above. Broader DDE-082 executable-adapter/authoring and DDE-083 adversarial/release work remain separately owned and are not silently claimed complete.
## Harness-boundary correction

VEKL v2 is harness-neutral but is delivered only through the certified DDE Rev 3 worker-harness set. **DeepSeek Harness is first-class under DDE-074**, alongside Codex Native and Claude Code / Claude Agent SDK. Hermes remains the separately governed research/coordination fabric. Development Prime / Prime Agent is explicitly non-canonical for DDE and is not an implementation dependency.
## Cross-project repository firewall

DDE repository capability now permanently refuses both `Vanguduza/dial-new` and superseded `Vanguduza/dial` before a Git connection can bind, across HTTPS, SSH and Git transports. The DDE checkout has only `Vanguduza/dde` configured as a remote, and the temporary DIAL audit clones used during diagnosis were deleted. The focused repository-firewall regression passes locally. DIAL repository reconciliation is outside DDE authority and must be performed only in a separately scoped DIAL workflow.
