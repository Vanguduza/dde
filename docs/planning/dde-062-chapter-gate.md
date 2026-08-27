# DDE-062 chapter gate -- DR drills, backup/restore, WORM ⟨Ch.17.5⟩

**Mission:** §18.3 S7 / `DDE-062` -- DR drills, backup/restore
verification, WORM enforcement ⟨Ch.17.5⟩. **Not** DDE-063 load,
DDE-064 readiness, or Frontend Studio.

**Status:** OPEN on `dde-062-dr-worm` from `origin/main` @ `3cf71b0`
(DDE-061). Isolated restore + WORM + chain verification wired;
PITR/R2/archives named as EDR-0033.

## Prior landings this chain

| Mission | SHA | Verdict |
|---|---|---|
| DDE-061 | `3cf71b0` | PASS-WITH-EDR (EDR-0002, 0003, 0005, 0027) |

## Ch.17.5 MUST/shall to name at production call sites (or defer)

| Rule | Current disposition |
|---|---|
| Evidence / artifacts WORM (object-lock, no delete in retention window) | **This slice:** `ArtifactObjectStore.delete` refuses `evidence_linked=True`; `WormRetentionService.purge_evidence` refuses before any SQL DELETE. No R2 object-lock yet (no R2 adapter). |
| Evidence integrity: content hash + signature at write | Already at `VerificationRunnerService` evidence writer (DDE-012). Not re-owned here. |
| `audit_events` hash-chained + periodic chain verification | Writer: `AuditService.append`. **This slice:** `ControlPlaneDrill.run` is a production caller of `AuditService.verify_chain`. |
| Restore drill (real restore into isolated environment) | **Not yet.** Drill currently verifies chain + WORM hold against the live DB. Isolated `pg_dump`/restore is still open. |
| RPO ≤ 5 min (PITR / WAL archiving) | Deferred -- managed Postgres setting; no production mutation in this repo yet. Next free EDR if we cannot name a call site. |
| RTO ≤ 2 hours | Target, not a code control. Named by the drill cadence once restore exists. |
| Event archives to object storage | Deferred |
| Secrets rotation + emergency revoke in drill cadence | Deferred (broker revoke exists; not this drill) |
| Redis is disposable | Already true by design (Ch.17.6). Drill must not treat Redis as a backup source. |

## Deferred unless this mission closes them

| ID | Item |
|---|---|
| **EDR-0002 / 0003 / 0005 / 0027** | Unchanged |
| DDE-063+ | Load, readiness -- frozen |

## Verdict

**OPEN.** Next: isolated restore drill at a real backup/restore call site,
or defer PITR/R2 object-lock with the next free EDR (**0033**, unused).
Do not overclaim `verify_chain` tests as the restore drill.
