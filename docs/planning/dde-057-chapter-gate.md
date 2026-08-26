# DDE-057 chapter gate — ExperienceRecord + eligibility filtering + governed promotion

**Mission:** §18.3 S7 / `DDE-057` — ExperienceRecord + eligibility filtering +
governed promotion ⟨Ch.6.8⟩. **Charter:** Chapter 6.8 four-condition
eligibility filter; Chapter 3.8 ownership (`engine.learning`, promotion
state only after insert); Chapter 6.4 simulation-origin exclusion by
construction. **Not** DDE-058 (routing learner, shadow evaluation,
calibration, canary, rollback ⟨Ch.6.9⟩), DDE-059 adaptive context, or
DDE-065 Frontend Studio.

**CI / local proofs (2026-08-26):**

- `just check` green — ruff / mypy (**358** files) / **1100 passed, 2
  skipped** (unit+contract+recovery) / `generate_contracts --check` /
  contract pytest **182 passed** / design-lints baseline / dde-studio
  `tsc --noEmit`
- `tests/unit/test_learning_eligibility_rules.py`: **15 passed**
- `tests/unit/test_learning_postgres.py`: **5 passed** (production
  call sites against live Postgres)

## What landed

- `schemas/objects/experience_record.json` + generated contract/SQL/RLS
  (migration `0021`). Table CHECK forces
  `experience_origin=simulation ⇒ eligible_for_routing_training=false`.
- `engine.learning.rules.evaluate_eligibility` — pure Chapter 6.8 filter
  (origin, verification confidence, attribution, terminal) plus Chapter
  6.5 flaky-quarantine exclusion.
- Production writers:
  - `ExperienceRecordService.record_from_verification` at
    `VerificationRunnerService.run()` terminal PASSED/FAILED, same
    transaction as telemetry + flaky refresh.
  - `ExperienceRecordService.record_from_simulation` at
    `RoutingSimulationService.run_regression` and
    `evaluate_shadow_promotion`.
- Governed promotion mutation: `queue_for_learning` refuses simulation,
  ineligible, superseded, blocked, or consumed rows. Observational
  fields are not rewritten. `list_eligible_for_training` is the
  production read DDE-058 will consume.

## Rule disposition

| Rule | Production call site |
|---|---|
| Ch.6.8 origin=`real` (never simulation) | `evaluate_eligibility`; writer + table CHECK; `list_eligible_for_training` filters `experience_origin=real` |
| Ch.6.8 verification_confidence above threshold | `evaluate_eligibility` (`DEFAULT_VERIFICATION_CONFIDENCE_THRESHOLD=0.9`) at `record_from_verification` |
| Ch.6.8 attribution `route_attributable` or `none` | `map_failure_attribution` + `evaluate_eligibility`; low-confidence excluded classes down-weighted and flagged |
| Ch.6.8 terminal outcome (no in-flight / superseded) | Writer gated on PASSED/FAILED; `supersede_prior_for_task` on a later terminal attempt |
| Ch.6.5 flaky checks quarantined from routing learning | `record_from_verification` intersects failed check refs with `FlakyQuarantineService.list_active` after refresh |
| Ch.6.4 simulation excluded by construction | `record_from_simulation` always `eligible=false`; table CHECK; `queue_for_learning` refuses |
| Ch.3.8 promotion state only | `update_promotion_state` / `queue_for_learning` mutate only promotion fields |
| Ch.3.2 tenant_id/project_id + RLS | Schema `tenant_scoped`/`project_scoped`; generated ENABLE+FORCE RLS |
| Idempotency | UNIQUE on `verification_run_id` / `routing_simulation_run_id`; atomic `INSERT … ON CONFLICT DO NOTHING` |

## Deferred (proposed EDRs)

| ID | Item |
|---|---|
| **EDR-0032** | Chapter 6.8 names environment / tool / specification / upstream attribution classes. DDE-034 still only produces `context_attributed` / `not_context_attributed` / `inconclusive`. Those extra classes are reserved on the ExperienceRecord enum and excluded if ever written; they are **not fabricated**. Failures those writers do not distinguish may be labelled `route_attributable`. |
| **EDR-0027** | Sequence/WS/SSE gap replay (Core) — unchanged, not this charter |
| Ch.6.9 learner / shadow / canary / rollback | **DDE-058**, not deferred as an EDR |

## Adversarial self-check

- A new `WorkerRun` still goes through `VerificationRunnerService.run()`;
  there is no second verification mutation path that skips ExperienceRecord.
- A new idempotency key on verification creates a new `VerificationRun`
  and a new ExperienceRecord (correct); replaying the same key returns
  the first run and does not insert a second row (`UNIQUE verification_run_id`).
- `queue_for_learning` with a fresh `learning_run_id` cannot attach an
  ineligible or simulation row.
- Claimed call sites are real mutations (`record_from_verification`,
  `record_from_simulation`, `queue_for_learning`), not reads.

## Verdict

**PASS-WITH-EDR** — Chapter 6.8 ExperienceRecord, eligibility filter, and
governed promotion-state mutation are wired at production call sites.
Attribution vocabulary beyond DDE-034's three-way context outcome is
EDR-0032. Auto-proceed to DDE-058 authorized under the standing order.

**Landed:** 2026-08-26 on `dde-057-experience-record` (FF to `main`).
