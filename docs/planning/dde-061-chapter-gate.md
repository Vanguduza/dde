# DDE-061 chapter gate -- chaos and worker-replacement suites

**Mission:** §18.3 S7 / `DDE-061` -- chaos and worker-replacement
suites. **Charter:** S7 exit "chaos suite green"; Ch.19.1 Environment
"replacement mid-run"; Ch.7.3 `FAILED → REPAIRING | REPLACEMENT` with
no run scheduled into `DRAINING` or `FAILED`; S3 residue "a killed
worker is replaced without mission loss" as a Flight Lab / chaos
attempt, not a new recovery matrix. **Not** DDE-062 DR/WORM, DDE-063
load, DDE-064 readiness, or Frontend Studio.

**Status:** IMPLEMENTATION on `dde-061-chaos-worker-replacement`.
Chapter-gate review in progress.

## Prior landings this chain

| Mission | SHA | Verdict |
|---|---|---|
| DDE-060 | `0aadb47` | PASS-WITH-EDR (EDR-0002, 0003, 0005, 0027) |

## Ch.19 / Ch.7 MUST/shall at production call sites

| Rule | Production mutation / gate |
|---|---|
| No run scheduled into DRAINING, FAILED, or REPLACEMENT | `ExecutionEnvironmentService.assert_schedulable` called from `WorkerManagerService.invoke_run`, `resume_run` (`_bound_environment_for_resume`), `_drive_lifecycle` after RUNNING, and `ExecutionPlanService.plan`. Chaos **attempts** `invoke_run` into DRAINING and FAILED (`test_chaos_invoke_run_refuses_draining_and_failed_environments`). |
| FAILED → REPLACEMENT (actual replace) | `ExecutionEnvironmentService.replace` — `any → FAILED → REPLACEMENT` plus `acquire()` of a substitute. Retired row is not schedulable. |
| Replacement mid-run (Ch.19.1 Environment) | `replace()` then `ExecutionPlanService.provision_workspace(execution_environment_id=…)` then `WorkerManagerService.resume_run` on the **same** TaskAttempt. New `WorkerRun.environment_id` is the substitute. Chaos: `test_chaos_replacement_mid_run_same_attempt_new_environment`. |
| Killed worker replaced without mission loss | Recoverable `WORKER_FAILURE` leaves the attempt `IN_PROGRESS` (`attempt_survives_run_failure` + `TaskAttemptService.stamp_checkpoint`). `invoke_run` refuses while that attempt is open. `resume_run` mints sequence N+1. Chaos: `test_chaos_killed_worker_replaced_without_mission_loss`. |
| Chaos suite green (S7 exit) | `evals/chaos/catalog.md` + `tests/unit/test_chaos_suite.py` / `test_chaos_inventory.py`. Runs in `just check` (`tests/unit`) and `just chaos`. |
| Core crash / worker crash / environment crash (Ch.19.1 Recovery) | Worker crash + environment crash are chaos scenarios at the call sites above. Core **OS process-crash** remains EDR-0027; this mission injects a new engine after a killed worker (`test_chaos_core_restart_then_resume_replaces_killed_worker`), not a second copy of `tests/recovery`. |

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

## Deferred unless this mission closes them

| ID | Item |
|---|---|
| **EDR-0002 / 0003 / 0005 / 0027** | Unchanged; chaos does not treat them as closed. Full Core OS process-crash stays EDR-0027. |
| DDE-062+ | DR/WORM, load, readiness -- frozen |
| EDR-0011 | Container/network kill at stop -- unchanged |

**No new EDR-0033.**

## Verdict

**OPEN** pending `just check` and independent re-read of named call sites.
