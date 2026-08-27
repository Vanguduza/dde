# DDE-061 chapter gate -- chaos and worker-replacement suites

**Mission:** §18.3 S7 / `DDE-061` -- chaos and worker-replacement
suites. **Charter:** S7 exit "chaos suite green"; Ch.19.1 Environment
"replacement mid-run"; Ch.7.3 `FAILED → REPAIRING | REPLACEMENT` with
no run scheduled into `DRAINING` or `FAILED`; S3 residue "a killed
worker is replaced without mission loss" as a Flight Lab / chaos
attempt, not a new recovery matrix. **Not** DDE-062 DR/WORM, DDE-063
load, DDE-064 readiness, or Frontend Studio.

**Status:** STARTED on `dde-061-chaos-worker-replacement` from
`origin/main` @ `0aadb47` (DDE-060). Implementation not landed.

## Prior landings this chain

| Mission | SHA | Verdict |
|---|---|---|
| DDE-060 | `0aadb47` | PASS-WITH-EDR (EDR-0002, 0003, 0005, 0027) |

## Ch.19 / Ch.7 MUST/shall to name at production call sites (or defer)

| Rule | Current disposition (audit, not closed) |
|---|---|
| No run scheduled into DRAINING or FAILED | `ExecutionEnvironmentService.assert_schedulable` -- confirm chaos suite *attempts* scheduling into those states |
| FAILED → REPAIRING \| REPLACEMENT | State table exists; REPLACEMENT is a terminal marker. Need a production mutation that *replaces* (new environment + rebind in-flight run) rather than only permitting the enum |
| Replacement mid-run (Ch.19.1 Environment) | **Not landed as Flight Lab / chaos.** DDE-060 deferred this to DDE-061 |
| Killed worker replaced without mission loss | Checkpoints exist (DDE-023); chaos must *attempt* a kill + replacement at WorkerManager / environment call sites |
| Chaos suite green (S7 exit) | `evals/chaos/` is empty `.gitkeep`. This mission must add executable chaos scenarios that run in `just check` or a named recipe -- do not overclaim unit tests as the chaos suite |
| Core crash / worker crash / environment crash (Ch.19.1 Recovery) | Recovery tests exist; chaos is process/environment *fault injection* at production sites, not a second copy of `tests/recovery` |

## Deferred unless this mission closes them

| ID | Item |
|---|---|
| **EDR-0002 / 0003 / 0005 / 0027** | Unchanged; chaos must not treat them as closed |
| DDE-062+ | DR/WORM, load, readiness -- frozen |

## Verdict

**OPEN.** Next: inventory existing environment/worker failure paths,
add chaos scenarios that attempt replacement mid-run and a killed-worker
replacement at real call sites, close only what this mission can name.
Do not overclaim `assert_schedulable` unit tests as the chaos suite.
