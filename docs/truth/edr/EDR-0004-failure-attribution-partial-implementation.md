# EDR-0004 — Chapter 5.11 failure attribution: two of three rules, no model fallback, routing exclusion not yet consumed

> **Location note.** Per Chapter 3.6, an EDR is a row in the `edrs` table,
> written only by `engine/truth/`. No such row exists yet. Following the
> convention established in `EDR-0001-subscription-based-worker-credentials.md`,
> `EDR-0002-semantic-retriever-default-gating.md` and
> `EDR-0003-promotion-gate-partial-implementation.md`, this file is a
> **markdown pre-image** of the eventual `edrs` row, filed as the proposal
> itself (not a side effect of implementing DDE-034 — AGENTS.md forbids
> editing `docs/truth/**` as a side effect). **This file is not itself an
> accepted EDR.** `status` is `proposed`; only a human decision can move it
> to `accepted`, at which point the durable record belongs in `edrs`, and
> this file should be deleted or reduced to a pointer.

- **slug:** `EDR-0004` (provisional)
- **status:** `proposed`
- **supersedes:** none
- **affected_requirement_slugs:** none filed yet — should be linked to
  whatever requirement charters Chapter 5.11's failure attribution engine
  once it exists as a Project Truth row.
- **raised during:** implementation of DDE-034 (Chapter 5.11 failure
  attribution engine), gate-reviewed independently after DDE-033
  (Chapter 5.10 knowledge graph, commit `208c64c`) was found PASS on
  substance.

## Context

Chapter 5.11 states: "Attribution is produced by a deterministic rule set
first (was a required category `partial`? did the worker request context
that existed but was not supplied? did it edit outside the supplied
scope?) and only falls back to a model judgment when the rules are
inconclusive." It also names the two consumers of an attribution outcome:
Chapter 5.13's promotion gate 2 (`context_attributed_failure_rate`, still
open per `EDR-0003`) and Chapter 6.8's routing-learning exclusion filter
("a failure attributed to context must not teach the router that a worker
is weak").

DDE-034 implements a real production writer, `engine.attribution`, wired
into the one real mutation call site the chapter's opening sentence names
("verification and recovery record..."): `engine.verification.runner.
VerificationRunnerService.run()`'s `FAILED` branch, in the same
transaction as the `FAILED` `VerificationRun`/`TaskAttempt` rows. Every
`FailureAttribution` row is genuinely idempotent on `verification_run_id`
(a real `UNIQUE` constraint plus an atomic `INSERT ... ON CONFLICT DO
NOTHING RETURNING`, not a check-then-insert).

Three gaps are deliberately left open, disclosed in `rule_reasons` on
every persisted row and in `engine.attribution`'s module docstrings, not
silently claimed as done:

1. **`context_request_denied` rule not evaluated.** Chapter 5.12's
   just-in-time expansion (`ContextRequest`/`ContextResponse`) has no
   writer anywhere in this codebase yet, so "did the worker request
   context that existed but was not supplied?" cannot be checked for
   real. Every attribution names this gap explicitly
   (`CONTEXT_REQUEST_RULE_DEFERRED`).
2. **No model-judgment fallback.** Chapter 5.11's escape hatch for
   rule-inconclusive cases is not implemented — the same no-model-call
   constraint `engine.context.critic`/`engine.context.conflict` (DDE-031)
   already hold to for Stage 1 core control-plane code. An inconclusive
   rule verdict is persisted honestly as `outcome=inconclusive`,
   `eligible_for_promotion_gating=False`, never silently upgraded.
3. **Chapter 6.8's routing-learning exclusion filter has no consumer.**
   `FailureAttribution.excluded_from_routing_learning` is computed and
   persisted for real today, but nothing reads it yet — `ExperienceRecord`
   eligibility filtering (`DDE-057`, Stage 7) does not exist. This is a
   real, working, independently-tested field a future mission should
   filter on, not a placeholder.

A fourth, narrower point: the **scope-overreach rule's causal
disambiguation is a Stage 1 approximation**. When no coverage category is
partial/missing but the worker edited outside `Task.expected_write_scope`,
this mission attributes the failure *away* from context (a worker/
competence signal). A real model judgment might sometimes attribute such
a case to context after all (the worker may have overreached *because* it
lacked the context to know the correct scope) — this codebase cannot make
that causal call without a model call it deliberately does not make, so
the deterministic rule takes the cheaper, disclosed simplification.

## Decision (proposed)

- `FailureAttribution.method` is restricted to `rule_based` or
  `model_judgment` at the schema level; no writer in this codebase
  constructs a `model_judgment` row, so every persisted row today is
  honestly `rule_based`.
- `eligible_for_promotion_gating` is `False` whenever `outcome ==
  "inconclusive"` — enforced in `engine.attribution.rules`, not only
  described in a docstring — so `EDR-0003`'s still-open gate 2
  (`context_attributed_failure_rate`) cannot be fed a definite yes/no it
  was never actually resolved to have.
- No production call site reads `excluded_from_routing_learning` to
  filter training data yet; that remains for the mission that implements
  Chapter 6.8's `ExperienceRecord` eligibility filtering.
- `rule_reasons` always names the `context_request_denied` gap explicitly
  on every row, so a reader of one attribution never has to
  cross-reference this file to know it was not evaluated.

## Consequences

- Chapters 5.9 (Context Critic) and 5.13 (promotion gate 2) — both of
  which DDE-031/DDE-032 already flagged as depending on Chapter 5.11 not
  existing — now have a real, if partial, attribution source to consume
  instead of a placeholder parameter/deferred-gates list. Neither is
  rewired to consume it by this mission; that is separate follow-on work,
  named here rather than silently assumed.
- The `failure_attributions` table, its idempotency key, and its real
  production call site are durable infrastructure today independent of
  how many of the three named rules run over it — a later mission can add
  the `context_request_denied` rule (once Chapter 5.12 exists) or a real
  model-judgment fallback without touching the schema or the call site.

## Open questions / risks

- Whether the scope-overreach rule's precedence choice (coverage-partial
  always wins over scope-overreach) should instead consider both
  signals jointly, or whether that joint reasoning is exactly the kind of
  case Chapter 5.11 intends the model-judgment fallback to resolve.
- Whether `context_attributed_failure_rate` (Chapter 5.13 gate 2) should
  treat `inconclusive` attributions as regressions, exclusions, or a
  separate reported-not-gating bucket once a real eval-corpus replay
  (`EDR-0003`) starts calling this engine per case.
