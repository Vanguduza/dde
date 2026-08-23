# EDR-0013 — ProductEnvironment verification composition, seed
# versioning, teardown event atomicity, and principal-trust disclosure

> **Location note.** Per Chapter 3.6, an EDR is a row in the `edrs` table,
> written only by `engine/truth/`. Following the convention established in
> `EDR-0001`–`EDR-0012`, this file is a **markdown pre-image** of the eventual
> `edrs` row, filed as the proposal itself. **This file is not itself an
> accepted EDR.** `status` is `proposed`; only a human decision via
> `scripts/accept_owner_edrs.py` can move it to `accepted`.

- **slug:** `EDR-0013`
- **status:** `proposed`
- **supersedes:** none (carries the four MINOR residuals that kept the
  independent chapter-gate review of DDE-038 from being a clean PASS;
  none breaks a MUST/shall at a production call site today)
- **raised during:** independent chapter-gate review (2026-08-23) of the
  DDE-038 ProductEnvironment landing (`4302973`) and the EDR-0012
  correction mission (`2c71727`); verdict PASS-WITH-EDR.

## Context

The gate review verified every Chapter 11.6 and Chapter 12.3/12.4 rule in
scope wired at real production call sites (state machine single mutation
site, worker/TTL/binding refusals, bidirectional READY gate, migration
0012 idempotence, RLS fail-closed predicates, armed-stop classification
and resume guard). Four bounded residuals remain; they are recorded here
with their smallest corrections rather than silently open.

**Finding 1 — verifier-to-service composition gap.**
`ProductEnvironmentService.apply_migrations_forward(empty_verified=...,
previous_verified=...)` records caller-asserted booleans; no production
code composes `MigrationVerifier`'s real `VerificationResult` into it —
today both are exercised only from tests with literals. The bidirectional
MUST is still enforced at the real `mark_ready` mutation site against the
recorded flags, so this is not a docstring-overclaim failure mode — but
the flags themselves are trusted input until provisioning automation
exists.

**Finding 2 — abandoned-event UoW split.**
`teardown_expired` commits the teardown transaction, then appends
`ProductEnvironmentAbandoned` in a separate `uow=None` unit of work. A
crash between the two destroys the row but loses the monitored-metric
event. The append should fold into the same unit of work as the teardown.

**Finding 3 — seed version hardcode.**
`SeedRegistry.register` writes `version=1` despite the module docstring
claiming supersession semantics; a second distinct-artifact registration
of the same slug violates `UNIQUE (tenant_id, project_id, slug, version)`
instead of creating v2. Next version should be computed from existing
rows. Related nit: the reproducibility hash covers the artifact *pointer*
(`artifact_ref`), not payload bytes.

**Finding 5 — principal trust disclosure.**
`requested_by_origin` on `provision()` is an unverified caller string;
the worker-origin FORBIDDEN refusal is only as strong as principal
authentication, which is globally deferred (disclosed at
`engine/truth/db.py`, DDE-027/DDE-051). The dependency must be named in
the service docstring so the refusal is never mistaken for an
authentication control.

*(The review's Finding 4 — a dead `_script_head` helper left in
`engine/product_env/verification.py` after the database-revision fix — is
a plain cleanup, applied directly without an EDR.)*

## Decision (proposed)

1. **Composition deferred to first provisioning consumer, filed now.**
   When DDE-043/044 build provisioning automation, the service must
   accept (or internally run) `MigrationVerifier` results instead of
   caller-asserted booleans — or require verifiable evidence references
   in the recorded halves. This EDR is the filing that obligation now,
   so no future mission can treat the boolean parameters as a settled
   contract.
2. **Event atomicity fix** at `teardown_expired`: same-unit-of-work event
   append, pinned by a test that observes both the row state and the
   outbox in one commit boundary.
3. **Seed versioning fix**: compute next version per
   `(tenant_id, project_id, slug)` inside the register transaction;
   reproducibility fingerprint unchanged (same identity inputs).
4. **Docstring disclosure** on `ProductEnvironmentService.provision`
   naming the authentication deferral.

What stays deferred (named, not silently open): payload-bytes hashing for
seed fingerprints (pointer-hash remains adequate while artifacts are
repo-resident); none.

## Consequences

- If adopted: DDE-038 closes clean; the four residuals have owners,
  timing (2-4 immediate, 1 at DDE-043/044), and smallest corrections.
- If rejected: each residual must be re-recorded as an accepted
  divergence from Chapter 11.6's intent or explicitly re-scoped, not left
  implicit.
