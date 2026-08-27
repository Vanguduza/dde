# DDE-062 chapter gate -- DR drills, backup/restore, WORM ⟨Ch.17.5⟩

**Mission:** §18.3 S7 / `DDE-062` -- DR drills, backup/restore
verification, WORM enforcement ⟨Ch.17.5⟩. **Not** DDE-063 load,
DDE-064 readiness, or Frontend Studio.

**Status:** CLOSED on `dde-062-dr-worm`.

**CI / local proofs (2026-08-27):**

- `just check` green -- ruff / mypy (**372** files) / **1156 passed, 3
  skipped** (unit+contract+recovery) / `generate_contracts --check` /
  contract pytest **185 passed** / design-lints baseline / dde-studio
  `tsc --noEmit`
- `tests/unit/test_object_store_worm.py`: evidence-linked delete refused;
  scope still enforced; `engine.dr` does not import Redis
- `tests/unit/test_dr_drill_postgres.py`: `purge_evidence` refuses;
  `ControlPlaneDrill.run` verifies chain, holds WORM, restores into a
  scratch database, and exercises `emergency_revoke`

## Prior landings this chain

| Mission | SHA | Verdict |
|---|---|---|
| DDE-061 | `3cf71b0` | PASS-WITH-EDR (EDR-0002, 0003, 0005, 0027) |

## What this mission wires

- `WormRetentionService.purge_evidence`: the sole public purge path for
  `evidence` rows. It loads the row (or unknown id) and always raises
  `POLICY_DENIED` with `control=worm_retention`. There is no SQL DELETE.
- `ArtifactObjectStore.delete`: every object-key delete must pass
  `verify_key`; `evidence_linked=True` is refused. No R2 adapter exists,
  so this is application-layer WORM, not Cloudflare object-lock.
- `IsolatedRestoreService.restore_tenant`: creates a throwaway database,
  Alembic-upgrades it to head, copies organization/tenant/project plus
  `audit_events` via `AuditRepository.insert`, then
  `AuditService.verify_chain` on the copy. That is a real restore into
  an isolated environment. It is **not** WAL/PITR replay.
- `ControlPlaneDrill.run`: production caller of `verify_chain`,
  `purge_evidence`, `ArtifactObjectStore.delete`, `restore_tenant`, and
  `CredentialBrokerService.emergency_revoke`. Durable
  `drill.started` / `drill.completed` audit events are appended.
- `IsolatedRestoreService.inspect_pitr`: read-only `SHOW archive_mode` /
  `SHOW wal_level`. Local and CI Postgres are `archive_mode=off`.

## Rule disposition

| Rule | Production call site |
|---|---|
| Restore drill (real restore into an isolated environment) | `IsolatedRestoreService.restore_tenant` at `ControlPlaneDrill.run` |
| Evidence / artifacts WORM (no delete in retention window) | `WormRetentionService.purge_evidence`; `ArtifactObjectStore.delete` |
| Evidence integrity: content hash + signature at write | Already at `VerificationRunnerService` evidence writer (DDE-012). Not re-owned. |
| `audit_events` hash-chained + periodic chain verification | Writer: `AuditService.append`. Production drill caller: `ControlPlaneDrill.run` → `verify_chain` |
| Secrets emergency revoke in the same drill cadence | `CredentialBrokerService.emergency_revoke` at `ControlPlaneDrill.run` |
| Redis is disposable | `engine.dr` has no Redis import; drill does not read Redis |
| Ch.3.2 tenant_id/project_id + RLS | No new tables this mission |
| RPO ≤ 5 min (PITR / WAL archiving) | **Deferred EDR-0033.** `inspect_pitr` reads settings; it does not enable archiving. |
| RTO ≤ 2 hours | Target, not a code control. Named by the restore drill existing; not timed here. |
| R2 object-lock / versioning | **Deferred EDR-0033.** No R2 adapter. Application-layer refuse is named above. |
| Event archives (detached partitions → object storage) | **Deferred EDR-0033.** |
| Secrets rotation *schedule* (vs emergency revoke) | **Deferred EDR-0033.** Revoke is named; cadence/rotation is not. |

## Adversarial self-check

- A new idempotency key cannot delete evidence: `purge_evidence` has no
  DELETE path.
- `ArtifactObjectStore.delete(..., evidence_linked=False)` is not WORM;
  only evidence-linked keys are held. Callers must pass the flag; a
  future R2 adapter must still route through this mediator.
- Restore copies organization/tenant/project/`audit_events` only — not
  the full control plane. That is the isolated-restore drill for the
  hash chain, not a claim of complete pg_dump coverage.
- `emergency_revoke` with zero live handles still goes through the
  production broker mutation (returns empty). Rotation schedule is not
  claimed.
- Claimed call sites are mutations (`purge_evidence` refuse,
  `restore_tenant` CREATE/INSERT/DROP, `emergency_revoke`, audit
  appends) or the live `verify_chain` / `delete` gates on the drill.

## Deferred (proposed / still-open EDRs)

| ID | Item |
|---|---|
| **EDR-0002 / 0003 / 0005 / 0027** | Unchanged |
| **EDR-0033** | PostgreSQL PITR/WAL archiving (RPO ≤ 5 min); R2 object-lock + versioning; event-partition archives to object storage; credential rotation schedule. Application-layer WORM + logical isolated restore + `emergency_revoke` in the drill are in this mission. |
| DDE-063+ | Load, readiness -- frozen |

## Verdict

**PASS-WITH-EDR.** EDR-0002, EDR-0003, EDR-0005, EDR-0027 remain open.
**EDR-0033** records PITR/R2/archives/rotation-schedule. Auto-proceed to
DDE-063 authorized under the standing order.

**Landed:** 2026-08-27 on `dde-062-dr-worm` (FF to `main`).
