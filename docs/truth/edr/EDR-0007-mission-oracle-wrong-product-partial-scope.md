# EDR-0007 — Chapter 11.3: mission-level AcceptanceOracle + wrong-product
# detection implemented; ProductEnvironment e2e, merge-to-main, and automatic
# replan invocation deferred

> **ACCEPTED 2026-08-22 by explicit human project-owner decision.** The
> authoritative record is the accepted row in the Project Truth `edrs` table
> (`edr_id=01a02cf3-018e-7eb0-b9e2-ba988dae7ee5`, owner project
> `9b6f1a58-e29a-4a35-a8e2-8e6c0f4b7d11`, written via
> `engine.truth.service.TruthService.propose_edr` + `accept_edr`). This file
> remains as readable documentation; where wording differs, the `edrs` row
> outranks it. Acceptance covers the design and deferrals **as documented** —
> ProductEnvironment end-to-end outcomes, merge-to-main gating and automatic
> replan invocation stay gated on their own missions.

> **Location note.** Per Chapter 3.6, an EDR is a row in the `edrs` table,
> written only by `engine/truth/`. The durable row now exists (see the
> acceptance note above). Following the convention established in
> `EDR-0001`–`EDR-0006`, this file stays as a readable pre-image of that row,
> filed as the proposal itself (AGENTS.md forbids editing `docs/truth/**`
> as a side effect).

- **slug:** `EDR-0007`
- **status:** `accepted (2026-08-22)`
- **supersedes:** none
- **affected_requirement_slugs:** none filed yet
- **raised during:** implementation of DDE-037 (`docs/blueprint/REV_2_0.md`
  §18.3's roadmap: "`DDE-037` mission-level AcceptanceOracle +
  wrong-product detection ⟨Ch.11.3⟩"), gate-reviewed independently after
  DDE-036 (Chapter 6.4 Routing Simulation Model, commit `ae8a2f8`) was
  found PASS-WITH-EDR.

## Context

Chapter 11.3: "Task oracles prove the tasks were done. The **mission**
oracle proves the right product was built." Three production rules:

1. Every mission with `risk ≥ medium` carries a mission oracle whose
   `observable_outcomes` are end-to-end and user-visible.
2. Mission completion requires the mission oracle to pass on the mission
   branch **before** merge to `main` (Ch.10.8).
3. If all task oracles pass and the mission oracle fails, the outcome is
   `WRONG_PRODUCT`: the mission enters replanning with the failing
   outcomes as context, and the discrepancy is a first-class learning
   signal about **decomposition quality**, not worker quality.

DDE-037 implements a real mission-scope `AcceptanceOracle` (`task_id`
null — never a fabricated task identity), a durable evaluator
(`MissionOracleService.evaluate()`, CommandLedger-guarded, driving the
same `run_check` path task oracles use), and a completion gate on
`MissionService.transition_mission(..., COMPLETED)`. WRONG_PRODUCT is
recorded only when every defined task-scope oracle has a latest
`PASSED` `VerificationRun` and the mission oracle itself fails.

## Decision (proposed)

The following Chapter 11.3 / adjacent rules are **deferred**:

- **End-to-end, user-visible outcomes against a ProductEnvironment.**
  Chapter 11.3 wants mission-oracle outcomes that are "end-to-end and
  user-visible." Stage 1 still has only `test`/`invariant` executable
  bindings (DDE-012); `api_probe`/`visual_diff`/`browser` and
  ProductEnvironment lifecycle are DDE-038/043/044. This slice runs the
  mission oracle's declared test/invariant bindings in the supplied
  workspace and names the ProductEnvironment gap in every evaluation's
  `disclosed_gaps`. It does not fabricate a product runtime.
- **Merge-to-main (Ch.10.8).** `IntegrationQueueService` still advances
  the mission integration branch, not origin `main`. The production
  completion gate is `MissionService.transition_mission` to `COMPLETED`
  — Chapter 4.9's "mission is COMPLETED only when ... the mission-level
  AcceptanceOracle passes." Origin-mainline merge remains the existing
  DDE-013 deferral.
- **Automatic replan invocation.** Chapter 11.3 says the mission
  "enters replanning." `RecoveryService.replan(trigger="WRONG_PRODUCT")`
  already exists (DDE-024) and REVERT of integrated nodes requires an
  explicit revert task (Ch.10.7). This slice classifies WRONG_PRODUCT,
  attaches `decide("WRONG_PRODUCT")` (replan, no silent worker retry) to
  the evaluation row, and refuses COMPLETED. It does not invent a revert
  task or call `replan()` itself.
- **Mission.risk field.** The Mission object has no `risk` column.
  "risk ≥ medium" is derived from `max(task.risk_class)` of the
  mission's tasks — the only real signal that exists.
- **"Authored during planning, before implementation"** is not a hard
  database constraint against an already-started WorkerRun. Definition
  is available as soon as the Mission row exists; tests (and operators)
  may define the mission oracle after a fixture WorkerRun. Sequencing
  is process, not a second lock.

## Consequences

- A planted wrong-product whose task oracles are green and whose
  mission oracle fails is classified WRONG_PRODUCT with
  `learning_signal_class=decomposition_quality` and
  `excluded_from_routing_learning=true` — by construction, not caller
  discretion.
- Medium-or-higher missions cannot COMPLETE without an ACCEPT
  evaluation. A WRONG_PRODUCT evaluation refuses COMPLETED even on a
  low-risk mission that happened to define a mission oracle.
- Recovery matrix WRONG_PRODUCT remains the operator/dispatch path for
  actually replanning.
