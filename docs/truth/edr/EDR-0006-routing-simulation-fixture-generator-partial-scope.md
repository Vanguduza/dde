# EDR-0006 — Chapter 6.4: RSM fixture generator implemented for 3 real scenario classes; 4 of the chapter's named examples deferred

> **Location note.** Per Chapter 3.6, an EDR is a row in the `edrs` table,
> written only by `engine/truth/`. No such row exists yet. Following the
> convention established in `EDR-0001`–`EDR-0005`, this file is a
> **markdown pre-image** of the eventual `edrs` row, filed as the proposal
> itself (not a side effect of implementing DDE-036 — AGENTS.md forbids
> editing `docs/truth/**` as a side effect). **This file is not itself an
> accepted EDR.** `status` is `proposed`; only a human decision can move it
> to `accepted`.

- **slug:** `EDR-0006` (provisional)
- **status:** `proposed`
- **supersedes:** none
- **affected_requirement_slugs:** none filed yet
- **raised during:** implementation of DDE-036 (`docs/blueprint/REV_2_0.md`
  §18.3's roadmap: "`DDE-036` Routing Simulation Model as fixture
  generator ⟨Ch.6.4⟩"), gate-reviewed independently after DDE-035
  (Chapter 6.5 routing telemetry, commit `2b82040`) was found
  PASS-WITH-EDR.

## Context

Chapter 6.4 retains and repositions the Routing Simulation Model: "an
evaluation and fixture-generation subsystem, never a training source for
a production policy and never an authority." Its "RSM is used for"
column names five example adversarial fixture classes: worker outage,
capability gap, modality mismatch, budget exhaustion, environment
incompatibility.

`engine.simulation` implements a real, deterministic fixture generator
(`engine.simulation.scenarios`) driving the real, already-implemented
`engine.routing.rules.evaluate()` pipeline (never
`engine.routing.service.RouterService.route()` — the RSM must never
write an authoritative `RouteDecision`), and a durable writer
(`engine.simulation.service.RoutingSimulationService`) that persists one
`RoutingSimulationRun` row per invocation with a real, reproducible
`seed`, `policy_version` and `model_version`, exactly as the chapter
requires ("simulation seeds, parameter sets and model versions are
persisted for reproducibility").

Three of the chapter's example scenario classes are real today, each
driving an elimination `engine.routing.rules` already implements for
production routing:

1. **`worker_outage`** — every profile `engine.routing.policy` prefers
   for a workload class is marked `REVOKED` in a non-development
   environment; gate 3 (`worker_eligibility`) eliminates all of them for
   real (`NOT_CERTIFIED_FOR_WORKLOAD`).
2. **`generator_independence_violation`** — a `verification` task whose
   `previous_generator_profile_id` equals the sole profile
   `verification`'s policy prefers; Chapter 11.4's real independence
   rule (`GENERATOR_INDEPENDENCE_VIOLATION`) eliminates it.
3. **`hard_gate_approval_required`** — `requires_approval=True` with
   `approval_satisfied=False`; gate 0's real hard-policy elimination
   (`HARD_GATE_APPROVAL_REQUIRED`).

All three genuinely escalate to `HUMAN_DECISION_TASK` through
`evaluate()`'s own real gate logic — verified directly in
`tests/unit/test_simulation_scenarios.py`, never asserted against a
mocked or hand-computed result.

## Decision (proposed)

Four of Chapter 6.4's five named example classes are **not implemented**
by this mission, because Stage 1's real, fixed worker-profile registry
and gate implementations give no real signal to drive them without
fabricating one:

- **`capability_gap` / `environment_incompatibility`.**
  `engine.routing.registry.PROFILES` is constructed so every workload
  class's own preferred profile (`engine.routing.policy.
  WORKLOAD_CLASSES[...].prefer`) already satisfies that class's declared
  `require`/environment need. There is no real candidate set in this
  codebase today whose entire preferred set fails gate 1 or gate 4;
  fabricating a registry entry that lacks a capability it does not
  really lack would misrepresent a certified profile, not simulate an
  outage of one. A future mission with a richer, non-uniformly-capable
  registry (Chapter 8, DDE-011/025 territory) is the natural point to
  add these.
- **`modality_mismatch`.** Stage 1 has no per-task modality signal at
  all — Chapter 5.2's Visual retriever is unbuilt until Stage 5
  (DDE-044). A "mismatch" needs two real modality values to compare;
  only one (a profile's declared capabilities) exists.
- **`budget_exhaustion`.** Gate 5 (`capacity_availability`) is a real,
  disclosed, hard-coded pass-through (`AVAILABILITY_NOT_TRACKED`) with
  no worker health/quota/concurrency/budget signal behind it yet
  (Chapter 8 Worker Manager / Chapter 7.4 warm pools, DDE-011/029).
  There is no real signal to exhaust.

Every `RoutingSimulationRun` row names any requested scenario class from
this deferred set via `disclosed_gaps`, never silently dropping it from
the persisted record.

## Consequences

- Chapter 6.4's regression/stress-testing use ("regression-testing
  policy changes before deployment", "stress-testing escalation and
  fallback chains") is real today for the three implemented classes —
  a policy-table change that breaks worker-outage handling,
  generator-independence enforcement, or the hard-approval-gate would
  be caught by `tests/unit/test_simulation_scenarios.py` and by any
  future CI job that calls `RoutingSimulationService.run_regression()`.
- `RoutingSimulationRun.experience_origin` is hard-coded `"simulation"`
  and `.excluded_from_routing_learning` is hard-coded `True` on every
  row — Chapter 6.8's "excluded by construction from any dataset used
  to train or promote a production policy" holds today even though no
  `ExperienceRecord` writer exists yet (DDE-057, Stage 7): this table
  simply carries no path into any future training pipeline by
  construction, the same discipline `FailureAttribution.
  excluded_from_routing_learning` (DDE-034/EDR-0004) already
  established.
- Cold-start sanity checks on new workload classes (Chapter 6.4's fourth
  named use) are mechanically possible today by adding a new
  `ScenarioFixture` branch in `engine.simulation.scenarios` once a real
  elimination signal exists for that class — not implemented for any
  specific new workload class by this mission, since none is chartered.

## Open questions / risks

- Whether a future mission should extend the worker-profile registry
  (Chapter 8) with at least one genuinely non-uniformly-capable profile
  set specifically so `capability_gap`/`environment_incompatibility`
  become real without fabrication, or whether that risk is better
  covered purely by Chapter 19.1's "Routing" contract-test suite instead
  of the RSM.
- Whether `budget_exhaustion` should wait for Chapter 7.4's warm-pool
  economics (DDE-029) or for a lighter, earlier capacity signal.
