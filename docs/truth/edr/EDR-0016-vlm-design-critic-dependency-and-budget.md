# EDR-0016 — VLM design-critic dependency & budget: admitting the
# multimodal critic behind DDE-068's visual verification loop

> **Location note.** Per Chapter 3.6, an EDR is a row in the `edrs` table,
> written only by `engine/truth/`. Following the convention established in
> `EDR-0001`–`EDR-0014`, this file is a **markdown pre-image** of the eventual
> `edrs` row, filed as the proposal itself (AGENTS.md forbids editing
> `docs/truth/**` as a side effect). **This file is not itself an accepted
> EDR.** `status` is `proposed`; only a human decision via
> `scripts/accept_owner_edrs.py` can move it to `accepted`.

- **slug:** `EDR-0016`
- **status:** `proposed`
- **supersedes:** none
- **affected_requirement_slugs:** none filed yet
- **raised during:** Frontend Studio charter v3 sign-off (2026-08-24).
  Charter §6 sequencing requires this filed AT charter sign-off; DDE-068
  implementation may not start before acceptance (the EDR-0008 accept-first
  pattern).

## Context

DDE-068 (Visual Verification & Critique Loop) needs a multimodal-model
capability no existing repo toolchain provides: screenshot → rubric critique
scored against playbook §8 scorecards → bounded revise ≤3 cycles → residuals
escalate to human. The Phase-B render harness is already landed (EDR-0008's
Playwright job in `dde-studio.yml`), so the missing piece is exactly the
critic dependency and its budget envelope. AGENTS.md admits a new dependency/
model call only with licence, maintenance signal, cost ownership and why the
existing toolchain is insufficient — static lints (DD201–DD206) and string
fingerprints cannot judge composition, hierarchy or distinctiveness of
rendered pixels.

Interaction with containment posture: model credentials must follow the same
brokered path as every other capability (EDR-0011's general containment
remains deferred; nothing here widens worker-run egress — critique calls are
control-plane side-effecting steps like donor-search queries under EDR-0015).

## Decision (proposed)

Admit ONE VLM design-critic capability for DDE-068, bounded as follows — with
two items explicitly left to the deciding human before acceptance:

1. **Model choice — OPEN for human decision.** Candidates to evaluate,
   named generically: a frontier closed multimodal API model (strongest
   rubric fidelity; per-call cost; brokered short-lived credential),
   a smaller/cheaper closed multimodal tier (cost-controlled first-pass
   scoring), or a self-hostable open-weights VLM (no per-call vendor cost;
   GPU/ops burden). No prices are invented here; the deciding human sets the
   model(s) and the **cost ceiling number** (per-mission and per-revise-cycle
   budget, Chapter 16.4 accounting).
2. **Brokered credential path.** The critic runs behind the capability
   broker with short-lived minted credentials and a declared
   `side_effect_class`; screenshots leave the workspace only as request
   payloads to the admitted endpoint, never via any other egress.
3. **Rubric storage.** Rubric/scorecard text lives under `schemas/design/`
   versioned alongside the token SSOT discipline (Ch.3.1 drift gate); the
   compiled prompt pins rubric + playbook versions so verdicts are
   reproducible against named inputs.
4. **Critique retention policy.** Critiques are durable rank-9 evidence
   artifacts (Ch.2.2): retained with their VerificationRun/Evidence linkage,
   never auto-deleted while the screen they judged remains merged; retention
   window beyond that (and whether raw screenshots age out ahead of verdict
   rows) is recorded at acceptance time.
5. **Bounded revise ≤3 cycles, human escalation.** Each revise cycle consumes
   exactly one stored critique artifact; cycle count >3 blocks
   auto-progression and requires explicit human approval through the
   approvals surface (`prototype_pixel_signoff` vocabulary already exists).
   Every critique call and revise step carries an idempotency key and writes
   its Ch.12.4 journal row before retry; replaying a duplicated critique
   asserts one effect.
6. **Rank-9 forever, never auto-applied.** Critiques inform humans and the
   bounded loop but never modify rank ≤3 artifacts, never auto-approve
   themselves, never widen autonomy (charter §5 guardrail 7 verbatim).

### Open question folded in from charter v3 sign-off — silhouette corpus sourcing

The DDE-068 silhouette test compares rendered layout-shape fingerprints
against "a corpus of documented generic layouts" (playbook §10.3). Where that
corpus comes from needs a licence-clean decision at DDE-068 charter time:

- godly/land-book-class design galleries are **SOURCE_REFERENCE_ONLY** with
  **no APIs** — scraping them is out; they can inspire human curation only;
- options for the deciding human: (a) hand-curated generic-layout corpus
  transcribed from published design-teardown articles (with attribution),
  (b) an explicitly licensed dataset of layout annotations, (c)
  self-generated generic layouts seeded from the playbook §1.1 nevers
  catalog (fully licence-clean, provenance trivially internal).

This item rides EDR-0016 rather than a separate filing because both decide at
DDE-068 charter time and share the same acceptance gate.

## Consequences

- If adopted: DDE-068 starts from a working renderer plus an admitted,
  budget-bounded critic; every critique is durable rank-9 evidence with a
  reproducible rubric lineage; the corpus question has a decided, licence-
  clean answer before the silhouette gate exists.
- If rejected or left undecided: DDE-068 cannot start implementation; the
  Definition-of-Polished gates that depend on it (VLM rubric, silhouette
  distinctness) stay named deferrals, and existing-surface floors (DD201–
  DD206 + honesty tests) remain the merge bar.
