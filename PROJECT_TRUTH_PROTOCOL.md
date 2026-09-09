# Vanguduza Project Truth Protocol

This repository must never infer project truth from chat memory, the GitHub default branch, the newest timestamp, or the currently checked-out branch.

## Mandatory rules

1. Read `PROJECT_CANONICAL_STATE.json` before planning, coding, merging, building, packaging, deploying, or releasing.
2. Inspect divergent branches and source-of-truth/decision documents before declaring any implementation canonical.
3. Preserve every locked feature and later approved change during reconciliation. Silent thinning is forbidden.
4. Every pushed commit is automatically recorded in `docs/project-state/CHANGE_LEDGER.jsonl` by GitHub Actions, including commit SHA, parent, branch, author, timestamp, changed files, tree SHA, and diff digest.
5. `docs/project-state/CURRENT_STATE.json` records the latest observed repository state. It is evidence, not permission to declare a branch canonical.
6. Releases remain blocked while `canonical_state.release_blocked` is true.
7. A release/build provenance record must identify repository, exact commit SHA, branch/ref, target/module, and canonical-state revision.
8. If remembered state conflicts with Git, stop and reconcile the divergence. Git evidence wins over memory.

## Canonicalization

The default installation deliberately uses `CANONICAL_DISCOVERY_REQUIRED`. A project-specific reconciliation must identify locked design/product authorities, required ancestor commits, active integration lineage, deprecated branches/modules, and build/release entrypoints before clearing the release block.

## Automation boundary

The repository can automatically document durable Git changes as soon as they are pushed. Local edits that have never been committed or pushed do not yet exist in repository history; local tooling should still use normal Git commits frequently so the automatic ledger stays near-real-time.
