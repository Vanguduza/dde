# EDR-0019 Amendment 1 — feature-gap closure and first runtime, evidence

Date: 2026-09-19
Authority: EDR-0019 Amendment 1 / AD-051
Base commit: `258cae6`
Proof database: PostgreSQL 16.13, Redis 6379 available

Every claim names the command that produced it.

## 1. Why there were gaps

A feature-level inventory of the source artifact, rather than of its twelve epic headings,
found **33 concrete named features**. The first tranche adopted 24, deliberately declined 2
(VAN `CommandAuthorityRecord` tables and Trading Core, both refused by the artifact's own
§29), and left **5 genuine gaps**.

Measured against the artifact directly:

```
graphify        0 hits      chatgpt         0 hits
graphrag        2 hits      deep research   0 hits
n8n            31 hits      vekl           30 hits
vati/vtil      16 hits      frontend design  1 hit
```

Two of the named-but-unadopted features — guided frontend design orchestration and the
VATI/VTIL borrowing model — are named without any specification, which is why their designs
here are owner-derived rather than transferred.

## 2. Gaps closed

| Gap | Contract | Enforcing check |
| --- | --- | --- |
| Discovery graph projection | `GraphTrustProjection` | anti-pattern cannot fill a positive slot; invalidated cannot stay retrievable |
| Model availability discovery | `ProviderModelAvailability` | catalogue presence carries no routing eligibility |
| Adaptive execution runner | `AdaptiveExecutionRun` | `FALLBACK_APPLIED` requires a checkpoint kind |
| Guided frontend design orchestration | `FrontendDesignOrchestrationRun` | `verification_satisfied` pinned false; `authority` is a single-value `ADVISORY` enum |
| VATI/VTIL knowledge borrowing | `KnowledgeBorrowGrant` | `lender_project_id <> project_id`; derived learning capped at `S7_DISCOVERY_ONLY` |

## 3. Migration 0042

5 tables, 18 foreign keys, 2 indexes, 15 RLS statements, extracted verbatim from generated
`schemas/sql/0001_stage1.sql`, guarded with the `to_regclass` convention `0040`/`0041` use.

| Path | Result |
| --- | --- |
| from base: `upgrade head` / `downgrade base` / `upgrade head` | exit 0 / 0 / 0 |
| **true `0041 → 0042`**, database built from commit `258cae6` | exit 0 |
| — tables created | **5 of 5** |
| — RLS enabled *and* forced | **5 of 5** |
| `downgrade 0041` / `upgrade head` | exit 0 / 0 |

The true upgrade was measured against a worktree of the previous commit, verified beforehand
to be at head `0041` with **0** gap tables present. Without that, a from-base build supplies
the tables through `0001` and the guard makes `0042` a no-op — which would have proved nothing.

## 4. New gates induced

Each row is a deliberately illegal insert the database refused, by check constraint rather
than by an incidental NOT NULL or FK error:

| Induced violation | Refused by |
| --- | --- |
| `ANTI_PATTERN` projection filling a positive slot | check |
| invalidated projection still marked retrievable | check |
| fallback applied with no checkpoint | check |
| frontend orchestration claiming verification | check |
| borrow grant from the same project | check |
| borrow grant laundering derived learning as first-party | check |

Five legal counterparts were accepted, including an anti-pattern projection that stays
retrievable without filling a positive slot, and a borrow grant whose derived learning is
capped at `S7_DISCOVERY_ONLY`.

## 5. Runtime landed

| Module | Tests |
| --- | --- |
| `engine/source/discovery/` (identity, policy, tables, repository, service) | 8 integration tests on real PostgreSQL |
| `engine/capabilities/gates.py`, `engine/recovery/postcondition.py`, `engine/missions/steering.py`, `engine/attention/scoring.py`, `engine/context/epistemics.py` | 36 decision-engine tests |
| `engine/research/` (coverage, packets, cursor) | 21 tests |

Identity normalisation was verified directly: four different GitHub views —
`/tree/main/workflows`, the bare repo, `.git`, and `/issues/42` — all collapse to
`github:zie619/n8n-workflows` and one candidate id, which is what makes independent
discoveries merge evidence instead of duplicating.

## 6. Invariants induced, not assumed

| Break introduced | Test that failed |
| --- | --- |
| a passing sandbox trial raises `source_trust` | `test_a_passing_trial_advances_lifecycle_but_never_raises_trust` |
| a generated column removed from the hand-written `external_effects` table | `test_external_effect_sqlalchemy_table_matches_the_generated_schema` |

In both cases exactly the intended test failed and nothing else, then the source was restored
and the suite returned to green.

## 7. A test that proved nothing, corrected

The first cross-project isolation test queried as the `dde` owner role. That role is a
superuser and bypasses RLS, so the test would have passed whether or not any policy existed —
the existing Chapter 13.9 suite warns about exactly this. It was rewritten to run through the
non-superuser `dde_rls_probe` role and now asserts only what it can prove: that another
project sees none of these rows.

Its unset-GUC case was dropped rather than papered over. On a pooled probe connection a
transaction-local `set_config` reverts to `''` rather than unset, which makes the RLS cast
fail for harness reasons unrelated to policy. That case is already covered for every stored
table by `test_rls_enforcement`, which enumerates the schema registry and therefore picked up
these tables automatically.

## 8. Repository-wide gates

| Gate | Result |
| --- | --- |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 1158 files already formatted |
| `mypy` | Success: no issues found in **659** source files |
| `generate_contracts --check` | exit 0 |
| `repository_governance verify-static` / `render-bug-ledger --check` | exit 0 / 0 |
| `generate_design_tokens --check` / `render_binding_matrix --check` | exit 0 / 0 |
| `pytest tests/unit tests/contract tests/recovery` | **1695 passed, 6 skipped, 0 failed** |
| `pytest tests/contract` + the three new suites | **317 passed** |

The 1695 figure is the run measured on a freshly migrated database: 1630 at base commit
`258cae6` plus the 65 new unit tests. That run was started before the last five contract
tests were written, so those were confirmed in the separate 317-test run above.

## 9. What this does **not** prove

No production call site invokes any engine landed here. Under `AGENTS.md` that is not
completion, and `IMPLEMENTATION_STATE.md` keeps the programme at `IMPLEMENTED_PARTIAL`.
Phase 8 (automation and browser runtimes), Phase 9 (Studio projections) and Phase 10
(DDE-083 adversarial certification) are not started, and Epic B's full fleet binding remains
blocked on DDE-076/077, which still do not exist in this repository.
