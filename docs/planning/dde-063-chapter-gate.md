# DDE-063 chapter gate -- load and capacity testing ⟨Ch.16.5⟩

**Mission:** §18.3 S7 / `DDE-063` -- load and capacity testing. **Charter:**
S7 exit "all Chapter 16.5 SLOs met". **Not** DDE-064 readiness or
Frontend Studio.

**Status:** OPEN pending `just check`. Named call sites below.

## Prior landings this chain

| Mission | SHA | Verdict |
|---|---|---|
| DDE-062 | `e6c1fba` | PASS-WITH-EDR (EDR-0002, 0003, 0005, 0027, 0033) |

## What this mission wires

- `GatewaySloProbe.measure_mission_read` hits production
  `GET /v1/missions/{id}` (`engine.gateway.api.read_mission` →
  `GatewayCommandService.read_mission`). That is the Chapter 16.5 API
  p95 read-latency call site. `GET /healthz` remains a liveness probe
  (`engine.gateway.app.healthz`) and is **not** claimed as the domain
  read SLO.
- `GatewaySloProbe.measure_command_acceptance` hits production
  `POST /v1/commands` (`accept_command` → `GatewayCommandService.accept`)
  with `mission.create`. Planner/router are not on that path
  ("excluding heavy planning").
- `GatewaySloProbe.measure_reconnect` times production
  `POST /v1/sessions/{id}/resume` (`resume_session` →
  `GatewaySessionService.resume`) with a one-hour cursor (bounded gap).
  WS/SSE sequence replay is **not** timed (EDR-0027).
- `GatewaySloProbe.measure_mission_read_concurrent` is an in-process
  burst (8) against the same mission-read site. It must complete
  without hanging (max < 10 s). It is **not** the p95 SLO — coverage
  and pool contention on one Windows process have been seen above
  500 ms. Capacity claim is "sequential p95 holds on one ASGI app +
  local Postgres at N=40". **Not** a published QPS ceiling or
  multi-instance soak.
- `engine.load.inventory.SLO_FIXTURE_SUITES` names the certified
  fixture files for the six non-latency Ch.16.5 rows. DDE-063 does not
  re-implement them.

## Ch.16.5 MUST/shall at production call sites

| Metric | Target | Production call site |
|---|---|---|
| Mission state reconstruction | 100% of certified recovery fixtures | Named: `tests/recovery/test_missions_recovery.py`, `tests/recovery/test_checkpoints_recovery.py`. Not re-implemented. |
| Duplicate side-effect prevention | 100% of idempotency suite | Named: `tests/recovery/test_external_effects_recovery.py`, `tests/unit/test_external_effects_postgres.py`. Production mutation remains `GatewayCommandService.accept` / effect journal (prior missions). |
| Lease fail-closed | 100% of security fixtures | Named: `tests/unit/test_capability_lease_enforcement.py`, `tests/unit/test_capability_leases_postgres.py`. |
| Worker replacement without mission loss | 100% of certified scenarios | Named: `tests/unit/test_chaos_suite.py` (DDE-061). |
| Checkpoint recovery | ≥ 99% of deterministic fixtures | Named: `tests/recovery/test_checkpoints_recovery.py`, `tests/unit/test_checkpoints_postgres.py`. Suites are binary pass/fail in `just check`; this mission does **not** compute a 99% ratio. |
| Post-integration verification | 100% of merge fixtures | Named: `tests/unit/test_integration_queue_postgres.py`, `tests/recovery/test_diff_gates_recovery.py`. |
| API p95 read latency | < 500 ms | `GET /v1/missions/{id}` at `read_mission`. Probe: `GatewaySloProbe.measure_mission_read` (sequential p95). Concurrent burst is hang-bound only. `GET /healthz` is additional liveness, not the domain SLO. |
| Command acceptance p95 | < 1 s excluding heavy planning | `POST /v1/commands` at `GatewayCommandService.accept` (`mission.create`). Probe: `GatewaySloProbe.measure_command_acceptance`. |
| Gateway reconnect recovery | < 10 s for a bounded gap | `POST /v1/sessions/{id}/resume` at `GatewaySessionService.resume`. Probe: `GatewaySloProbe.measure_reconnect`. Correctness fixtures remain `test_android_gateway_reconnect.py` / `test_gateway_sessions.py`. |

## Adversarial self-check

- A new idempotency key still goes through `GatewayCommandService.accept`
  (ledger `begin` then dispatch). The p95 probe uses a fresh key per
  sample; replay is not substituted for first-acceptance.
- A new `WorkerRun` does not skip named chaos/recovery suites; those
  suites already run in `just check`.
- `/healthz` cannot stand in for API read: the capacity statement and
  `MEASURED_ROUTES` require `GET /v1/missions/{id}`.
- Reconnect timing is HTTP resume, not WS/SSE replay. Claiming stream
  reconnect would be an overclaim (EDR-0027).
- Claimed latency call sites are the live FastAPI routes. The probe is
  the load caller, not a second source of mission truth.

## Deferred (proposed / still-open EDRs)

| ID | Item |
|---|---|
| **EDR-0002 / 0003 / 0005 / 0027 / 0033** | Unchanged. EDR-0027 still covers WS/SSE list/stream reconnect. |
| Frontend Studio CWV / generated-output LCP/CLS/INP | Out of charter. Gap-closure named DDE-063 as a possible owner; Ch.16.5 has no CWV row. Frozen with DDE-064+. |
| DDE-064 | Production readiness / removal-test -- frozen until this gate closes |

**No new EDR-0034.** Auto-proceed to DDE-064 is authorized only after
`just check` green and this verdict is PASS or PASS-WITH-EDR.

## Verdict

**OPEN** -- call sites named; `just check` not yet recorded on this
revision (`9e9afce`).
