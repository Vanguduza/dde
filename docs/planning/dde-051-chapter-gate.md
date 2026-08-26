# DDE-051 chapter gate — multi-tenant authority + isolation suite

**Mission:** §18.3 S6 / `DDE-051` — multi-tenant authority, org/tenant
hierarchy, isolation suite. **Charter:** blueprint `REV_2_0.md` Ch.3.2
(tenancy/scoping), Ch.3.4 (identity), Ch.13.9 (tenancy authority +
four-layer isolation), Ch.14.2 (principals / RBAC+ABAC), Ch.18.2 S6
exit criteria. §18.6 removal tests are Stage-7 / DDE-064 — out of
charter here; S6 requires the multi-tenant isolation suite green.

**CI:** ruff check/format · mypy (352 files) · **1042 passed / 2 skipped**
(unit+contract+recovery, Postgres up) · `generate_contracts --check` ·
design tokens · dde-studio + desktop typecheck/tests — all green on the
landing commit. Secret-gate flake fixed under this mission
(`diff --text` + proposed-blob backstop); assertion not weakened.

## What landed

- Migration `0020_tenancy_authority`: `organizations` with FORCE RLS on
  `dde.organization_id`; `tenants.organization_id NOT NULL` FK;
  `principal_grants.scope_type` / `grant_scope` CHECKs; composite
  scope-binding FKs on artifacts / task_attempts / worker_runs /
  verification_runs (parent-side UNIQUE indexes).
- `TenancyAuthorityService` (`engine/tenancy/authority.py`):
  `resolve_principal_tenant`, `authorize_project_access` (PROJECT /
  TENANT / ORGANIZATION, sibling-tenant via org grant),
  `record_project_grant`.
- Layer helpers: `ArtifactObjectStore.verify_key`
  (`engine/object_store/scope.py`); `GitConnectionScope`
  (`engine/capabilities/git_scope.py`).
- Isolation suite: `tests/unit/test_multi_tenant_isolation.py` (7
  adversarial cases) + `tests/contract/test_tenancy_authority.py` +
  organizations SCOPE_ANCHOR exemption in `test_tenancy_rls.py`.
- Collateral: secret-detection binary-diff backstop so planted-secret
  quarantine cannot pass when git emits a no-`+`-line hunk.

## Rule disposition (adversarial call-site check)

### Ch.13.9 four isolation layers

| Layer | Claimed mechanism | Production mutation / authz site? |
|---|---|---|
| 1. DB RLS + org hierarchy | migration 0020 + probe-role unset-GUC | **YES** — schema FORCE RLS; live fail-closed in `test_unset_guc_yields_no_rows_fail_closed_on_new_tables`. Composite FKs reject cross-scope artifact refs (`test_cross_scope_artifact_reference_rejected_by_fk`). |
| 2. Object-storage prefix mediation | `ArtifactObjectStore.verify_key` | **NO** — helper + isolation-suite only; no `engine/**` artifact write path calls `verify_key`. Composite FK is DB-layer, not byte/key mediation. |
| 3. Project-scoped git credentials | `GitConnectionScope.bind` / `authorize_operation` | **NO** — helper + isolation-suite only; `capability.git_operations` / integration `update-ref` never consult it. In-process `_BINDINGS` is not durable. |
| 4. Telemetry correlation | `RoutingTelemetryService.record_decision_outcome` | **YES** — `VerificationRunnerService.run` (PASSED and FAILED branches) stamps scope from the `Task` / WorkerRun chain in the same transaction as the terminal VerificationRun write. |

### Ch.14.2 / tenancy authority before domain ops

- **Production authz today:** `GatewaySessionService.authorize_project`
  → `PrincipalLookup.grant_covers` only
  (`engine/gateway/sessions/service.py`). Filters by session tenant;
  `project_id IS NULL` covers all projects **within that tenant**.
- **`TenancyAuthorityService.authorize_project_access`:** ORGANIZATION
  grant covers sibling tenants — **unit-tested only**. Zero production
  callers (no gateway/worker/broker import). Docstring “gateway consumes
  its verdicts” is an overclaim; named here as gap, not as wired.
- Adversarial: a new WorkerRun / new idempotency key cannot bypass RLS
  GUCs or composite FKs. It **can** still reach a sibling-tenant project
  through the gateway if only an ORGANIZATION grant exists, because the
  gateway never asks `TenancyAuthorityService`.

### Ch.3.2 / Ch.3.4

- Scoping columns + parent-scope uniques enforced in generated SQL /
  migration 0020 (contract-pinned).
- Identity resolution still runs without tenant GUC on the local `dde`
  superuser (bypass). Dedicated non-bypass identity role is not landed.

## Deferred (proposed EDRs)

| ID | Item | Rationale |
|---|---|---|
| **EDR-0022** | Wire `TenancyAuthorityService.authorize_project_access` (incl. ORGANIZATION / sibling-tenant) at `GatewaySessionService.authorize_project` | Production authz is still `PrincipalLookup.grant_covers`; ORGANIZATION coverage exists only in an unwired service. |
| **EDR-0023** | Call `ArtifactObjectStore.verify_key` (or equivalent) on every artifact byte/key write | Mediator exists and is unit-tested; no production Artifact write path uses it. |
| **EDR-0024** | Call `GitConnectionScope` before git remote ops; durable binding (not process-local `_BINDINGS`) | Layer 3 helper unused by real git mutation paths. |
| **EDR-0025** | Non-bypass DB role for principal/grant identity reads | Docstring-claimed hardening; identity still bypasses RLS as superuser. |

Dashboard “same authorization scope as API reads” (Ch.13.9 last clause)
belongs with DDE-052+ and is not claimed here.

## Verdict

**PASS-WITH-EDR** — in-charter schema/RLS/composite-FK isolation and
telemetry correlation are enforced at named production sites; isolation
suite green; ORGANIZATION gateway wiring and object-store / git-scope
mediation deferred under EDR-0022–EDR-0025 rather than silently
overclaimed. Auto-proceed to DDE-052 authorized under the standing
order.
