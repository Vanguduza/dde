# DDE-064 chapter gate -- production readiness review and removal-test
# pass ⟨§18.6⟩

**Mission:** §18.3 S7 / `DDE-064` -- production readiness review and
removal-test pass ⟨§18.6⟩. **Charter:** S7 exit completeness plus
Chapter 18.6 ("can this be removed without reducing verified outcomes
or increasing cost per verified success? Removals are recorded as EDRs
with the measurement that justified them"). **Not** Frontend Studio.

**Status:** STARTED on `dde-064-production-readiness` from `origin/main`
@ `1654a1b` (DDE-063). Chapter gate OPEN.

## Prior landings this chain

| Mission | SHA | Verdict |
|---|---|---|
| DDE-063 | `1654a1b` | PASS-WITH-EDR (EDR-0002, 0003, 0005, 0027, 0033) |

## §18.6 MUST/shall to name at production call sites (or defer)

| Rule | Current disposition |
|---|---|
| Ask of every named candidate: removable without outcome drop or cost-per-verified-success increase? | **This slice:** `evaluate_candidate` at `ReadinessReview.run`. Unmeasured fail-closes to KEEP. |
| Removals recorded as EDRs with the measurement | PROPOSE_EDR does not delete. No candidate is auto-removed this mission. |
| Re-examine: context critic, route critic, model-assisted planning, simulation model, retriever | Named in `engine.readiness.inventory.REMOVAL_CANDIDATES`. Route critic remains unimplemented (honest zeros in DDE-041); KEEP without a counterfactual. |
| S7 prior rows (learning gates, chaos, DR, Ch.16.5 SLOs) | Named in `S7_PRIOR_LANDINGS`. Not re-implemented. |

## Deferred unless this mission closes them

| ID | Item |
|---|---|
| **EDR-0002 / 0003 / 0005 / 0027 / 0033** | Unchanged |
| Frontend Studio | Frozen |

## Verdict

**OPEN.** Next: `just check` after this slice, then name any remaining
§18.6 MUST at a production call site or defer with the next free EDR
(0034).
