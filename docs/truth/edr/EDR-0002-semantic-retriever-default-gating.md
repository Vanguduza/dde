# EDR-0002 — Semantic retriever: lexical stand-in embedding, gated off by default

> **Location note.** Per Chapter 3.6, an EDR is a row in the `edrs` table,
> written only by `engine/truth/`. No such row exists yet. Following the
> convention established in `EDR-0001-subscription-based-worker-credentials.md`,
> this file is a **markdown pre-image** of the eventual `edrs` row, filed as
> the proposal itself (not a side effect of implementing DDE-030/031 — AGENTS.md
> forbids editing `docs/truth/**` as a side effect). **This file is not itself
> an accepted EDR.** `status` is `proposed`; only a human decision can move it
> to `accepted`, at which point the durable record belongs in `edrs`, and this
> file should be deleted or reduced to a pointer.

- **slug:** `EDR-0002` (provisional)
- **status:** `proposed`
- **supersedes:** none
- **affected_requirement_slugs:** none filed yet — should be linked to whatever
  requirement charters Chapter 5.2's semantic retriever and Chapter 5.13's
  eval-corpus promotion gate once those exist as Project Truth rows.
- **raised during:** independent chapter-gate review of DDE-030 (semantic
  retriever + index lifecycle + versioned embeddings, commit `9dedcfe`)

## Context

DDE-030 implemented the Chapter 5.4 semantic index lifecycle (build,
incremental update/invalidation, embedding-model versioning with two
versions coexisting, staleness detection, tombstone-on-delete) and a
semantic retriever (Chapter 5.2) over it. Two blueprint constraints are in
tension with what was shipped, and neither was filed as an EDR at commit
time — they were only flagged in code docstrings, which the mission-chapter-
gate rule treats as a claim requiring independent verification, not a
substitute for a Project Truth record:

1. **Chapter 5.2 (line ~975): "Semantic retrieval arrives in Stage 3 and
   must demonstrate uplift on the eval corpus (§5.10) against a
   lexical+structural baseline before it is enabled by default."**
   DDE-030's original commit wired the semantic retriever into
   `ContextService.compile()` unconditionally: whenever a
   `ContextIndexService` had ever built an index for a project, `compile()`
   consulted it, ran the semantic retriever, and included its results in
   fusion by default — with no eval corpus, no uplift measurement, and no
   opt-in gate. This is a real, undisclosed divergence from an explicit
   blueprint MUST-equivalent rule, not merely a simplification: it silently
   turns on the most expensive, least debuggable retriever by default with
   zero evidence it doesn't regress coverage or contradiction rate. Chapter
   5.13's promotion gates (critical coverage, context-attributed failure
   rate, contradiction rate — "no regression against the current certified
   baseline") do not exist yet, and no eval corpus (Chapter 5.13, minimum 60
   cases) exists to run them against.

   **Fix applied as part of this gate review (not deferred):**
   `ContextService.__init__` now takes `semantic_retrieval_enabled: bool =
   False`. `compile()` only consults the index / runs the semantic
   retriever / applies the Chapter 5.4 staleness gate when a caller
   explicitly opts in. An index existing is no longer sufficient to enable
   semantic retrieval. This makes the "not enabled by default" half of the
   Chapter 5.2 rule true in the production call site, not just in a
   docstring.

2. **The embedding model itself.** `engine/context/embeddings.py` supplies a
   deterministic hashing-trick bag-of-tokens vector, not a transformer/
   semantic embedding. This was flagged in the module's own docstring at
   commit time. Cosine similarity over it surfaces lexical overlap, not deep
   semantic paraphrase — closer to a second lexical-ish signal than the
   Chapter 5.2 "Semantic | pgvector over chunk embeddings" retriever the
   blueprint describes. This is a legitimate zero-new-dependency stand-in
   (Chapter 9.6) but is not the retriever Chapter 5.13's uplift eval is
   meant to certify.

## Decision (proposed)

- Semantic retrieval stays implemented and testable (all four Chapter 5.4
  lifecycle operations, the retriever itself, the staleness gate) but
  **disabled by default in the only production call site** (`compile()`)
  until a follow-on mission (tracked as DDE-031) builds the Chapter 5.13
  eval corpus and promotion gate and flips `semantic_retrieval_enabled` on
  through that gate — not through a constructor default.
- The hashing-trick embedding remains the model until a real embedding
  model + pgvector dependency decision is made (Chapter 9.6 licence/
  maintenance review); `EMBEDDING_MODEL_VERSION` bumps and re-indexes via
  the existing `change_embedding_model`/`activate_index` lifecycle when
  that happens, so no schema change is needed later.

## Consequences

- No project currently in Stage 1 gets semantic results injected into a
  `ContextPackage` without an explicit, code-reviewed opt-in — closing the
  undisclosed-divergence gap this EDR exists to record.
- DDE-031 has a concrete, blueprint-anchored deliverable: Chapter 5.13's
  eval corpus + promotion gate, which is also the mechanism that should
  eventually flip `semantic_retrieval_enabled` on for real, evidence-backed
  reasons instead of a hand-set flag.
- Until DDE-031 lands, `retrievers_used` for every `ContextPackage` stays
  `(explicit, authority, lexical, structural)`, matching the Stage 1 set
  Chapter 5.2's table already prescribes.

## Open questions / risks

- Whether `semantic_retrieval_enabled` should live as a constructor flag
  (current, minimal shape) or as a first-class `context_policy` row once
  that object exists (Chapter 5.3 already anticipates `context_policy` for
  fusion weights) — likely the latter once Chapter 6/13 policy machinery
  exists, per the `engine/context/fusion.py` divergence note making the same
  observation about RRF weights.
- Whether the hashing-trick embedding should be replaced before or after
  Chapter 5.13's eval corpus exists — measuring uplift over a stand-in
  lexical vector may not carry over to a real embedding model, so this EDR
  should be revisited once a real model is chosen.
