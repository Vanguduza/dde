# EDR-0003 — Chapter 5.13 promotion gate: one of five gates implemented

> **ACCEPTED 2026-08-22 by explicit human project-owner decision.** The
> authoritative record is the accepted row in the Project Truth `edrs` table
> (`edr_id=01a028c4-a0ac-73a8-b0aa-f0133f2a5520`, owner project
> `9b6f1a58-e29a-4a35-a8e2-8e6c0f4b7d11`, written via
> `engine.truth.service.TruthService.propose_edr` + `accept_edr`). This file
> remains as readable documentation; where wording differs, the `edrs` row
> outranks it. Acceptance covers the design and deferrals **as documented** —
> implementing gates 2–5 stays gated on its own mission.

> **Location note.** Per Chapter 3.6, an EDR is a row in the `edrs` table,
> written only by `engine/truth/`. No such row exists yet. Following the
> convention established in `EDR-0001-subscription-based-worker-credentials.md`
> and `EDR-0002-semantic-retriever-default-gating.md`, this file is a
> **markdown pre-image** of the eventual `edrs` row, filed as the proposal
> itself (not a side effect of implementing DDE-031 — AGENTS.md forbids
> editing `docs/truth/**` as a side effect). **This file is not itself an
> accepted EDR.** `status` is `proposed`; only a human decision can move it
> to `accepted`, at which point the durable record belongs in `edrs`, and
> this file should be deleted or reduced to a pointer.

- **slug:** `EDR-0003` (provisional)
- **status:** `proposed`
- **supersedes:** none
- **affected_requirement_slugs:** none filed yet — should be linked to
  whatever requirement charters Chapter 5.13's promotion gates once it
  exists as a Project Truth row.
- **raised during:** implementation of DDE-031 (Chapter 5.13 eval corpus +
  promotion gate), the follow-on mission EDR-0002 scoped.

## Context

Chapter 5.13 names five promotion gates a new context policy must clear
against the current certified baseline, "all must hold":

1. Critical coverage — no regression on required categories.
2. Context-attributed failure rate — no regression.
3. Contradiction rate — no regression.
4. Task success on corpus — no regression, improvement preferred.
5. Token cost per verified success — reported, not a gate on its own.

DDE-031 implements the Chapter 5.13 corpus construction protocol in full
(real-mission sourcing via `MERGED` `IntegrationProposal`s, mechanically
derived ground truth, the draft → frozen human-review boundary, retire-
never-delete, and the 60-case/6-class/10-adversarial adequacy
precondition), plus **gate 1 only** (`critical_coverage`), computed by
running `ContextService.compile()` for the baseline and candidate policy
over every frozen case's real source `Task` and diffing the Chapter 5.8
coverage contract category-by-category.

Gates 2–5 are **not computed** by this mission. Each needs a mechanism
DDE-031's brief did not charter:

- **Context-attributed failure rate** (gate 2) needs Chapter 5.11's
  failure-attribution pipeline run against real worker executions of each
  eval case's task, under both the baseline and candidate context policy —
  i.e. a real `TaskAttempt`/`WorkerRun`/`VerificationRun` replay per case,
  not just a `compile()` call.
- **Contradiction rate** (gate 3) needs Chapter 5.6's conflict adjudication
  (`ContextConflict`, rank ≤ 6 contradiction detection) to actually fire
  across the corpus and be counted; nothing in the current retriever set
  reliably manufactures or detects rank ≤ 6 contradictions at eval-corpus
  scale.
- **Task success on corpus** (gate 4) needs the same real execution replay
  as gate 2, scored against each case's acceptance oracle.
- **Token cost per verified success** (gate 5) is denominated in *verified*
  successes, which does not exist without gates 2/4's execution loop.

## Decision (proposed)

- `PromotionGateRun.decision` is restricted to `INSUFFICIENT_CORPUS`,
  `FAIL`, or `PARTIAL_PASS_IMPLEMENTED_GATES_ONLY` — never a bare `PASS`.
  This is enforced in the wire contract (`schemas/objects/promotion_gate_run
  .json`'s `decision` enum), not only in a docstring, so no caller can
  construct a `PromotionGateRun` claiming full Chapter 5.13 promotion.
- `gate_results` always names its own `deferred_gates` list explicitly
  (`context_attributed_failure_rate`, `contradiction_rate`,
  `task_success_on_corpus`, `token_cost_per_verified_success`) so a reader
  of any single run can see what was and was not evaluated without cross-
  referencing this file.
- No production call site wires a `PARTIAL_PASS_IMPLEMENTED_GATES_ONLY`
  decision into flipping `ContextService`'s `semantic_retrieval_enabled`.
  That remains the manual, code-reviewed change EDR-0002 already
  describes, until a follow-on mission (tracked, provisionally, as
  DDE-032) implements gates 2–4's execution-replay mechanism and gate 5's
  reporting, and Chapter 5.13's "all must hold" can be evaluated for real.

## Consequences

- The Chapter 5.13 corpus itself (sourcing, ground truth, freeze,
  adequacy) is real production infrastructure today, independent of how
  many gates run over it — a later mission can add gates 2–5 without
  touching `engine.context.eval_corpus` or the `eval_cases` schema.
- Nobody can mistake a `PARTIAL_PASS_IMPLEMENTED_GATES_ONLY` run for
  Chapter 5.13 promotion clearance; the decision vocabulary and the
  `deferred_gates` field both say so at the data layer.
- `semantic_retrieval_enabled` stays `False` by default in
  `ContextService` (EDR-0002) until gates 2–5 exist and a real corpus
  (currently absent — no project has 60 frozen cases yet) actually clears
  all five.

## Open questions / risks

- Whether gates 2/4's execution replay should re-run each eval case's
  `TaskAttempt` from scratch per promotion evaluation (expensive, but
  faithful) or reuse the case's already-recorded verification outcome
  under the *baseline* policy and only re-execute under the *candidate*
  policy (cheaper, but assumes the baseline recording is still valid) —
  an EDR of its own once that mission is scoped.
- Whether `contradiction_rate` (gate 3) needs new adversarial retrieval
  fixtures purpose-built to manufacture rank ≤ 6 contradictions, since
  Stage 1's four retrievers rarely produce genuine authority-rank
  conflicts today.
