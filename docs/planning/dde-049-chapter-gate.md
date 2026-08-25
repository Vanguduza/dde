# DDE-049 chapter gate — database and backend capabilities

**Mission:** §18.3 S5 / `DDE-049` — database and backend capabilities.
**Charter:** blueprint `REV_2_0.md` §18.3 S5 line; Ch.9.8 portfolio
("backend/database"); Ch.11.2's `db_assertion` binding — which
`engine.verification.oracle` explicitly flagged as "still needs DDE-049".

**CI:** ruff check/format · mypy · 1015 passed / 2 skipped
(unit+contract+recovery, Postgres up) · `generate_contracts --check` ·
`generate_design_tokens --check` · design lints (within baseline budget) ·
dde-studio + desktop typecheck/tests — all green.

## What landed

- `capability.database` seeded descriptor: PURE_READ, T1, egress scoped
  to the datastore under test (`engine/capabilities/seed.py`).
- `engine.capabilities.database`: stdlib Protocol plus an in-process
  read-only SQL assertion runner (`InProcessDatabaseAsserter`) —
  short-lived engine per check, no vendor database tooling (Ch.9.6).
- Read-only by construction: single-statement validation, SELECT/WITH
  only, write/DDL keyword refusal before execution, and a query error is
  recorded as genuine FAILED evidence rather than raised.
- Verification surface: `db_assertion` added to `EXECUTABLE_KINDS`
  (`[datastore_url, assertion_sql...]` argv), executed through
  `run_check(..., database=...)` and the injected capability on the
  runner — Chapter 11.2's example binding
  (`sql/assertions/credit_limit_enforced.sql`) now has a real executor.
- Routing: `profile.database` declares repository/testing/database;
  no existing workload class requires the new capability, so routing
  behaviour for existing tasks is unchanged.

## Rule disposition

1. **Side-effect class declared** — PURE_READ at the descriptor; the
   asserter refuses mutation statements mechanically, not by convention.
2. **No vendor SDK in engine/** — the asserter uses SQLAlchemy Core text
   queries already used throughout the control plane; nothing new is
   imported beyond it.
3. **Lease before side effect** — verification's capability injection is
   the T1 seam; callers without an injected capability fail closed with
   POLICY_DENIED (same shape as browser/security/android).
4. **Credential discipline** — the datastore URL arrives per-binding from
   the oracle author; DDE control-plane credentials are never implied,
   and assertion output carries values, not connection material.
5. **Recovery** — a failing or erroring assertion is FAILED evidence on
   the CheckResult; nothing retries blind.

## Deferred (with proposed EDR)

- **Write-path backend operations** (migrations-as-capability, seeded
  data mutation against product datastores): deliberately not granted —
  ProductEnvironment lifecycle already owns seeding/migration through
  `engine.product_env`, and a second write path would violate the
  single-writer rule. Any future write-capable database capability needs
  an EDR naming its idempotency/reconciliation story (**EDR-0019**
  proposed).
- **Live OpenAPI/property-testing backends** (Appendix A candidates):
  out of charter scope here; they slot behind additional pure-read
  protocols when a mission needs them.

## Verdict

**PASS-WITH-EDR** — in-charter MUSTs enforced at named production call
sites; write authority deferred behind EDR-0019 rather than silently
absent. Auto-proceed to DDE-050 authorized under the standing order.
