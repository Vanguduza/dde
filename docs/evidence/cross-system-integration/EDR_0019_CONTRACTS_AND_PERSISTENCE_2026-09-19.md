# EDR-0019 cross-system operational intelligence — contract and persistence evidence

Date: 2026-09-19
Authority: EDR-0019 / AD-051
Base head: `042c353d8f3a7448d36e37ed78fda3632d98b6c6` (`feat/vekl-automation-corpus-runtime-20260916` reconciled)
Proof database: PostgreSQL 16.13, with Redis 6379 available for the suite

This artifact records what was **measured**, not what was intended. Each claim names the
command that produced it so a reader who does not trust this document can re-derive it.

## 1. Phase 0 — base reconciliation

```
git rev-list --left-right --count origin/main...origin/feat/vekl-automation-corpus-runtime-20260916
0	42
```

0 behind, 42 ahead: a clean successor to `main` that owns migration `0040`
(`down_revision = "0039"`). Building on `main` would have produced a second Alembic head at
`0039` and a parallel Source Intelligence surface.

## 2. A measurement error, found and corrected

The first reversibility runs were written as:

```bash
alembic downgrade base 2>&1 | tail -3; echo "DOWN_EXIT=$?"
```

`$?` after a pipeline is **`tail`'s** exit status, not alembic's. Those runs reported
`DOWN_EXIT=0` / `UP_EXIT=0` unconditionally and would have reported success even had every
migration failed. The instrument was measuring the wrong process.

Re-run without the pipeline, the same commands exposed a real defect (§4). Every migration
result below was produced by invoking alembic directly and capturing its own exit code.

## 3. Phase 1 — contracts

```
uv run python -m scripts.generate_contracts          # exit 0
uv run python -m scripts.generate_contracts --check  # exit 0
```

Generated DDL delta, derived from the diff rather than recalled:

```
git diff schemas/sql/0001_stage1.sql | grep -c "^+CREATE TABLE"     -> 29
git diff schemas/sql/0001_stage1.sql | grep -c "^-CREATE TABLE"     -> 0
git show HEAD:schemas/sql/0001_stage1.sql | grep -c "^CREATE TABLE" -> 145
grep -c "^CREATE TABLE" schemas/sql/0001_stage1.sql                 -> 174
```

29 tables added, 0 removed, 0 modified. The `external_effect` change is additive: three
nullable columns plus one check constraint, with the `status` enum byte-identical to before.

## 4. The defect the correct measurement exposed

Migration `0001` replays the **generated** `schemas/sql/0001_stage1.sql` in full. Because the
generator rewrites that file to contain every table, adding a schema means `0001` already
creates it. A migration that then creates the same table again double-creates on any database
built from base.

The first version of `0041` did exactly that. It appeared to pass only because the broken
exit-code capture hid the failure, and because the database it was first applied to had been
built from an *older* `stage1` that predated the new tables.

```
DuplicateTableError: relation "discovery_candidates" already exists
```

Migration `0040` already solved this: it probes `to_regclass` for its tables, skips creation
when all are present, and raises on a partial schema. `0041` now follows the same convention.

A second defect surfaced from the same correction: on a from-base build the postcondition
check constraint is created **inline and unnamed** by `stage1`, so the downgrade's named
`DROP CONSTRAINT` failed. The teardown is now `IF EXISTS` on all four statements, and dropping
the columns removes whichever constraint shape references them.

A third defect was caught only by running the whole unit suite against the baseline and
against this branch through the same instrument. `engine/recovery/tables.py` declares the
`external_effects` SQLAlchemy table **by hand**, while the contract is generated. Adding the
postcondition columns to the schema without adding them there made every ExternalEffect
insert fail:

```
sqlalchemy.exc.CompileError: Unconsumed column names:
postcondition_policy, postcondition_verified_at, postcondition_state
```

Because effects are journaled by many subsystems, one missing table definition cascaded into
**82 unit failures** across external effects, verification, workers, checkpoints, telemetry,
the integration queue, diff gates, learning and the eval corpus. Measured through the same
instrument, `pytest tests/unit tests/recovery` on a freshly migrated database with Redis up:

| Tree | Result |
| --- | --- |
| pristine baseline (no EDR-0019 changes) | `1383 passed, 6 skipped` |
| this branch, before the fix | `82 failed, 1301 passed, 6 skipped, 1 error` |
| this branch, after the fix | `1383 passed, 6 skipped` |

1301 + 82 = 1383, so exactly the passing set regressed and no test was added or lost; after
declaring the three columns on the table the branch is at **exact parity with baseline**.

All three defects are covered by regression tests (§7).

## 5. Phase 2 — persistence, both build paths

`migrations/versions/0041_cross_system_operational_intelligence.py`: 29 `CREATE TABLE`,
103 foreign keys, 5 indexes, 87 row-level-security statements (29 × ENABLE/FORCE/POLICY), all
extracted verbatim from generated `schemas/sql/0001_stage1.sql`.

**Path A — database built from base** (tables arrive via `0001`; `0041` must skip):

