# DDE-060 chapter gate -- Flight Lab full suite / Ch.19

**Mission:** §18.3 S7 / `DDE-060` -- Flight Lab full suite ⟨Ch.19⟩.
**Charter:** Chapter 19.1 contract suites (inventory of schema, state,
negative, recovery fixtures already landed) and Chapter 19.2 golden
mission `MISSION-ERP-000421` including the S7-added scenarios (worker
outage and a policy rollback). The golden mission must remain green on
every merge to `main`. **Not** DDE-061 chaos/worker-replacement,
DDE-062 DR/WORM, DDE-063 load, DDE-064 readiness, or Frontend Studio.

**Status:** CLOSED on `dde-060-flight-lab`.

**CI / local proofs (2026-08-27):**

- `just check` green -- ruff / mypy (**368** files) / **1145 passed, 3
  skipped** (unit+contract+recovery) / `generate_contracts --check` /
  contract pytest / design-lints baseline / dde-studio `tsc --noEmit`
- `tests/unit/test_flight_lab_inventory.py`: every Ch.19.1 suite named;
  named files exist
- `tests/unit/test_flight_lab_force_push.py`: force-push of `main` and
  `mission/*` refused; task refs may still rewind; FF still allowed
- `tests/unit/test_flight_lab_golden_mission.py`: ERP identity spine;
  `RouterService.route` worker outage; `LearningActivationService.rollback`
  then certified `route()`

## Prior landings this chain

| Mission | SHA | Verdict |
|---|---|---|
| DDE-057 | `032439a` | PASS-WITH-EDR (EDR-0032) |
| DDE-058 | `24936b4` | PASS-WITH-EDR (EDR-0005, EDR-0027) |
| DDE-059 | `ea7e603` | PASS-WITH-EDR (EDR-0002, EDR-0003, EDR-0027) |

## What this mission wires

- Inventory: `evals/golden-mission/ch19-inventory.md` +
  `tests/support/flight_lab_inventory.py` (every Ch.19.1 suite named;
  named files must exist; gaps deferred with owner).
- Golden mission identity: slug `MISSION-ERP-000421`, title
  "Implement supplier credit limits", `REQ-AP-019`. Executable spine
  remains the Stage-1 verification-terminated graph (not a fake
  seven-node ERP product).
- S7 worker outage: `RouterService.route` with preferred
  `bulk_implementation` profiles `REVOKED` in production persists
  `NO_ELIGIBLE_WORKER` (not the RSM `evaluate()`-only fixture).
- S7 policy rollback: `LearningActivationService.rollback` then
  `RouterService.route` selects deterministic / non-frozen.
- Force-push: `engine.integration.git.update_ref` refuses non-FF of
  `main` and `mission/*`. Flight Lab attempts both in a throwaway repo.
- Workspace escape / symlink / credential-path: `WorkspaceService.read`
  on the golden-mission workspace.

## Rule disposition

| Rule | Production call site |
|---|---|
| Four tests per contract (schema, state, negative, recovery) | Inventory names existing `tests/contract`, `tests/unit`, `tests/recovery` files per Ch.19.1 suite; this mission does not re-implement closed suites |
| Golden mission end-to-end on every merge to main | `tests/unit/test_flight_lab_golden_mission.py` (`build_golden_mission` → MissionService / RouterService / IntegrationQueueService); already inside `just check` |
| S7 worker outage | `RouterService.route` (`test_s7_worker_outage_persists_via_router_service`) |
| S7 policy rollback | `LearningActivationService.rollback` then `RouterService.route` |
| Workspace escape / symlink / credential-path | `WorkspaceService.read` / `resolve_within_workspace` |
| Force-push of `main` / mission branches refused | `engine.integration.git.update_ref` (used by `IntegrationQueueService.integrate` for `mission/*`) |
| Learning: simulation/ineligible cannot train; promotion without gates refused; rollback | Existing `test_learning_eligibility_rules` / `test_learning_activation_gates`; Flight Lab rollback scenario above |
| Routing: no eligible worker, stale profile, hard-gate, exploration containment, propensity | `RouterService.route`; exploration is structurally unreachable (`selection_source` never `exploration`; propensity 1.0 on deterministic) |
| Ch.3.2 tenant_id/project_id + RLS | No new tables this mission |

## Deferred (proposed / still-open EDRs)

| ID | Item |
|---|---|
| **EDR-0002 / 0003** | Context canary still unreachable via `attempt_advance`; Flight Lab does not treat PARTIAL_PASS as promotion |
| **EDR-0005** | `RouteDecision.predicted_success` remains null |
| **EDR-0027** | Sequence/WS/SSE gap replay -- Core, not this charter |
| Ch.6.10 pick-flip / distribution-shift harness | Not a Ch.19.1 named fixture. Exploration containment is named at `RouterService.route` (structurally off). Remainder is later eval depth, not DDE-061 chaos. No new EDR. |
| DDE-061+ | Chaos, worker-replacement, DR/WORM, load -- frozen |

## Adversarial self-check

- A new `WorkerRun` cannot bypass worker-outage: `RouterService.route`
  is the only `route_decisions` writer; REVOKED certifications still
  persist `NO_ELIGIBLE_WORKER`.
- A new idempotency key cannot skip rollback: `rollback` upserts
  `routing_activation_state`; the next `route()` re-reads it.
- `git.update_ref` on `task/*` may still rewind (rebase). Protected
  refs are only `main` and `mission/*`.
- Claimed call sites are mutations (`rollback`, `update_ref`) or the
  live route writer (`RouterService.route`), not the RSM helper.

## Verdict

**PASS-WITH-EDR.** EDR-0002, EDR-0003, EDR-0005, EDR-0027 remain open.
**No new EDR-0033.** Auto-proceed to DDE-061 authorized under the
standing order.

**Landed:** 2026-08-27 on `dde-060-flight-lab` (FF to `main`).
