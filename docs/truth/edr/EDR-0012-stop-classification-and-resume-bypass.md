# EDR-0012 — Chapter 12.3 stop classification and the resume bypass:
# wire INTENTIONALLY_STOPPED at its refusal sites; route resume_run
# through the armed-stop guard

> **Location note.** Per Chapter 3.6, an EDR is a row in the `edrs` table,
> written only by `engine/truth/`. Following the convention established in
> `EDR-0001`–`EDR-0011`, this file is a **markdown pre-image** of the eventual
> `edrs` row, filed as the proposal itself (AGENTS.md forbids editing
> `docs/truth/**` as a side effect). **This file is not itself an accepted
> EDR.** `status` is `proposed`; only a human decision via
> `scripts/accept_owner_edrs.py` can move it to `accepted`.

> **Slug note.** The work order that produced this review asked for this
> correction to be filed as "EDR-0011", but that slug is already a live,
> distinct PROPOSED record (`EDR-0011-t2-network-egress-and-container-
> containment.md`, referenced from `engine/capabilities/*`, blueprint Ch.14's
> termination amendment, and `docs/planning/gap-closure-record.md §6.3`).
> Slugs are unique per project (Chapter 3.6); two decisions cannot share one.
> This filing therefore takes the next free number, `EDR-0012`, and names
> the collision explicitly rather than silently renumbering or overwriting.

- **slug:** `EDR-0012`
- **status:** `proposed`
- **supersedes:** none (closes the two MAJOR findings of the independent
  chapter-gate review of the DDE-024 recovery landing; implements the already-
  accepted EDR-0010 at its real mutation sites)
- **affected_requirement_slugs:** none filed yet — should be linked to
  whatever requirement charters Chapter 12.3's recovery matrix once one
  exists as a Project Truth row.
- **raised during:** independent chapter-gate review (2026-08-23) of the
  intentional-stop mechanism (`engine/recovery/dispatch.py`,
  `engine/workers/service.py`, `engine/capabilities/kill_switch.py`),
  returned PASS-WITH-EDR with two MAJOR findings.

## Context

EDR-0010 (accepted 2026-08-23) added `INTENTIONALLY_STOPPED` as a first-class
Chapter 12.3 recovery class with governed action `acknowledge_stop`
(`requires_human=True`, no automatic retry, no new WorkerRun until the
operator acknowledges). The implementation shipped three pieces:

- `RecoveryService.classify_run_stop_failure_class`
  (`engine/recovery/dispatch.py`) — described by its docstring as "the
  classification writer for the kill-flag refusal sites";
- `RecoveryService.assert_clear_to_retry` — refuses any new WorkerRun for a
  task whose runs hold an ARMED durable stop record;
- `engine/recovery/matrix.py` — `KILL_FLAG_ACTIVE → INTENTIONALLY_STOPPED`.

The gate review found both halves of exactly the failure mode
`.cursor/rules/mission-chapter-gate.mdc` exists to catch: a docstring
claiming wiring that does not exist at any production call site, and an
adversarial path around a control.

**Finding A — classification gap (docstring overclaim).**
`classify_run_stop_failure_class` has ZERO production callers. The docstring
says "the kill-flag checkout/admission sites ... consult this before writing
the attempt's failure_class" — they do not; they raise typed
`KILL_FLAG_ACTIVE` without recording any attempt classification. The real
mid-run failure writer is `_drive_lifecycle`'s adapter-start handler in
`engine/workers/service.py`, which catches every non-EFFECT_CONFLICT
`DdeError` and records `WORKER_CAPABILITY_DENIED`. Consequence: a run killed
mid-flight by an armed stop is durably classified
`WORKER_CAPABILITY_DENIED`, which aliases to AUTHORIZATION_FAILURE in the
matrix — the exact borrowed classification EDR-0010 retired — instead of the
accepted `INTENTIONALLY_STOPPED` row. The accepted decision is not
operational at the one site where a mid-run stop actually lands.

**Finding B — resume bypass (the adversarial question).**
`WorkerManagerService.resume_run` creates a brand-new WorkerRun on an
IN_PROGRESS attempt with fresh capability leases, guarded only by
`assert_clear_to_start_attempt`, completed-result refusal, effect-journal
refusal and budget checks. It never calls `assert_clear_to_retry` nor
consults `_find_armed_stop`. Exploit window: arm a stop on run R1 while its
attempt is still IN_PROGRESS and R1 has not gone terminal — the operator's
stop has not yet been observed by R1's synchronous lifecycle. `resume_run`
passes the IN_PROGRESS check, fails R1 as `replaced_by_resume_run`, inserts
a NEW run whose id is unknown to the kill-switch registry, grants it fresh
leases, and drives its lifecycle: continuing the intentional stop without
operator acknowledgement. This answers the gate rule's question "could a
new WorkerRun bypass this control?" — currently yes. Chapter 12.4's law
("only verified absence permits a new mutation") is enforced for
`invoke_run` but not for the resume path.

## Decision (proposed)

Two wirings, minimal and at existing call sites; nothing new invented:

1. **Classification wired where failure classes are durably written.** The
   mid-run exception mapping in `WorkerManagerService._drive_lifecycle`
   consults the durable stop record when the caught `DdeError` carries
   `error_code == "KILL_FLAG_ACTIVE"` and records
   `INTENTIONALLY_STOPPED` instead of the borrowed
   `WORKER_CAPABILITY_DENIED`; every other code keeps today's mapping
   byte-identically (`EFFECT_CONFLICT → SIDE_EFFECT_UNKNOWN`, everything
   else `WORKER_CAPABILITY_DENIED`). The kill-flag refusal surfaces
   themselves (`require_active` checkout, broker credential admission)
   raise without writing attempt rows — their durable trail remains the
   enforcement events plus the ARMED ledger row, which the lifecycle writer
   now reads through the classifier. `classify_run_stop_failure_class`'s
   docstring is corrected to name its real callers.
2. **resume_run routed through the armed-stop guard.** Immediately after
   resolving the attempt (beside the existing recovery guards, before any
   prior-run replace, new run insert or lease grant), `resume_run`
   consults the same armed-stop semantics `assert_clear_to_retry` uses and
   refuses with typed `KILL_FLAG_ACTIVE` while any run of the task holds an
   ARMED stop record, recording observability consistent with the existing
   `_record_resume_refusal` pattern. After `disarm_run_stop` (the operator
   acknowledgement), resume proceeds exactly once as today.

What stays deferred (named, not silently open):

- Operator acknowledgement remains a service-layer act
  (`CapabilityLeaseService.disarm_run_stop`); no gateway command exposes it
  yet. Exposing `run.stop_acknowledge` over the gateway is follow-on work
  behind its own scope decision.
- "Exactly one new guarded run after DISARM" is enforced as absence-of-ARMED
  plus per-failure-class occurrence counters in
  `assert_clear_to_retry`, not by a dedicated post-stop counter.
- The T2 egress/container residuals remain under the distinct proposed
  EDR-0011; nothing here touches them.

## Consequences

- If adopted: a mid-run intentional stop is durably queryable as
  `INTENTIONALLY_STOPPED` end-to-end (matrix dispatch, acknowledge_stop,
  requires_human), and the resume bypass closes — no new WorkerRun can be
  minted past an unacknowledged stop. EDR-0010 becomes true at its
  production mutation call sites rather than in docstrings.
- If rejected: the borrowed `WORKER_CAPABILITY_DENIED` classification stands
  for mid-flight kills and `resume_run` stays a documented bypass; both must
  then be recorded explicitly as accepted divergences from accepted
  EDR-0010, not left as docstring claims.
