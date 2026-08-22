# EDR-0005 — Chapters 6.5–6.7: real telemetry implemented; Route Critic, exploration and actual cost deferred

> **ACCEPTED 2026-08-22 by explicit human project-owner decision.** The
> authoritative record is the accepted row in the Project Truth `edrs` table
> (`edr_id=01a028c4-a124-7a84-bd1b-2bd06f206f27`, owner project
> `9b6f1a58-e29a-4a35-a8e2-8e6c0f4b7d11`, written via
> `engine.truth.service.TruthService.propose_edr` + `accept_edr`). This file
> remains as readable documentation; where wording differs, the `edrs` row
> outranks it. Acceptance covers the design and deferrals **as documented** —
> the Route Critic, exploration, real predictions and actual-cost recording
> stay gated on their own missions.

> **Location note.** Per Chapter 3.6, an EDR is a row in the `edrs` table,
> written only by `engine/truth/`. No such row exists yet. Following the
> convention established in `EDR-0001-subscription-based-worker-credentials.md`,
> `EDR-0002-semantic-retriever-default-gating.md`,
> `EDR-0003-promotion-gate-partial-implementation.md` and
> `EDR-0004-failure-attribution-partial-implementation.md`, this file is a
> **markdown pre-image** of the eventual `edrs` row, filed as the proposal
> itself (not a side effect of implementing DDE-035 — AGENTS.md forbids
> editing `docs/truth/**` as a side effect). **This file is not itself an
> accepted EDR.** `status` is `proposed`; only a human decision can move it
> to `accepted`, at which point the durable record belongs in `edrs`, and
> this file should be deleted or reduced to a pointer.

- **slug:** `EDR-0005` (provisional)
- **status:** `proposed`
- **supersedes:** none
- **affected_requirement_slugs:** none filed yet — should be linked to
  whatever requirement charters Chapter 6.5's real-telemetry engine once
  it exists as a Project Truth row.
