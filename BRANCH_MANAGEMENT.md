# DDE Branch Management Policy

DDE has one persistent integration branch: `main`.

Branches are transport for candidate work, not Project Truth and not long-lived project memory. Architectural authority remains Project Truth, accepted EDRs, governed evidence, and the contracts they control.

## Mandatory lifecycle

1. Start every side-work branch from current `origin/main` after Project Truth verification.
2. Use a temporary prefix: `feat/`, `fix/`, `work/`, `docs/`, `ci/`, `test/`, `chore/`, `refactor/`, `security/`, or `hotfix/`.
3. A side branch must never claim authority with names such as `canonical`, `source-of-truth`, or `mainline`.
4. Push the branch and open a PR to `main`; an unmerged side branch without an open PR is an orphan and a governance failure.
5. Keep the PR synchronized with current `main`. Do not rebase or squash ledgered commits. If synchronization is needed, merge `main` into the side branch with a reviewable, ledgered merge result.
6. Merge only after Project Truth, Linux CI, Windows CI, and every path-applicable gate are green.
7. GitHub automatically deletes the side branch after merge. The completing agent must verify deletion before declaring the work closed.
8. If work is rejected or superseded, audit it against Project Truth, salvage accepted missing work through a new governed PR if necessary, then delete the obsolete branch.

## Persistent-branch rule

`main` is the only persistent branch. Release branches, personal integration branches, model-specific branches, recovered "canonical" branches, and permanent staging branches are forbidden unless the owner explicitly changes Project Truth to authorize one.

An active PR branch is explicitly **non-authoritative**. Its contents become part of the canonical integration lineage only after protected merge into `main`.

## Merge identity

DDE preserves ledgered commit identity. Repository settings therefore allow merge commits and disable squash/rebase merging. Protected `main` is strict/up-to-date, force pushes and branch deletion are disabled, and administrators are subject to protection.

## Changelog rule

Every material product/runtime/schema/migration/security/performance/refactor change updates `CHANGELOG.md` in the same PR. Documentation-only, test-only, and CI-only changes may omit a changelog entry unless they alter developer/operator behavior.

Changelog entries describe behavior that is accepted for integration; branch-only experiments are never written as completed changes.

## Fixed-bug ledger rule

Every `fix:` or `hotfix:` change appends at least one entry to `docs/project-state/BUG_FIX_LEDGER.jsonl` and regenerates `BUG_FIX_LEDGER.md`. Existing JSONL entries are immutable. Corrections are appended as new entries rather than rewriting history.

A fixed-bug entry records symptom, root cause, resolution, affected scope, regression proof, evidence, and the fixing commit (or `SELF` when the entry is committed with its fix).

## Automated enforcement

`Project Truth Guard` verifies branch naming, PR target, changelog/bug-ledger requirements, append-only bug history, and generated bug-ledger drift.

`Branch Governance` runs a remote audit daily and on demand. Every remote branch other than `main` must correspond to an open PR targeting `main`; otherwise the audit fails until the branch is reconciled and merged/deleted.

GitHub repository settings automatically delete merged PR branches. Repository branch protection requires the Actions-owned `project-truth`, `ci`, and `windows` checks before merge.
