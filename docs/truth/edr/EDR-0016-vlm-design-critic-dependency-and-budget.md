# EDR-0016 — VLM design-critic dependency & budget: admitting the
# multimodal critic behind DDE-068's visual verification loop

> **ACCEPTED 2026-08-24 by explicit human project-owner standing directive
> ("accept and fix all EDRs according to best recommended solutions").** The
> authoritative record is the accepted row in the Project Truth `edrs` table
> (`edr_id=01a0341c-7119-7b38-9ddf-e6e73f2e1a88`, owner project
> `9b6f1a58-e29a-4a35-a8e2-8e6c0f4b7d11`, written via
> `engine.truth.service.TruthService.propose_edr` + `accept_edr`). This file
> remains as readable documentation; where wording differs, the `edrs` row
> outranks it. Both items left open below (model choice + cost ceiling, and
> silhouette corpus sourcing) are answered by decided defaults in the
> ACCEPTANCE section at the end of this file; defaults are amendable by
> future EDR. DDE-068 implementation may start.

> **Location note.** Per Chapter 3.6, an EDR is a row in the `edrs` table,
> written only by `engine/truth/`. Following the convention established in
> `EDR-0001`–`EDR-0014`, this file was filed as a **markdown pre-image** of
> the eventual `edrs` row (AGENTS.md forbids editing `docs/truth/**` as a
> side effect). The durable row now exists (see the acceptance note above);
> this file stays as the readable pre-image of that row.

- **slug:** `EDR-0016`
- **status:** `accepted (2026-08-24)`
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
   approvals surface. Note: `prototype_pixel_signoff` is NOT yet in
   `APPROVAL_TYPES` (`engine/governance/types.py` verified 2026-08-24);
   it must be added through the ordinary contract path or an existing
   type designated before DDE-068's sign-off queue can be typed (GUI-spec
   open item D2).
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

## ACCEPTANCE (2026-08-24)

**Accepted with decided defaults** by the project owner's standing directive
of 2026-08-24 ("accept and fix all EDRs according to best recommended
solutions"). The authoritative row is
`edr_id=01a0341c-7119-7b38-9ddf-e6e73f2e1a88`; where this section and the row
differ in wording, the row outranks this file. Each default is amendable by a
future EDR.

1. **Model choice — low-cost high-throughput multimodal class, existing
   routing path only.** The primary critic is one low-cost,
   high-throughput multimodal model, selected by name at implementation time
   from whatever providers are then declared. It routes through the EXISTING
   provider-agnostic selection path — Appendix A's "vision and visual
   evidence" profile (`modality: image`, "returns structured evidence, not
   prose") with `RouterService.model_mode="fixed"` pinning the declared
   model id/provider. No new credential plumbing, no new provider SDK
   outside `adapters/**`: the critic rides the same broker/adapter machinery
   as every other harness (brokered short-lived credentials, declared
   `side_effect_class`). A frontier tier may be evaluated later behind its
   own decision if measured verdict quality demands escalation; self-hosted
   open-weights VLMs stay out (GPU/ops burden, own Ch.9.6 admission).

2. **Cost ceiling — $0.05 per critique cycle, $10 per product per month.**
   One critique cycle = screenshot capture + rubric scoring + verdict for
   one screen state. Crossing either ceiling is typed `BUDGET_EXCEEDED`
   state routed to the existing pause-for-human path (Ch.12.3/13.1), never
   silently absorbed; both numbers count against Ch.16.4 overhead
   accounting and are initial targets retunable by policy version with
   measured data.

3. **Rubric storage — extend existing structures, prefer no new table.**
   Checked first: `schemas/objects/verification_run.json` already links
   runs to evidence via `evidence_refs` and carries JSONB-class result
   structures. Rubric text is versioned under `schemas/design/` alongside
   `tokens.json` under the Ch.3.1 drift-gate discipline; each compiled
   prompt pins rubric + playbook versions onto the VerificationRun/Evidence
   linkage so verdicts are reproducible against named inputs. A dedicated
   durable table is added only if query needs outgrow the linkage (that
   widening would be its own schema decision through generate_contracts).

4. **Retention — rank-9 evidence law, unchanged.** Screenshots and critiques
   are rank-9 evidence artifacts: WORM object-lock ≥ the project's audit
   retention requirement (Ch.17.5); evidence-linked artifacts are never
   detached while referenced (Ch.3.7); never auto-deleted while the screen
   they judged remains merged. Raw screenshots may age to cold storage ahead
   of verdict rows per the artifact lifecycle policy — never deleted inside
   the retention window.

5. **Bounded revise ≤3 cycles, human escalation** exactly as proposed: each
   cycle consumes exactly one stored critique artifact; >3 cycles blocks
   auto-progression and escalates residuals to explicit human approval
   through the approvals surface. `prototype_pixel_signoff` must still be
   added through the ordinary contract path or an existing type designated
   before DDE-068's sign-off queue can be typed (GUI-spec open item D2).

6. **Silhouette generic-corpus sourcing — option (c): self-generated.** The
   generic-layout corpus is self-generated from playbook §1.1's nevers
   catalog: fully licence-clean, provenance trivially internal. Godly/
   land-book-class galleries remain SOURCE_REFERENCE_ONLY with no APIs and
   no scraping (playbook §10.5) — human curation inspiration only. Options
   (a) hand-transcribed teardown corpora and (b) licensed datasets stay
   available to a future amendment if curation capacity demands.

7. **Rank-9 forever, never auto-applied**, verbatim from the proposal:
   critiques inform humans and the bounded loop but never modify rank ≤3
   artifacts, never auto-approve themselves, never widen autonomy.
