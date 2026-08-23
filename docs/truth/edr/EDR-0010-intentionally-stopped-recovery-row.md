# EDR-0010 — Chapter 12.3 recovery matrix: no governed row for an
# intentionally stopped run (kill flag)

> **Location note.** Per Chapter 3.6, an EDR is a row in the `edrs` table,
> written only by `engine/truth/`. No such row exists yet. Following the
> convention established in `EDR-0001`–`EDR-0008`, this file is a
> **markdown pre-image** of the eventual `edrs` row, filed as the proposal
> itself (AGENTS.md forbids editing `docs/truth/**` as a side effect).
> **This file is not itself an accepted EDR.** `status` is `proposed`; only a
> human decision can move it to `accepted`.

- **slug:** `EDR-0010` (provisional)
- **status:** `proposed`
- **supersedes:** none
- **affected_requirement_slugs:** none filed yet — should be linked to
  whatever requirement charters the Chapter 12.3 recovery matrix once one
  exists as a Project Truth row.
- **raised during:** review of the kill-flag mechanism (durable stop record
  in CommandLedger, commit `0df07eb`; `engine/capabilities/kill_switch.py`),
  which surfaced that an intentional stop has no dedicated recovery-matrix
  row and currently maps onto a borrowed classification.

## Context

Chapter 12.3's recovery matrix dispatches on failure class. The implemented
matrix (`engine/recovery/matrix.py`) recognises WORKER_FAILURE,
MERGE_CONFLICT, SCOPE_VIOLATION, VERIFICATION_FAILURE, WRONG_PRODUCT,
SPECIFICATION_FAILURE, RESOURCE_EXHAUSTION, SIDE_EFFECT_UNKNOWN and
DRIFT_FAILURE — every row describes something going *wrong* with the work.

An operator stopping a run via the kill flag is not a failure of the work.
The mechanism is real and durable today:

- the durable stop record lives in the CommandLedger under one deterministic
  key per run (`kill_flag_run_stop:{worker_run_id}`,
  `engine/capabilities/kill_switch.py`, commit `0df07eb`), armed/flipped by
  `CapabilityLeaseService.arm_run_stop` / `disarm_run_stop`;
- enforcement fails closed at capability checkout and broker admission with
  typed `KILL_FLAG_ACTIVE`.

But because Chapter 12.3's taxonomy has no distinct intentionally-stopped
class, the mapping layer routes the refusal onto a borrowed row:

```python
# engine/recovery/matrix.py
"KILL_FLAG_ACTIVE": "AUTHORIZATION_FAILURE",
```

with the inline admission that this mapping was chosen *because* "Chapter
12.3's taxonomy has no distinct intentionally-stopped class; adding one
would be a Project Truth change, proposed not made." That proposed change is
this EDR.

The mismatch is semantic, not just cosmetic: AUTHORIZATION_FAILURE means
"the system refused to act; a human must grant authority" — its governed
action is to stop until approval. An intentional stop is the opposite
posture: authority was deliberately withdrawn by an operator, the work is
expected to stay stopped, and resuming it should require an explicit
acknowledge-style action after the stop is reviewed, rather than being
misread downstream as a VERIFICATION/AUTHORIZATION failure episode. A run
stopped mid-flight by design currently surfaces through generic failure
paths and can be re-attempted wherever those rows allow new worker runs.

## Decision (proposed)

Add a distinct recovery-matrix entry for the intentional stop so it is
governed on its own terms instead of being misread as VERIFICATION_FAILURE /
AUTHORIZATION_FAILURE. Sketch (exact action names to be settled against
Chapter 12.3's action vocabulary when implemented):

- **Key:** a distinct failure classification, e.g.
  `INTENTIONALLY_STOPPED` (raised from the existing `KILL_FLAG_ACTIVE`
  refusal sites and/or the durable ledger stop record).
- **Governed action:** `acknowledge` — no automatic retry, no replan;
  `requires_human=True`.
- **New worker run:** `allow_new_worker_run=False` until an operator
  acknowledges the stop; after acknowledgement a new WorkerRun is permitted
  (`allow_new_worker_run=True`) through the normal guarded path, never a
  silent continuation of the stopped attempt.

This is exactly the "adding one would be a Project Truth change" case the
mapping comment anticipated: the blueprint chapter's matrix gains a row (or
the taxonomy gains a class) only via an accepted EDR, never by editing
`engine/recovery/matrix.py` alone. Until accepted, the
`KILL_FLAG_ACTIVE → AUTHORIZATION_FAILURE` mapping remains the governing
behaviour.

## Consequences

- If adopted: intentional stops become a first-class, queryable recovery
  outcome with acknowledge-gated restarts; the borrowed
  AUTHORIZATION_FAILURE row is retired for this case; consumers that count
  failures stop conflating operator stops with refusals or verification
  failures; requires a schema/classification addition plus matrix wiring in
  its own mission.
- If rejected: the status quo stands and should be recorded explicitly —
  intentional stops remain governed only by the borrowed authorization row,
  with the semantic mismatch acknowledged in the matrix comment rather than
  resolved.
