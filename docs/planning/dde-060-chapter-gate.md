# DDE-060 chapter gate -- Flight Lab full suite / Ch.19

**Mission:** §18.3 S7 / `DDE-060` -- Flight Lab full suite ⟨Ch.19⟩.
**Charter:** Chapter 19.1 contract suites (schema, state transition,
negative, recovery for every listed suite) and Chapter 19.2 golden
mission `MISSION-ERP-000421` including the S7-added scenarios (worker
outage and a policy rollback). The golden mission must remain green on
every merge to `main`. **Not** DDE-061 chaos/worker-replacement,
DDE-062 DR/WORM, DDE-063 load, DDE-064 readiness, or Frontend Studio.

**Status:** STARTED on `dde-060-flight-lab` from `origin/main` @
`ea7e603` (DDE-059). Implementation not landed.

## Prior landings this chain

| Mission | SHA | Verdict |
|---|---|---|
| DDE-057 | `032439a` | PASS-WITH-EDR (EDR-0032) |
| DDE-058 | `24936b4` | PASS-WITH-EDR (EDR-0005, EDR-0027) |
| DDE-059 | `ea7e603` | PASS-WITH-EDR (EDR-0002, EDR-0003, EDR-0027) |

## Ch.19 MUST/shall to name at production call sites (or defer)

| Rule | Current disposition (audit, not closed) |
|---|---|
| Four tests per contract (schema, state, negative, recovery) | Many objects have unit/contract/recovery coverage from DDE-001..059; Flight Lab must inventory gaps rather than re-implement closed suites |
| Golden mission end-to-end on every merge to main | Exists as fixtures (`tests/support/mission_trace_fixtures.py`, client-parity); confirm it is the `MISSION-ERP-000421` shape and runs in `just check` |
| S7 adds worker outage + policy rollback | **Not landed.** Routing rollback is `LearningActivationService.rollback`; context rollback is `ContextActivationService.rollback`. Flight Lab must *attempt* a worker outage and a policy rollback as golden-mission scenarios, not merely unit-test the mutations |
| Workspace escape / symlink / credential-path (Ch.7 / §19.2) | Partial environment tests exist; Flight Lab must attempt them as security failures |
| Force-push of `main` / mission branches refused | Integration suite may cover; confirm a Flight Lab attempt exists |
| Learning suite: simulation/ineligible rows cannot train; promotion without gates refused; rollback | DDE-057/058/059 unit tests exist; promote into Flight Lab inventory |

## Deferred unless this mission closes them

| ID | Item |
|---|---|
| **EDR-0002 / 0003** | Context canary still unreachable; Flight Lab must not treat PARTIAL_PASS as promotion |
| **EDR-0027** | Sequence/WS/SSE gap replay -- Core, not this charter unless a Ch.19 recovery fixture requires it |
| Ch.6.10 pick-flip / exploration containment | Named from DDE-058 as DDE-060; include if it is a Ch.19 Routing suite fixture, else note as still later |
| DDE-061+ | Frozen |

## Verdict

**OPEN.** Next: inventory Ch.19.1 fixtures against existing tests, add
the S7 golden-mission worker-outage and policy-rollback scenarios at
real execution/routing/context call sites, close only what this mission
can name. Do not overclaim existing unit tests as the Flight Lab.
