# Production VEKL runtime foundation — 2026-09-08

## Status

`IMPLEMENTED_PARTIAL` — common cross-mission runtime foundation implemented under
Blueprint §26A / AD-048 without renumbering DDE-070…DDE-083 and without adding a second
truth, mission, context, permission, evidence or memory authority.

This evidence supersedes only the **implementation-status** statement in
`VEKL_V1_PACK_INTEGRATION.md` that runtime contracts were still deferred. The v1 pack
remains the reviewed architecture input and its original hash/evidence is preserved.

## Production boundaries implemented

- `projects.kind` distinguishes `TARGET_APPLICATION` and `DDE_CONTROL_PLANE`;
  application-manufacturing VEKL fails closed with `VEKL_SCOPE_VIOLATION` outside a
  target application.
- Schema-generated persistent contracts cover `VEKLResource`, `StackFingerprint`,
  `TaskSignature`, `VEKLActivationManifest`, `VEKLManifestInvalidation`,
  `VEKLResourceOutcome`, Instruction IR, Hook IR and BoundedLoopDefinition. Migration
  `0038` creates the persistent VEKL tables and tenant/project RLS and is Alembic head.
- Source qualification reuses current Source Intelligence records/artifact admissions and
  the existing EDR-0015 donor allowlist. No new host, open-web worker browse path or VEKL
  source-catalog egress was admitted.
- Production `vekl.activation.prepare` requires a scoped DDE `workspace_id`; it no longer
  accepts caller/model stack facts. `engine.vekl.stack` mechanically reads a bounded set
  of manifest/lock/runtime files, skips dependency/build trees, records exact versions
  only when observed as exact, and binds each fact source to SHA-256 evidence.
- TaskSignature binds the observed stack plus Requirement/Feature refs. Eligibility rejects
  before ranking on scope, lifecycle/revocation, source admission, source/reuse class,
  license/provenance, exact versions, stack constraints, Project Truth conflicts, prompt
  injection, executable bundle ambiguity, sandbox/capability/verifier availability,
  filesystem/network/secret overreach, budget, stale mandatory security evidence and
  offline exact-pin requirements.
- Activation manifests bind Project Truth, policy, StackFingerprint, task/signature,
  attempt/WorkerRun when available and exact resource revision/content hashes. Failover
  returns the same still-valid manifest. Policy/truth/stack/resource/source/revocation
  drift writes an append-only invalidation and refuses silent reselection.
- `VEKLKnowledgeCompiler` emits bounded provenance-bearing context with stack facts,
  selected excerpts/reasons, freshness/caveats, tool contracts and verifier obligations.
  `VEKLService.compile_worker_context` injects its capsule into the existing
  `ContextService` as a hash-bound/budget-reserved `ContextExtension`; the ordinary
  `ContextPackage` remains the one worker-context authority.
- `capability.vekl.qualify`, `.resolve` and `.compile_context` are narrow no-egress
  capability seeds with explicit risk/side-effect metadata.
- `LeaseBoundComponentRuntime` and `LeaseBoundHookRuntime` re-check executable component
  and TaskSignature scope, require an active CapabilityLease, write ExternalEffect
  PREPARED/SENT before non-read invocation, confirm verified results and mark uncertain
  non-idempotent/irreversible effects UNKNOWN rather than retrying.
- Bounded loops enforce max cycles/steps, pre-step reservations for every declared measured
  budget, required checkpoint writers, verifier termination and declared rollback on
  exhaustion. Instruction IR is hash-bound to Project Truth/policy/provenance.
- `VEKLResourceOutcome` remains distinct from routing `ExperienceRecord` and conversation
  `ExecutionExperienceRecord`; outcome writes require verifier and evidence refs. Hermes
  has candidate-only authority.
- Gateway exposes governed register/transition/activation/context/outcome commands plus a
  mission-scoped real VEKL projection. The projection never fabricates active resources.

## Verification executed on this host

- focused VEKL runtime + contract: **21 passed**;
- pure unit suite: **698 passed, 5 skipped, 558 database-backed deselected**;
- contract suite: **223 passed**;
- extension/shared tests: **77/77 passed**;
- Frontend Studio full Playwright: **79/79 passed**, including the new canonical
  1672×941 proof that Universal DDE Chat does not overlap/intercept Source Intelligence
  `source-blend-apply`, plus responsive Inspector-clearance proofs;
- React/Vite production build: PASS;
- desktop TypeScript check: PASS;
- strict repository MyPy: PASS (**579 source files**);
- Ruff on changed VEKL/context/Gateway/test surfaces: PASS;
- generated contract, design-token and binding-matrix drift checks: PASS;
- Alembic reports `0038` as the single head; `0038` independently compiles through
  Alembic's PostgreSQL offline Operations context to **205 upgrade / 16 downgrade SQL
  lines**, including all six VEKL tables, RLS and policies. Repository-wide
  `alembic upgrade head --sql` remains unavailable because historical migration `0002`
  executes a live `SELECT` even in offline mode; that historical behavior was not changed.

## Environment-only gates still open here

This shell exposes no PostgreSQL server/client runtime, Redis server, Docker or `just`.
Therefore these checks are **UNAVAILABLE on this host**, not PASS and not product FAIL:

1. `tests/unit/test_vekl_postgres.py` (2 integration tests): persistent manifest failover,
   revocation/historical audit, source/scope/cross-project fail-closed behavior;
2. a live PostgreSQL reversible migration cycle exercising `0038` upgrade/downgrade;
3. any deployment-specific Redis/worker/harness execution involving VEKL resources.

CI or a service-capable DDE host must run those before a completion/certification claim.

## Mission-state honesty

This foundation does **not** mark DDE-075/076/077/080/081/082/083 complete. It lands the
shared primitives they now consume. Remaining work includes the full DDE-081 operator UX,
harness-specific qualified executable adapter fleet and authoring surfaces in DDE-082,
Hermes/eval-shadow-canary learning promotion, and DDE-083 release-environment adversarial,
supply-chain, poisoning, cross-project and migration certification. No new external source
egress is implied by VEKL source/catalog seeds.
