# DDE-064 chapter gate -- production readiness review and removal-test
# pass ⟨§18.6⟩

**Mission:** §18.3 S7 / `DDE-064` -- production readiness review and
removal-test pass ⟨§18.6⟩. **Charter:** S7 exit completeness plus
Chapter 18.6 ("can this be removed without reducing verified outcomes
or increasing cost per verified success? Removals are recorded as EDRs
with the measurement that justified them"). **Not** Frontend Studio.

**Status:** CLOSED on `dde-064-production-readiness`.

**CI / local proofs (2026-08-27):**

- `just check` green -- ruff / mypy (**379** files) / **1167 passed, 3
  skipped** (unit+contract+recovery) / `generate_contracts --check` /
  contract pytest **185 passed** / design-lints baseline / dde-studio
  tests **67 passed** / desktop `tsc --noEmit`
- `tests/unit/test_readiness_removal.py` +
  `test_readiness_review_postgres.py`: **7 passed**. Unmeasured KEEP;
  outcome-drop KEEP; cost-increase KEEP; justifying measurement
  proposes EDR without deleting; `ReadinessReview.run` audits
  `readiness.reviewed` against live Postgres.

## Prior landings this chain

| Mission | SHA | Verdict |
|---|---|---|
| DDE-063 | `1654a1b` | PASS-WITH-EDR (EDR-0002, 0003, 0005, 0027, 0033) |

## What this mission wires

- `evaluate_candidate` (`engine.readiness.removal`): Chapter 18.6 rule.
  A candidate may be proposed for removal only when verified outcomes
  would not drop and cost per verified success would not increase.
  Missing measurement fail-closes to KEEP. This function never deletes.
- `ReadinessReview.run`: production caller. Evaluates every named
  §18.6 candidate, fail-closes unmeasured rows to KEEP, appends a
  durable `readiness.reviewed` audit event via `AuditService.append`.
  It never deletes a module. `PROPOSE_EDR` is the only non-keep
  verdict and still does not delete.
- Inventory: `S7_PRIOR_LANDINGS` names DDE-057 through DDE-063
  chapter-gate files (Ch.18.2 exit rows plus remaining Ch.18.3 S7
  landings). `REMOVAL_CANDIDATES` names the five Ch.18.6 re-examine
  targets. Missing files raise before any audit write.
- This pass supplied no live counterfactual. All five candidates KEEP
  (`unmeasured`). No removal EDR is recorded. Live overhead-row
  counterfactuals are **not** claimed.

## §18.6 MUST/shall at production call sites

| Rule | Production call site |
|---|---|
| Ask of every named candidate: removable without outcome drop or cost-per-verified-success increase? | `evaluate_candidate` at `ReadinessReview.run`. Unmeasured fail-closes to KEEP. |
| Removals recorded as EDRs with the measurement that justified them | `PROPOSE_EDR` does not delete. This pass has no justifying measurement, so no removal EDR. A human writes the EDR if a later review proposes one. |
| Re-examine: context critic, route critic, model-assisted planning, simulation model, retriever | Named in `engine.readiness.inventory.REMOVAL_CANDIDATES`. Evaluated at `ReadinessReview.run`. Route critic remains unimplemented (honest zeros in DDE-041 `ControlPlaneOverheadService.record_for_worker_run`); KEEP without a counterfactual. |
| S7 Ch.18.2 exit (learning gates, chaos, DR, Ch.16.5 SLOs) plus remaining Ch.18.3 S7 rows | Named in `S7_PRIOR_LANDINGS` (DDE-057 through DDE-063). Not re-implemented. |

## Adversarial self-check

- A new `WorkerRun` or new idempotency key cannot delete a named
  candidate. The KEEP/PROPOSE_EDR rule is on `ReadinessReview.run`;
  nothing else in this mission writes those modules away.
- Re-running the review appends another `readiness.reviewed` audit
  event. It still cannot delete.
- `ReadinessReview.run` is a real mutation (`AuditService.append` into
  `audit_events`), not a read/helper.
- Unmeasured KEEP is the fail-closed answer, not a claim that the
  five candidates were counterfactually measured. Claiming live
  removal-test telemetry would be an overclaim.
- `just readiness` exercises the production caller; it is not a
  second source of subsystem truth.

## Deferred (proposed / still-open EDRs)

| ID | Item |
|---|---|
| **EDR-0002 / 0003 / 0005 / 0027 / 0033** | Unchanged |
| Frontend Studio | Frozen. DDE-065+ are appended workstreams beyond the original §18.3 S7 chain (`docs/planning/product-studio-charter.md`). |
| Live counterfactual from overhead rows | Not claimed. Fail-close KEEP covers the unmeasured case. **No new EDR-0034.** |

## Verdict

**PASS-WITH-EDR.** EDR-0002, EDR-0003, EDR-0005, EDR-0027, EDR-0033
remain open. Chapter 18.6 is named at `evaluate_candidate` /
`ReadinessReview.run`. This pass removes nothing. S7 numbered
missions DDE-057 through DDE-064 are complete as the original §18.3
S7 chain. DDE-065+ are product-studio / Frontend Studio, not S7 core.

**Landed:** 2026-08-27 on `dde-064-production-readiness` (FF to `main`).
