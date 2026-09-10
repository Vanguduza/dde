# Vanguduza Project Truth Protocol

This repository must never infer project truth from chat memory, the GitHub default branch, the newest timestamp, or the currently checked-out branch.

## Mandatory rules

1. Read `PROJECT_CANONICAL_STATE.json` before planning, coding, merging, building, packaging, deploying, or releasing.
2. Inspect divergent branches and source-of-truth/decision documents before declaring any implementation canonical.
3. Preserve every locked feature and later approved change during reconciliation. Silent thinning is forbidden.
4. Every substantive commit must have durable evidence in `docs/project-state/CHANGE_LEDGER.jsonl` before protected merge. Pure merge-carrier commits whose tree is identical to a parent, and commits changing only `docs/project-state/`, are lineage/evidence carriers rather than new truth-bearing changes.
5. `docs/project-state/CURRENT_STATE.json` records the latest observed repository state. It is evidence, not permission to declare a branch canonical.
6. Releases remain blocked while `canonical_state.release_blocked` is true.
7. A release/build provenance record must identify repository, exact commit SHA, branch/ref, target/module, and canonical-state revision.
8. If remembered state conflicts with Git, stop and reconcile the divergence. Git evidence wins over memory.

## Canonicalization

DDE has completed repository-lineage reconciliation: `main` is the sole verified **integration lineage**, while authority continues to come from the canonical Project Truth, accepted EDRs and governed evidence rather than branch recency. `canonical_state.required_ancestors` records the reconciled VEKL v2 integration merge. The release block remains independent and must not be cleared until separately owned incomplete release gates are evidenced.

## Automation boundary

GitHub Actions is a **read-only Project Truth guard** on protected branches and pull requests. It validates the canonical-state manifest and verifies that substantive commits are already represented by durable ledger evidence. CI MUST NOT self-push Project Truth updates into protected `main`.

Local/authorized tooling records staged substantive diffs before commit. When a commit is necessarily created through an API path that cannot run the local pre-commit recorder, a later explicit reconciliation commit may backfill that exact commit SHA, changed-file set and diff digest; verification uses the durable ledger at the current head and does not silently accept missing evidence.

A merge commit is exempt only when it is a pure lineage carrier whose tree is identical to one of its parents. A merge that introduces novel conflict-resolution content remains substantive and must be ledgered. Local edits that have never been committed do not yet exist in repository history.
