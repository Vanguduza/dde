# EDR-0009 — Chapter 6.5 routing-telemetry gap: guardrail-demoted PARTIAL
# VerificationRuns produce no telemetry outcome row

> **Location note.** Per Chapter 3.6, an EDR is a row in the `edrs` table,
> written only by `engine/truth/`. No such row exists yet. Following the
> convention established in `EDR-0001`–`EDR-0008`, this file is a
> **markdown pre-image** of the eventual `edrs` row, filed as the proposal
> itself (AGENTS.md forbids editing `docs/truth/**` as a side effect).
> **This file is not itself an accepted EDR.** `status` is `proposed`; only a
> human decision can move it to `accepted`.

- **slug:** `EDR-0009` (provisional)
- **status:** `proposed`
- **supersedes:** none
- **affected_requirement_slugs:** none filed yet — should be linked to
  whatever requirement charters Chapter 6.5 routing-decision telemetry once
  one exists as a Project Truth row.
- **raised during:** independent chapter-gate review of the verification
  self-grading guardrails (Chapter 11.1, `engine/verification/runner.py`
  `_evaluate` / `_fail_unverified_attempt`), which disclosed that a
  guardrail-demoted PARTIAL run "gets no `routing_decision_outcomes` row".

## Context

Chapter 6.5 requires DDE to record, for every decision, its *actual verified
outcome* among other outcome-side signals. The durable shape of that record
is the `RoutingDecisionOutcome` row (`schemas/objects/
routing_decision_outcome.json`, table `routing_decision_outcomes`), whose
`actual_verified_outcome` enum admits only two values:

```json
"actual_verified_outcome": { "type": "string", "enum": ["PASSED", "FAILED"] }
```

The production writer honours that enum as a gate:
`RoutingTelemetryService.record_decision_outcome`
(`engine/telemetry/service.py`) refuses any `VerificationRun` whose status is
not terminal `PASSED` or `FAILED` (`POLICY_DENIED: telemetry is recorded
only for a terminal VerificationRun`).

The verification self-grading guardrails introduced a third real verdict:
when `VerificationRunnerService.run()` detects harness-gaming edits
(undeclared test-path edits or shadow expected-test files) via
`engine.verification.guardrails.assess_diff_independence`, it still runs the
oracle's checks but forces the run's status to **PARTIAL** (never PASSED) so
an untrusted clean pass is not certified. The attempt is durably FAILED with
`failure_class="SCOPE_VIOLATION"` through the existing recovery surface —
but the PARTIAL `VerificationRun` itself can never produce a telemetry
outcome row: the enum has no PARTIAL value and the service gate rejects it.

Consequence today: every guardrail-demoted verification silently drops out
of Chapter 6.5's decision-outcome history. Routing-learning consumers reading
`routing_decision_outcomes` see no trace that these runs happened, even
though the runs are real, durable, and safety-relevant — they are exactly
the population a learning pipeline must not train on as successes, and
exactly the population worth counting when tuning guardrail thresholds.

## Decision (proposed)

Record guardrail demotions without blueprint enum surgery. Two options were
considered; the second is recommended:

1. **Widen the enum/schema.** Admit `"PARTIAL"` in
   `actual_verified_outcome` and add a `demotion_reason` field to
   `RoutingDecisionOutcome`. This changes a Chapter 6.5 schema contract for
   a Stage-1-only producer, and blurs the chapter's meaning of
   `actual_verified_outcome` (a demoted-but-clean-checking run did not
   "fail"; certifying what happened needs a new field either way).

2. **Side-table keyed by verification_run_id (recommended).** Keep
   `actual_verified_outcome` PASSED/FAILED and `record_decision_outcome`'s
   terminal gate untouched. Add a small durable side-table (e.g.
   `verification_run_demotions`: `verification_run_id` unique FK,
   `reason`/`guardrail_findings`, timestamps) written by the same guarded
   path in `engine.verification.runner` that already forces PARTIAL.
   Telemetry consumers join on `verification_run_id` when they need the
   demoted population; the main Chapter 6.5 row stays exactly as the
   blueprint defines it.

Option 2 keeps `schemas/objects/routing_decision_outcome.json` byte-stable,
needs no change to `RoutingTelemetryService`, and gives the demotion its own
durable identity instead of overloading an outcome enum designed before the
guardrails existed.

## Consequences

- If adopted: every guardrail-demoted PARTIAL run leaves a queryable trace;
  Chapter 6.5 consumers can exclude or count them explicitly; the blueprint
  enum stays untouched; a new table + writer + contract test is needed (its
  own mission).
- If rejected: the gap stays open and should be named in the runner's
  disclosed-gaps documentation rather than silently accepted — today it is
  documented in a docstring but invisible in data.
