# DDE-069 candidate verification execution

State: `IMPLEMENTED_BOUND` — production PostgreSQL E2E unavailable on this host.

## What is now real

A Frontend candidate no longer stops at a durable verification request. The
request can execute through DDE-068's existing verification authority and
produce ordinary `VerificationRun` and `Evidence` records without fabricating a
WorkerRun.

Canonical flow:

```text
hash-confirmed LIVE candidate preview
→ FrontendVerificationRequest PENDING
→ frontend.verification.run
→ request RUNNING / candidate VERIFYING
→ exact candidate document + AcceptanceOracle
→ real capability leases
→ shared DDE-068 checks/evidence writer
→ VerificationRun PASSED|FAILED|PARTIAL
→ request PASSED|FAILED (or stays SUPERSEDED)
→ candidate VERIFIED|FAILED with current verification_run_id
```

## Lineage correction

`VerificationRun` had been implemented more narrowly than Blueprint Rev 3
§17.1 and Frontend Studio Rev 3 §20.1: it required a WorkerRun and TaskAttempt
even though canonical verification also covers a candidate/accepted revision.
Migration `0029_verification_subject_lineage.py` preserves all worker lineage
while adding typed subject lineage. Existing rows backfill as `WORKER_RUN`;
Frontend edits use `FRONTEND_CANDIDATE`. Downgrade fails closed if non-worker
evidence exists rather than deleting or inventing lineage.

## Capability authority

Candidate verification does not bypass Chapter 9. `CapabilityLease.worker_run_id`
was already nullable; `CapabilityLeaseService.require_active_lease` now permits
an explicitly identified non-worker lease and deliberately rejects any
WorkerRun-bound lease, which must continue through the original kill-flag-aware
checkout. Browser and EDR-0017 visual-critic adapters are wrapped so each call
rechecks its lease.

`capability.claude_code_invoke` is unchanged and is not used here.

## Exact render identity

AcceptanceOracle definitions remain immutable. At execution, only the render
URL is rebound to the exact materialized candidate preview document. Silhouette,
visual critique and visual-diff therefore inspect candidate code, while golden
paths, thresholds, outcome identity and authored expectations remain the
accepted oracle's values. The effective runtime URL is recorded in check/evidence
output.

## Stale-evidence safety

A mutation clears the candidate's attached verification run and supersedes
outstanding requests. Promotion now loads only `candidate.verification_run_id`;
it no longer consumes every historical run for a task. An old PASSED run cannot
approve changed candidate code.

If a request becomes superseded while a verifier is finishing, the completed
run remains attached to the request for audit but cannot become current
candidate evidence.

## Workbench evidence

The React workbench executes each new PENDING request once after LIVE. Candidate
cards show request state; QA shows the attached run, check statuses, evidence
count and confidence; Inspector shows current PASSED coverage for its required
screen verification kinds or an explicit stale/not-evaluated state.

## Verification

Runnable on the current host:

- generated-contract drift: PASS
- binding-matrix drift: PASS
- Ruff: PASS
- mypy over changed verification/studio/gateway paths: PASS
- focused Python: 68 passed
- React TypeScript: PASS
- Playwright: 22 passed
- extension tests: 75 passed
- `git diff --check`: PASS

Database-backed proof is present in
`tests/unit/test_candidate_verification_runner_postgres.py`, but this execution
host has no `DDE_DATABASE_URL`, `DDE_REDIS_URL`, Docker, PostgreSQL or Redis.
That test is therefore `UNAVAILABLE`, not passed or failed here.

## Residuals

- Real VS Code → Gateway → PostgreSQL candidate verification E2E remains BOUND.
- The narrow visual critic may consume a real authorized provider/runtime when a
  user actually verifies a candidate; development tests use fakes and did not
  spend critic quota.
- React Frontend Chat is the next packet.
- Screen Audit and M8 Source Intelligence remain mandatory downstream.
- AD-039 still blocks pixel-reference conformance.