| Step | Result |
| --- | --- |
| `upgrade head` from empty | exit 0 |
| `downgrade base` | exit 0 |
| `upgrade head` | exit 0 |
| `downgrade 0040` | exit 0 |
| `upgrade head` | exit 0 |

**Path B — real upgrade from an existing `0040` database** built from the pristine branch, so
the new tables and columns are genuinely absent beforehand (verified: head `0040`,
`discovery_candidates` absent, 0 postcondition columns):

| Step | Result |
| --- | --- |
| `upgrade head` (must create) | exit 0 |
| new tables created | **29 of 29** |
| RLS enabled **and forced** on them | **29 of 29** |
| postcondition columns added | **3 of 3** |
| `downgrade 0040` (must drop) | exit 0, `discovery_candidates` gone, 0 postcondition columns |
| `upgrade head` again | exit 0 |

**Partial-schema guard induced.** One table was dropped from a `0041` database and the version
reset to `0040`. The upgrade refused, naming the exact gap:

```
RuntimeError: partial cross-system operational intelligence schema detected before
migration 0041; missing tables: steering_impacts
```

## 6. Evidence gates were induced, not assumed

A gate whose failure has never been induced is not known to work. Each row is a deliberately
illegal insert the database **refused**, and in every case the refusal came from the intended
*check* constraint rather than an incidental NOT NULL or foreign-key error:

| Induced violation | Refused by |
| --- | --- |
| environment certification green without evidence | check |
| capability gate `READY` without an evidence pointer | check |
| provider readiness `READY` without fresh evidence | check |
| effect postcondition `VERIFIED` without a timestamp | check |
| automation grant consuming more than `max_uses` | check |
| browser session with a non-isolated profile | check |
| browser session permitting cookie export | check |
| `INFO` attention candidate bypassing the budget | check |
| read-only steer taking a barrier | check |
| `NO_AUTHORITY` steer that is not read-only | check |
| `MODEL_INFERENCE` fact persisted as promoted | check |
| automation run `VERIFIED` without callback/journal/verifier | check |
| release `PRODUCTION_QUALIFIED` without security + sandbox evidence | check |

**Checked in the opposite direction.** A constraint that refuses everything proves nothing, so
the 12 legal counterparts were also attempted: 8 accepted outright, and the other 4 rejected
only by missing foreign-key parents in the harness. Re-run with FK triggers isolated inside a
rolled-back transaction, all four legal rows were accepted. **Zero legal rows were blocked by
a check constraint.** Both runs were repeated after the migration was rewritten, on a database
rebuilt from base, with identical results.

## 7. Contract tests

`tests/contract/test_cross_system_integration_schema_objects.py` — 24 tests, all passing.

Five invariants were deliberately broken and each was caught by its own test before the source
was restored:

| Break introduced | Test that failed |
| --- | --- |
| second trust vocabulary on `discovery_candidate` | `test_discovery_reuses_the_single_canonical_source_trust_vocabulary` |
| `STEERING_HELD` appended to `tasks.status` | `test_task_status_is_not_widened_by_steering` |
| `external_effects.status` enum replaced | `test_external_effect_status_semantics_are_unchanged` |
| postcondition teardown made non-idempotent | `test_migration_0041_downgrade_is_idempotent_across_both_build_paths` |
| (guard presence) | `test_migration_0041_guards_against_stage1_double_create` |
| a generated column removed from the hand-written table | `test_external_effect_sqlalchemy_table_matches_the_generated_schema` |

## 8. Repository-wide gates

| Gate | Result |
| --- | --- |
| `ruff check .` | All checks passed |
| `ruff format --check .` | all files formatted |
| `mypy` | Success: no issues found in 638 source files |
| `repository_governance verify-static` | exit 0 |
| `repository_governance render-bug-ledger --check` | exit 0 |
| `generate_design_tokens --check` | exit 0 |
| `render_binding_matrix --check` | exit 0 |
| `design_lints --baseline` | exit 0 (70 pre-existing violations in untouched `interfaces/dde-studio`) |
| `pytest tests/contract` | 247 passed |
| `pytest tests/unit tests/recovery` | 1383 passed, 6 skipped — exact parity with baseline |

`just studio-check` was not run: it performs four `npm ci` installs and no frontend file is
touched by this change.

## 9. What this evidence does **not** prove

It does not prove any runtime behaviour. There is no service, no production call site and no
operator surface for any of the twelve epics. Under `AGENTS.md` this tranche is
`IMPLEMENTED_PARTIAL` and must not be cited as delivering steering, discovery, research,
readiness, verified actions, automation, browser capability, attention or certification.

It also does not prove the source artifact's Epic B integration, which is blocked: the fleet
contracts it names (`HarnessInstallation`, `HarnessRuntimeCapabilities`,
`ModelControlCapabilities`, `WorkerConfiguration`, `WorkerProfileCertification`,
`TaskExecutionDescriptor`, `ExecutionStrategy`) do not exist in this repository, and neither do
`ChangePacket` or `WorkspaceLease`. That was established by direct search, not assumed.
