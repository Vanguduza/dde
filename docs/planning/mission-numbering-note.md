# Mission numbering correction — real DDE-031 vs. the commit labelled DDE-031

**Status:** factual correction record, not an EDR. No Project Truth row is
affected; this file exists only because `AGENTS.md` forbids editing
`docs/truth/**` as a side effect of implementing a task, and a plain
mislabelling of a *mission number* in a commit message is not itself a
Project Truth change — it needs a place to be recorded plainly, and this is
that place, following the same "no rewriting accepted history" discipline
`EDR-0003` already uses for a related, adjacent scoping error.

## The defect

Commit `4369c15` was authored with the message *"DDE-031: Chapter 5.13 eval
corpus + promotion gate (partial)"*. That work — `engine/context/eval_corpus.py`,
`engine/context/promotion.py`, the `eval_cases`/`promotion_gate_runs` schema
and migration `0003` — was independently gate-reviewed and confirmed
**PASS-WITH-EDR** on its substance (see `docs/truth/edr/EDR-0003-promotion-
gate-partial-implementation.md`, which itself already flags the commit's
mission number as "provisional").

Per `docs/blueprint/REV_2_0.md` §18.3's own roadmap, **Chapter 5.13's eval
corpus and promotion gates are chartered as `DDE-032`, not `DDE-031`.** The
commit message mislabels its actual blueprint-chartered scope.

The real `DDE-031` — **Chapter 5.6 conflict adjudication + Chapter 5.9
Context Critic** — was skipped entirely by the autonomous chain and had
never been implemented anywhere in this codebase before this mission
(confirmed at the time: no `ContextConflict`, `CONFLICTED` status, or
Context Critic mechanism existed in `ContextService`).

## What this mission does about it

- **`4369c15` is not rewritten.** No rebase, amend, or force-push. Its
  content is real, gate-reviewed, chartered work — it is simply chartered
  as `DDE-032`, not `DDE-031`, and its commit message is now permanently
  wrong about that one label. That is a historical fact to record, not a
  defect to erase.
- **This mission implements the real, correctly-numbered `DDE-031`** —
  Chapter 5.6 conflict adjudication (`engine/context/conflict.py`,
  `ContextConflict`, the `CONFLICTED` package status) and Chapter 5.9's
  Context Critic (`engine/context/critic.py`, `ContextCriticFinding`) — and
  is committed separately, with a commit message that names the correct
  chapter/number pairing.
- Anyone auditing mission history should read `4369c15`'s "DDE-031" label
  as `DDE-032`'s actual scope, and read this mission's own commit as the
  real `DDE-031`.

## Interaction with `EDR-0003`'s deferred `contradiction_rate` gate

`EDR-0003` names `contradiction_rate` (Chapter 5.13 gate 3) as **not
computed**, specifically because, at the time it was filed, *"nothing in
the current retriever set reliably manufactures or detects rank <= 6
contradictions at eval-corpus scale"* — i.e. gate 3 was blocked on Chapter
5.6 not existing yet.

This mission's Chapter 5.6 implementation (`engine.context.conflict.
detect_conflicts`) is a **real, structural, deterministic** contradiction
detector — not a semantic one — over two rules:

1. `overlapping_accepted_edrs` — two independently accepted EDRs (rank 4)
   name the same requirement slug in `affected_requirement_slugs` without
   either superseding the other.
2. `superseded_item_still_authoritative` — a resolved Requirement/EDR's
   `supersedes_id` names another item also resolved into the same package.

This **partially** unblocks `EDR-0003`'s gate 3, but does not fully close
it:

- It gives `engine.context.promotion.PromotionGateService` a real mechanism
  it could call per eval case to count genuine rank<=6 contradictions,
  which did not exist when `EDR-0003` was filed.
- It does **not** replay eval-corpus cases through this detector, wire a
  `contradiction_rate` computation into `PromotionGateService.evaluate`, or
  touch `gate_results`/`deferred_gates`/the `decision` vocabulary in
  `schemas/objects/promotion_gate_run.json` — that wiring is explicitly out
  of this mission's chartered scope (Chapter 5.6/5.9 only), and is left
  undone here on purpose rather than added as an unreviewed extra.
- It only detects the two **structural** contradiction shapes named above.
  `EDR-0003`'s gate 3 language ("rank <= 6 contradiction detection... at
  eval-corpus scale") does not distinguish structural from semantic
  contradictions; a future mission scoping the `contradiction_rate` gate
  should decide explicitly whether this structural subset is an acceptable
  gate 3 definition, or whether genuine semantic contradiction detection
  (which would need a model call this mission deliberately does not make —
  see `engine/context/conflict.py`'s module docstring) is required first.

**Recommendation, not a decision:** `EDR-0003` should be revised (by a
human, through `engine.truth`, once it exists as a real accepted-or-
proposed row) to note that Chapter 5.6 now has a real, if partial,
contradiction-detection mechanism available for gate 3 to call — but gate 3
itself remains unimplemented in `PromotionGateService` until a follow-on
mission explicitly scopes that wiring and decides the structural-vs-
semantic question above. This mission does not make that revision itself
(`AGENTS.md` forbids editing `docs/truth/**`, and `EDR-0003` is written as a
pre-image of a `docs/truth/edr` row); it only records the finding here for
whoever scopes that follow-on mission.
