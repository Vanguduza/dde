# DDE-061 chapter gate -- chaos and worker-replacement suites

**Mission:** §18.3 S7 / `DDE-061` -- chaos and worker-replacement
suites. **Charter:** S7 exit "chaos suite green"; Ch.19.1 Environment
"replacement mid-run"; Ch.7.3 `FAILED → REPAIRING | REPLACEMENT` with
no run scheduled into `DRAINING` or `FAILED`; S3 residue "a killed
worker is replaced without mission loss" as a Flight Lab / chaos
attempt, not a new recovery matrix. **Not** DDE-062 DR/WORM, DDE-063
load, DDE-064 readiness, or Frontend Studio.

**Status:** CLOSED on `dde-061-chaos-worker-replacement`.

**CI / local proofs (2026-08-27):**

- `just check` green -- ruff / mypy (**368** files) / **1151 passed, 3
  skipped** (unit+contract+recovery) / `generate_contracts --check` /
  contract pytest / design-lints baseline / dde-studio `tsc --noEmit`
- `tests/unit/test_chaos_inventory.py`: four chaos scenarios named;
  named files exist; `evals/chaos/catalog.md` present
- `tests/unit/test_chaos_suite.py`: drain/failed `invoke_run` refused;
  `replace` + `resume_run` mid-attempt; killed worker replaced on the
  same attempt; new engine after kill still `resume_run`s

## Prior landings this chain

| Mission | SHA | Verdict |
|---|---|---|
| DDE-060 | `0aadb47` | PASS-WITH-EDR (EDR-0002, 0003, 0005, 0027) |

## What this mission wires

- `ExecutionEnvironmentService.replace`: production mutation
  `any → FAILED → REPLACEMENT` plus `acquire()` of a substitute.
- `WorkerManagerService.resume_run` binds the new WorkerRun to the
  workspace environment; a different environment than the hashed plan
  is legal only when the original is already `REPLACEMENT`.
- Recoverable `WORKER_FAILURE` / `ENVIRONMENT_FAILURE` leave the
  TaskAttempt `IN_PROGRESS` (`stamp_checkpoint`); `invoke_run` refuses
  while that attempt is open.
- Chaos catalog `evals/chaos/catalog.md` plus executable
  `tests/unit/test_chaos_suite.py` (inside `just check` and `just chaos`).

## Rule disposition

| Rule | Production call site |
|---|---|
| No run scheduled into DRAINING, FAILED, or REPLACEMENT | `ExecutionEnvironmentService.assert_schedulable` at `WorkerManagerService.invoke_run`, `resume_run` (`_bound_environment_for_resume`), `_drive_lifecycle` after RUNNING, and `ExecutionPlanService.plan`. Chaos **attempts** `invoke_run` into DRAINING and FAILED. The RUNNING re-check is named; chaos does not claim a concurrent fail-during-`start()` race (scripted adapter is synchronous). |
| FAILED → REPLACEMENT (actual replace, not enum-only) | `ExecutionEnvironmentService.replace` |
| Replacement mid-run (Ch.19.1 Environment) | `replace` then `ExecutionPlanService.provision_workspace(execution_environment_id=…)` then `WorkerManagerService.resume_run` on the same TaskAttempt |
| Killed worker replaced without mission loss | Surviving attempt + `resume_run` sequence N+1. `invoke_run` cannot mint a second attempt while IN_PROGRESS. |
| Chaos suite green (S7 exit) | `evals/chaos/catalog.md` + `tests/unit/test_chaos_suite.py` |
| Core / worker / environment crash as chaos | Worker and environment crash at the call sites above. Core **OS process-crash** remains EDR-0027; this mission injects a new engine after a killed worker, not a second copy of `tests/recovery`. |
| Ch.3.2 tenant_id/project_id + RLS | No new tables this mission |

## Adversarial self-check

- A new `WorkerRun` via `invoke_run` cannot bypass an open IN_PROGRESS
  attempt (must `resume_run`).
- A new idempotency key cannot schedule into DRAINING / FAILED /
  REPLACEMENT (`assert_schedulable` on invoke, resume, and mid-RUNNING).
- Resume onto a different environment is refused unless the plan's
  original environment is already `REPLACEMENT`.
- Repeated WORKER_FAILURE (two failed **runs**) fails the attempt and
  `assert_clear_to_retry` counts failed runs so a new attempt cannot
  skip the reroute threshold.
- Claimed call sites are mutations (`replace`, `resume_run`,
  `provision_workspace`, `stamp_checkpoint`) or the live schedulable
  gate on `invoke_run`.

## Deferred (proposed / still-open EDRs)

| ID | Item |
|---|---|
| **EDR-0002 / 0003 / 0005 / 0027** | Unchanged. Full Core OS process-crash stays EDR-0027. |
| **EDR-0011** | Container/network kill at stop -- unchanged |
| DDE-062+ | DR/WORM, load, readiness -- frozen |

**No new EDR-0033.** Auto-proceed to DDE-062 authorized under the
standing order.

## Verdict

**PASS-WITH-EDR.** EDR-0002, EDR-0003, EDR-0005, EDR-0027 remain open.

**Landed:** 2026-08-27 on `dde-061-chaos-worker-replacement` (FF to `main`).
