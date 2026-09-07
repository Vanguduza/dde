# DDE-069 Recovery Feature-Preservation Register

Date: 2026-09-07
Baseline: `ebee865` (`DDE-069 consolidate source of truth`)
State: recovery repairs implemented; uninterrupted G1 is GREEN; DDE-069 remains IN_PROGRESS.

## Recovery law

This tranche repairs blockers without deleting, weakening, bypassing or silently reinterpreting accepted capabilities. When two authoritative features collided, both were retained behind distinct contracts and storage ownership.

## Feature-preservation register

| Capability / invariant | Defect found | Recovery | Preservation result |
| --- | --- | --- | --- |
| DDE-057/058 routing-learning experience | DDE-069 execution-experience work reused `ExperienceRecord` / `experience_records` and displaced routing-learning semantics | Restored routing-learning `ExperienceRecord`; added separate `ExecutionExperienceRecord` and `execution_experience_records` | Both capabilities remain independently typed and persisted |
| Existing databases across schema split | Pre-0035 database could contain the collided execution shape | Migration `0035_split_execution_experience` detects/moves the execution-shaped data and restores routing-learning storage | Existing execution experience is preserved; routing learning regains its authoritative table |
| Donor public API | Import cycle `donor -> execution -> integration -> donor` broke otherwise valid tests | Lazy, type-safe public re-exports in `engine.donor.__init__` | Existing public import names remain available without eager cycle |
| Frontend governed mutation lifecycle | Unit fixtures accidentally invoked a real Fabric lifecycle through a fake engine | Tests inject the supported lifecycle seam | Production BEFORE/AFTER mutation lifecycle remains enabled |
| Blueprint E.5 data ownership | AST test treated ordinary payload words such as `capabilities` as exclusive table-name ownership | Guard now detects actual SQLAlchemy / SQL writes to foreign-owned authoritative tables | Real write ownership is enforced without renaming public payload fields |
| Migration recovery verification | Recovery test pinned historical head `0026` while repository head advanced | Test derives current Alembic head and predecessor from the migration graph | Future migrations cannot silently stale this recovery contract |
| Full migration reversibility | The first scratch `head -> base` proof exposed a 0035/0032 worker-session FK dependency | 0035 downgrade now preserves the canonical split at 0034; exact CI `head -> base -> head` succeeds without CASCADE | Migration history is reversible without recreating the obsolete schema collision |
| Fresh CI Project Truth | Integration ran against schema-only PostgreSQL although accepted owner EDR rows are authoritative runtime truth | CI now provisions `scripts.accept_owner_edrs` through `TruthService` before integration | Fresh environments receive the versioned accepted EDR set through the sole-writer path |
| Universal DDE Chat binary attachment upload | Shared `Uint8Array<ArrayBufferLike>` failed desktop DOM `fetch` typing | Transport makes an owned byte-for-byte `Uint8Array` copy before `fetch` | Wire bytes, content type, scope headers and idempotency identity are unchanged |
| DDE-only host isolation | Fresh shell lost exported service URLs | Recovered previously evidenced DDE-local configuration; both endpoints resolve to `127.0.0.1` | No Dial/shared service configuration was substituted |

## Verification already completed in this recovery tranche

- Persistent isolated DDE database: Alembic `0035`, matching code head.
- Focused lifecycle repair: `2/2` pass.
- Import-cycle / PostgreSQL regression modules: `9/9` pass after migration.
- Ownership + migration recovery focused verification: `5/5` pass.
- Full Python suite after recovery: `1489 passed, 6 skipped, 0 failed`.
- Contract rerun: `220 passed, 0 failed`.
- Ruff / formatting / mypy: green; mypy checked 551 source files.
- Extension shared tests: `77 passed, 0 failed`.
- Desktop TypeScript check: green.
- React TypeScript check and production Vite build: green.
- Exact CI migration cycle on a throwaway PostgreSQL database: `upgrade head -> downgrade base -> upgrade head` green.
- Authoritative accepted Project Truth bootstrap: EDR-0001..EDR-0017 provisioned through `TruthService`; fresh integration `5/5` pass.
- Final uninterrupted G1 process: exit code `0` with `=== G1 GREEN ===`.

## Non-silent residuals

The desktop dependency install reports 15 npm audit findings (1 moderate, 13 high, 1 critical). They pre-exist the byte-copy repair and remain explicit security/hardening work; they are not waived by this recovery.

The repository design lint currently reports the known DD206 baseline violations. They remain visible evidence and are not converted into a false pass.

## Continuation preservation additions

| Capability / invariant | Risk avoided | Continuation result |
| --- | --- | --- |
| CA-07 selected-design Try Live | Rebuilding an already-landed UI or marking a stub as complete | Existing persisted Direction cards were retained and strengthened with selected-artifact LIVE-byte and fresh DDE-068 verification proof |
| Explorer lock authority | Duplicating lock counts in React-local state | EX-16..EX-19 now consume per-kind counts from the existing `LockService.inventory()` projection |
| Screen Audit / QA authority | Creating a second QA truth store only to satisfy Explorer chrome | EX-20/EX-21 derive current issue counts from Screen Audit; EX-22 stays honestly unknown when accessibility is not evaluated |
| Sync/build provenance | Showing a plausible saved time or build string without backend evidence | TB-03 uses durable revision time; ST-06 now receives the installed DDE package version through the real Gateway snapshot |
| Screen Audit dogfood | Freezing tests to a remembered ledger count | Dogfood compares reconciliation counts directly with the matrix's derived statuses, preserving the no-invented-pass invariant as controls advance |

Latest complete gate after these additions: 1489 passed / 6 skipped, 220/220 contract rerun, 77/77 extension tests, desktop/UI TypeScript and Vite build green, and 61/61 Playwright visual tests. Current ledger: 6 VERIFIED / 61 BOUND / 7 TYPED_UNAVAILABLE / 25 UNBOUND.