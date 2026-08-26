# DDE-058 chapter gate — routing learner / frozen fit / canary / rollback

**Mission:** §18.3 S7 / `DDE-058` — routing learner, shadow evaluation,
calibration, canary, rollback ⟨Ch.6.9⟩. **Charter:** Chapter 6.9 mode
machine (`deterministic → shadow_learning → canary → promoted_historical`),
activation gates including refusal when unmet, offline full-information
fit before any partial-information path, frozen-exploitation-first
rollout, limited canary, ROLLBACK to last certified policy. **Not**
DDE-059 adaptive context, DDE-060 Flight Lab / Ch.6.10 full eval suite,
or DDE-065 Frontend Studio.

**CI / local proofs (2026-08-27):**

- `just check` green — ruff / mypy (**364** files) / **1122 passed, 2
  skipped** (unit+contract+recovery) / `generate_contracts --check` /
  contract pytest / design-lints baseline / dde-studio `tsc --noEmit`
- `tests/unit/test_routing_learner.py` + `test_learning_activation_gates.py`:
  **13 passed**
- `tests/unit/test_learning_canary_postgres.py`: **4 passed** (fit, rollback,
  canary `RouterService.route()`, online-update refusal against live Postgres)
- `tests/unit/test_learning_activation_postgres.py`: empty-population
  advance still refused

## What landed

- `schemas/objects/learned_routing_policy.json` +
  `routing_activation_state.json` (migration `0022`, tenant/project + RLS).
- Pure learner: `engine.learning.learner.fit_frozen_policy` — empirical
  full-information fit over train-partition observations; holdout
  Brier/ECE; learner vs best-constant vs incumbent on the same window;
  class-mix total-variation drift.
- Production mutations (`engine.learning.activation_service`):
  - `fit_frozen_policy` — TRAIN / OFFLINE EVALUATE writer of
    `learned_routing_policies` (`continued_update=false`, table CHECK).
    Cold-start (empty train partition) is POLICY_DENIED.
  - `attempt_advance` — sole forward `routing.mode` writer. Reads
    **durable** current mode (a caller cannot skip). Refuses unmet
    Chapter 6.9 gates. Safety regressions are counted from eligible
    rows whose `routing_policy_version` is a frozen artifact and whose
    attribution is `route_attributable` FAILED.
  - `rollback` — from any mode to last certified (declared deterministic
    table when none); frozen artifact is not deleted.
  - `attempt_online_update` — partial-information path; always
    POLICY_DENIED (`no_online_updater`).
- Production reader: `RouterService.route()` applies the frozen mapping
  among hard-gate survivors on the canary slice and in
  `promoted_historical`. Shadow mode still selects deterministically
  and records `SHADOW_LEARNED:<profile>`. An eliminated learned profile
  is never resurrected (`LEARNED_PROFILE_ELIMINATED`).

## Rule disposition

| Rule | Production call site |
|---|---|
| Mode progression one step; skip refused | `can_transition` inside `LearningActivationService.attempt_advance`; durable current mode |
| ROLLBACK to last certified, never untested | `LearningActivationService.rollback` → `routing_activation_state` |
| Activation gates; refuse when unmet (S7) | `attempt_advance` → `evaluate_activation_gates`; empty population still refused |
| No promote from training metrics | `attempt_advance` requires a persisted frozen fit plus holdout calibration for learned modes |
| Offline full-information fit before partial-information | `fit_frozen_policy`; `attempt_online_update` structurally refused |
| Frozen exploitation first | table CHECK `continued_update = false`; `route()` reason `FROZEN_EXPLOITATION` |
| Beats best constant (promotion) | `evaluate_activation_gates` mandatory for `canary` / `promoted_historical` |
| Limited canary among survivors only | `RouterService.route()` + `in_canary_slice`; `evaluate(..., learned_mapping=)` |
| Previous policy remains deployable | `rollback` does not delete `learned_routing_policies` |
| Calibration on holdout | frozen fit Brier/ECE, not `RouteDecision.predicted_success` (still null, EDR-0005) |
| Safety regressions = 0 | counted at `attempt_advance` from frozen-policy `route_attributable` FAILED rows |
| Fallback robustness | demonstrated at fit time: `evaluate` with learned profiles health-evicted never selects an evicted profile |
| Ch.3.2 tenant_id/project_id + RLS | both new tables `tenant_scoped` / `project_scoped` |
| Idempotency | policy UNIQUE `(tenant_id, project_id, policy_hash)` and `learning_run_id`; activation UNIQUE `(tenant_id, project_id)` upsert |

## Deferred (proposed / still-open EDRs)

| ID | Item |
|---|---|
| **EDR-0005** | `RouteDecision.predicted_success` remains null. Activation calibration is the frozen fit's holdout Brier/ECE over empirical rates, not a live prediction model. |
| **EDR-0027** | Sequence/WS/SSE gap replay (Core) — unchanged, not this charter |
| Ch.6.10 full evaluation suite (simulator validity, pick-flip, exploration containment) | **DDE-060**, not deferred as a new EDR |
| Partial-information / continued-update updater | Unreachable by design until an explicit switch plus its own canary evidence; no updater is implemented. Not an EDR — refusal is the control. |

## Adversarial self-check

- A new `WorkerRun` still routes through `RouterService.route()`, which
  reads activation state; there is no second route writer.
- A new idempotency key on `fit_frozen_policy` with the same training
  hash returns the existing artifact (`ON CONFLICT DO NOTHING`).
- `attempt_advance(..., current_mode="canary")` cannot skip shadow:
  durable mode is authoritative.
- `attempt_online_update` cannot be unblocked by a new `learning_run_id`.
- Claimed call sites are mutations (`fit_frozen_policy`, `attempt_advance`,
  `rollback`) or the live route writer (`RouterService.route()`), not
  helpers.

## Verdict

**PASS-WITH-EDR** — Chapter 6.9 mode machine, frozen full-information fit,
limited canary, and rollback are wired at production call sites. Live
`RouteDecision` prediction vectors remain EDR-0005. Auto-proceed to
DDE-059 authorized under the standing order.

**Landed:** 2026-08-27 on `dde-058-routing-learner` (FF to `main`).
