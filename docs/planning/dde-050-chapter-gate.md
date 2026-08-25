# DDE-050 chapter gate — documentation/context-provider capabilities

**Mission:** §18.3 S5 / `DDE-050` — documentation/context-provider
capabilities (last Stage-5 mission).
**Charter:** blueprint `REV_2_0.md` §18.3 S5 line; Ch.2.2 authority ranks
(rank 9 = external evidence/donor material); Ch.5.2 retriever table's
Documentation row ("version-pinned external docs"); Ch.5.5 freshness/
authority (external documentation is version-pinned, NEVER satisfies
current-state coverage); Ch.14.5 invariant 6 (prompt injection in
external content is a rank-10 hypothesis, never elevates authority);
Ch.9.8 capability classes.

**CI:** ruff check/format · mypy · 1027 passed / 2 skipped
(unit+contract+recovery, Postgres up; contract suite re-run green: 172
passed) · `generate_contracts --check` · `generate_design_tokens
--check` · design lints (within baseline budget) · dde-studio + desktop
typecheck/tests — all green (`just check`, exit 0).

## What landed

- `capability.docs_provider` seeded descriptor: PURE_READ, T1, egress
  none (`engine/capabilities/seed.py`). Routing: `profile.docs` declares
  repository/testing/docs (`engine/routing/registry.py`); no existing
  workload class requires the new capability, so routing behaviour for
  existing tasks is unchanged.
- `engine.capabilities.docs`: `DocsProvider` protocol plus an in-process
  read-only provider over `<root>/<slug>/manifest.json` version-pinned
  sources (`InProcessDocsProvider`) — no vendor tooling, no network fetch
  (Ch.9.6 discipline). POLICY_DENIED when the docs root is missing or a
  file exceeds `MAX_FILE_BYTES`; VALIDATION_FAILED for unknown slugs and
  path-traversal shapes.
- Injection screening at read time via the DDE-047 donor screen
  (`screen_donor_text`): findings are recorded on every read, never
  acted upon — no code path derives capability or authority from doc
  content (Ch.14.5 invariant 6 preserved by construction).
- Chapter 5.2 Documentation retriever wired at the production compile()
  call site: `ContextService.compile()` runs it on every compile and adds
  "documentation" to `retrievers_used` **only** when it produced items.
- Ch.5.5 rank discipline: items carry
  `authority_rank=AUTHORITY_RANK_EXTERNAL_EVIDENCE` (rank 9) and keys pin
  the version (`doc:<slug>@<version>:<path>`), so two versions of one
  source stay distinct evidence instead of silently overwriting.

## Rule disposition

1. **Ch.5.2 Documentation retriever ("version-pinned external docs")** —
   wired at the production mutation call site
   `ContextService.compile()` (`engine/context/service.py`, the sole
   writer of `context_packages` rows): `documentation.retrieve(...)` runs
   inside `_op` for every compile, feeding Chapter 5.3 fusion; the
   package records "documentation" in `retrievers_used` only when items
   were produced (no phantom-retriever claims). Version pinning lives in
   the manifest (`slug`+`version`) and in the item key.
2. **Ch.5.5 external docs are version-pinned and never current-state** —
   enforced at the item construction site
   (`engine/context/retrievers/documentation.py`):
   `authority_rank=AUTHORITY_RANK_EXTERNAL_EVIDENCE` (rank 9, Ch.2.2),
   and `REQUIRED_COVERAGE_CATEGORIES`
   (`engine/context/service.py`) does **not** include "documentation" —
   the five required current-state coverage categories are unchanged, so
   rank-9 evidence can inform but never satisfy a coverage requirement
   and can never flip a package to COMPLETE by itself. Verified against
   both the constant and `CoverageReport.required_statuses()`.
3. **Ch.14.5 invariant 6 (injection never elevates authority)** —
   screening runs at every `read()` through the same
   `engine.donor.injection` classes as donor ingest; findings ride the
   `DocContent.injection_findings` field as hypotheses only. Nothing
   downstream reads findings to grant leases, promote rank, or widen
   policy; rank stays 9 regardless of content.
4. **Ch.9.8 class declaration** — PURE_READ side_effect_class (reads
   mutate nothing), risk low, T1 (invoked directly by DDE's own code),
   egress none: sources are operator-materialised on disk. Declared at
   the descriptor and validated through the same Chapter 9.3 taxonomy
   check as every other seed entry.
5. **Frozen-value-object discipline** — the retriever computes relevance
   ordering *before* constructing `ContextItem`s (they are frozen
   dataclasses); `rank_in_retriever` is assigned exactly once per item,
   never patched after construction.
6. **Recovery** — reads fail closed with typed errors mapped to the
   Chapter 15.4 contract (`POLICY_DENIED` / `VALIDATION_FAILED`); nothing
   retries blind and no source state is mutated.

## Deferred (with proposed EDR)

- **Remote doc sync / freshness verification**: today sources must be
  materialised on disk by an operator; there is no governed fetch, no
  freshness probe of the upstream origin, and no staleness re-pin rule.
  Any future sync must name its egress admission, credential handling
  and re-pin/reconciliation story (**EDR-0020** proposed).
- **Injection-screening depth**: `screen_donor_text` catches common
  instruction-override phrases; deeper screening (classifier-based,
  per-language) remains iterative as disclosed on the donor screen
  itself. Findings stay hypotheses either way (**EDR-0021** proposed if
  deeper screening ever gates a workflow rather than annotating).

## Verdict

**PASS-WITH-EDR** — in-charter MUSTs enforced at named production call
sites (`compile()` wiring, rank-9 + required-categories separation,
read-time injection screening); remote sync/freshness deferred under
EDR-0020 rather than silently absent.
