# DDE-063 chapter gate -- load and capacity testing ⟨Ch.16.5⟩

**Mission:** §18.3 S7 / `DDE-063` -- load and capacity testing. **Charter:**
S7 exit "all Chapter 16.5 SLOs met". **Not** DDE-064 readiness or
Frontend Studio.

**Status:** STARTED on `dde-063-load-capacity` from `origin/main` @
`e6c1fba` (DDE-062). Chapter gate OPEN.

## Prior landings this chain

| Mission | SHA | Verdict |
|---|---|---|
| DDE-062 | `e6c1fba` | PASS-WITH-EDR (EDR-0002, 0003, 0005, 0027, 0033) |

## Ch.16.5 MUST/shall to name at production call sites (or defer)

| Metric | Target | Current disposition |
|---|---|---|
| Mission state reconstruction | 100% of certified recovery fixtures | Named in `engine.load.inventory` (`tests/recovery/test_missions_recovery.py`, checkpoints). Not re-implemented. |
| Duplicate side-effect prevention | 100% of idempotency suite | Named (`test_external_effects_recovery.py`). |
| Lease fail-closed | 100% of security fixtures | Named (`test_capability_lease_enforcement.py`). |
| Worker replacement without mission loss | 100% of certified scenarios | Named (`test_chaos_suite.py`, DDE-061). |
| Checkpoint recovery | ≥ 99% of deterministic fixtures | Named (recovery + unit checkpoint suites). |
| Post-integration verification | 100% of merge fixtures | Named (integration queue + diff-gate recovery). |
| API p95 read latency | < 500 ms | **This slice:** `GatewaySloProbe.measure_healthz` against the production FastAPI `/healthz`. |
| Command acceptance p95 | < 1 s excluding heavy planning | **Not yet.** `/v1/commands` 202 path is not measured. |
| Gateway reconnect recovery | < 10 s for a bounded gap | Named (`test_android_gateway_reconnect.py`). Not a timed load probe yet. |

## Deferred unless this mission closes them

| ID | Item |
|---|---|
| **EDR-0002 / 0003 / 0005 / 0027 / 0033** | Unchanged |
| DDE-064 | Production readiness / removal-test -- frozen |

## Verdict

**OPEN.** Next: command-acceptance p95 at `POST /v1/commands`, reconnect
timing, and a capacity statement that does not overclaim `/healthz` as
the full operational SLO set.
