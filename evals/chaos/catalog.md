# DDE-061 chaos suite

Executable scenarios live in `tests/unit/test_chaos_suite.py` and run
inside `just check` (and `just chaos`). This catalog names the production
mutation call sites. These are not a second copy of `tests/recovery`.

| Scenario | Fault injected | Production call sites | Expected |
|---|---|---|---|
| Drain / failed not schedulable | Environment `DRAINING` then `FAILED` | `WorkerManagerService.invoke_run` → `ExecutionEnvironmentService.assert_schedulable` | No WorkerRun minted |
| Replacement mid-run | Live environment replaced while the attempt is open | `ExecutionEnvironmentService.replace`, `ExecutionPlanService.provision_workspace`, `WorkerManagerService.resume_run` | Same TaskAttempt, new environment_id, mission not lost |
| Killed worker replaced | Non-zero worker exit (`WORKER_COMMAND_FAILED`) | `WorkerManagerService.invoke_run` then `resume_run` | Attempt stays `IN_PROGRESS`; sequence 2 completes |
| Core restart then replace | New engine after killed worker | `WorkerManagerService.resume_run` on a fresh process/engine | Same attempt identity; no second attempt |

Deferred (not this suite): full OS process-crash of Core (EDR-0027),
container/network kill at stop (EDR-0011), DR/WORM (DDE-062).