- **raised during:** implementation of DDE-035 (`docs/blueprint/REV_2_0.md`
  §18.3's roadmap: "`DDE-035` routing telemetry, propensity logging,
  shadow mode ⟨Ch.6.5–6.7⟩"), gate-reviewed independently after DDE-034
  (Chapter 5.11 failure attribution engine, commit `ff39fd7`) was found
  PASS on substance.

## Context

Chapter 6.5: "Even under deterministic routing, DDE records for every
decision: candidate set with elimination gates, predictions, selection
propensity, actual verified outcome, verification confidence, rework
count, escalation, human intervention, actual token/tool cost, elapsed
time, failure class, recovery path, context policy version, capability
set, and the attribution from §5.11. This is cheap, must never be
skipped, and is the only thing that makes later learning possible without
an architectural migration."

`engine.routing.service.RouterService.route()` (DDE-027/S3) already
persists the decision-time half of that list on every `RouteDecision`
row — `candidates`, `predicted_success`/`predicted_cost`/
`predicted_latency`/`confidence` (currently always `None`, disclosed in
that module's own docstring), and `selection_propensity` (fixed `1.0`,
Chapter 6.3's literal value for a deterministic selection). Its own
docstring already named the gap this mission closes: "real performance/
cost telemetry and predictions ... Chapter 6.5's telemetry pipeline is
DDE-035/S4."

DDE-035 implements the real production writer, `engine.telemetry`, for
the outcome-side half of Chapter 6.5's list — the fields no
`RouteDecision` can know about itself because they only exist once the
routed attempt has actually been verified. It is wired into the one real
mutation call site Chapter 6.5's "for every decision" and "must never be
skipped" language names: `engine.verification.runner.
VerificationRunnerService.run()`'s two terminal branches (`PASSED` and
`FAILED`), in the same transaction as that run's own status write and the
`TaskAttempt` finalise/fail call. The real `RouteDecision` a
`RoutingDecisionOutcome` belongs to is resolved through the already-real
`WorkerRun.execution_plan_id -> ExecutionPlan.route_decision_id` chain
(Chapter 7.1), never invented. Every `RoutingDecisionOutcome` row is
genuinely idempotent on `verification_run_id` (a real `UNIQUE` constraint
plus an atomic `INSERT ... ON CONFLICT DO NOTHING RETURNING`, the same
race-safe pattern `engine.attribution` (DDE-034) uses).

Two gaps are deliberately left open, disclosed in `disclosed_gaps` on
every persisted row (for the cost gap) and in this EDR (for the two
un-implemented chapters), not silently claimed as done:

1. **Actual token/tool cost is not recorded.** `WorkerRun.usage_record_id`
   references a `UsageRecord` concept no writer in this codebase produces
   yet. Every `RoutingDecisionOutcome` names this gap explicitly via
   `disclosed_gaps` (`engine.telemetry.model.ACTUAL_COST_GAP_DISCLOSED`).
2. **"Context policy version" has no writer.** Chapter 6.5 names it as a
   telemetry field, but no versioned "context policy" concept exists
   anywhere in this codebase yet (that is Chapter 5.13/`EDR-0003`
   promotion territory: `PromotionGateRun` versions a context *policy
   change*, not a per-decision "policy version" a `RouteDecision` was
   made under). `RoutingDecisionOutcome.context_package_id` stores the
   real, durable `ContextPackage` the verified attempt actually used
   instead — a genuine pointer a future policy-version concept can join
   through, not a fabricated version string.

## Decision (proposed)

Chapters 6.6 (Route Critic) and 6.7 (exploration and propensity) are
**not implemented** by this mission, for the same reason
`engine.routing.service`'s own pre-existing docstring already gave:
both explicitly need real telemetry as an input, which is exactly what
this mission produces for the first time.

- **Chapter 6.6 (Route Critic — triggered).** Its triggers are
  `risk_class >= high`; financial/security/production blast radius; "a
  prior attempt on this task failed verification"; or "predicted-success
  confidence is below threshold." The first three conditions are already
  real, checkable signals (`Task.risk_class`/`blast_radius`,
  `RoutingDecisionOutcome.rework_count > 0` as of this mission). The
  fourth is not: `RouteDecision.predicted_success`/`.confidence` are
  still always `None` (no model or heuristic produces a real prediction
  yet), so "confidence is below threshold" cannot be evaluated for real.
  Implementing the critic's trigger logic today would mean either
  silently treating "no prediction" as "below threshold" (fabricating a
  trigger reason) or omitting the condition without disclosure — both
  worse than deferring the whole sub-chapter honestly. A future mission
  that adds real `predicted_success` (Stage 4/5 per the routing
  simulation/learning chapters) is the natural point to also implement
  Chapter 6.6.
- **Chapter 6.7 (Exploration and propensity).** `selection_propensity` is
  already correctly `1.0` for every Stage 1 deterministic decision
  (Chapter 6.3's own literal value), and epsilon already defaults to `0`
  in `engine.routing.rules`/`policy` (no tenant enables it). Implementing
  real ε-greedy exploration would select among "eligible candidates"
  using some ranking — but with no real `predicted_success` to rank by,
  "uniformly among eligible candidates" is the only honest interpretation
  Stage 1 could implement, and Chapter 6.1's deterministic policy table
  already produces exactly one eligible candidate per gate in the common
  case (there is no meaningful "exploration" over a policy table that
  does not yet expose multiple ranked candidates to explore over). Real
  exploration is deferred to the mission that gives routing a genuine
  ranked candidate set to explore among.

`RoutingDecisionOutcome.escalated` and `.human_intervention_required` are
real signals today (read directly from `engine.recovery.matrix.
RecoveryDecision.action`/`.requires_human`, the same recovery decision
`engine.verification.runner`'s `FAILED` branch already computes) —
**not** a stand-in for Chapter 6.6's Route Critic, which is a distinct,
still-deferred routing-time mechanism.

## Consequences

- Chapter 6.8's `ExperienceRecord` (DDE-057, Stage 7) can now be built
  against two real, independently-tested upstream sources instead of one:
  `FailureAttribution` (DDE-034) for the `failure_attribution` eligibility
  filter, and `RoutingDecisionOutcome` (this mission) for
  `verification_confidence`, `observed_outcome_vector`-shaped signals and
  `attribution_confidence`. Neither is rewired to feed `ExperienceRecord`
  by this mission; that remains DDE-057's job, named here rather than
  silently assumed.
- `RoutingDecisionOutcome.failure_attribution_id` is a real, non-null FK
  on every `FAILED` row (verified directly against the same-transaction
  `FailureAttribution` row `engine.attribution` wrote moments earlier) —
  the loop `EDR-0004` named as a live, unwired integration opportunity
  ("Neither is rewired to consume it by this mission") is now closed for
  the telemetry side specifically, though `EDR-0004`'s own named gaps
  (Context Critic's `previously_context_attributed_failure`, Chapter 5.13
  gate 2) remain open exactly as that EDR describes.
- `engine.context.critic`/`engine.context.service` docstrings previously
  said Chapter 5.11's pipeline "is not built anywhere in this codebase
  yet" — stale as of DDE-034. Corrected in this mission (no logic change)
  to say the pipeline exists but has no production caller resolving it
  into `compile()`'s `previously_context_attributed_failure` parameter
  yet, since `ContextService.compile()` itself still has no production
  caller outside tests.

## Open questions / risks

- Whether Chapter 6.6's Route Critic should be implemented against a
  *heuristic* (non-model) `predicted_success` proxy before a real
  learned model exists, the way `engine.context.critic`'s confidence
  proxy uses `_mean_relevance` — or whether that is exactly the kind of
  approximation this codebase's no-fabricated-signal discipline should
  refuse until a real prediction pipeline exists.
- Whether `RoutingDecisionOutcome` should eventually carry its own
  `context_policy_version` column once Chapter 5.13's promotion-gate
  versioning is extended to cover a per-decision policy identifier, or
  whether `context_package_id` remains the permanent, sufficient join
  key.
