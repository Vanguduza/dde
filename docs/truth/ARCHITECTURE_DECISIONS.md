# DDE Architecture Decisions — Rev 3 Decision Index

**Status:** CANONICAL HUMAN-READABLE DECISION INDEX  
**Effective:** 2026-09-02  
**Authority note:** accepted Project Truth EDR rows outrank this file. This file exists to let agents and humans understand the locked architecture without reconstructing it from chat history or scanning every historical document.

---

## 0. Decision classes

- **ACCEPTED-EDR** — implemented/locked by an accepted Project Truth EDR. The actual EDR row is authoritative.
- **REV3-LOCKED** — explicitly locked by Blueprint Rev 3. If implementation requires a contract-level divergence, file an EDR before changing the design.
- **PLANNED** — direction is accepted in the development plan but may depend on unavailable interfaces or later sequencing.
- **DEFERRED** — deliberately not current work.

---

## AD-001 — DDE, not any model or harness, owns authoritative state

**Status:** REV3-LOCKED

DDE Core owns Project Truth, mission state, approvals, routing policy, capability policy, verification and evidence. Claude Code, Hermes, Fable, DeepSeek, Cursor workers and future harnesses are replaceable workers/clients.

**Consequence:** no external harness may become the source of truth for missions, requirements, approvals or completion.

---

## AD-002 — Project Truth outranks all human-readable documents

**Status:** REV3-LOCKED / inherited architecture invariant

Accepted Project Truth rows written through `engine/truth/**` outrank markdown summaries, code comments, prompts, chat history and model memory.

**Consequence:** a markdown change cannot silently override an accepted EDR/requirement row.

---

## AD-003 — Blueprint Rev 3 supersedes Rev 2 for forward development

**Status:** REV3-LOCKED

`docs/truth/BLUEPRINT_REV3.md` is the canonical human-readable architecture. `docs/blueprint/historical/REV_2_0.md` remains historical depth/reference.

**Consequence:** new work boots from Rev 3; where Rev 2 conflicts with Rev 3, Rev 3 wins unless an accepted Project Truth record says otherwise.

---

## AD-004 — Schemas remain the contract SSOT

**Status:** REV3-LOCKED / inherited

`schemas/**` is the single source of truth for generated contracts. `engine/contracts/**` is generated output and must not be hand-edited.

**Consequence:** contract changes start at schemas and include drift checks.

---

## AD-005 — Interfaces never bypass Gateway/Core boundaries

**Status:** REV3-LOCKED / inherited

`interfaces/**` consumes API/Gateway/MCP surfaces and never reads/writes core tables directly.

**Consequence:** DDE Code and Frontend Studio must use the same governed command paths as other clients.

---

## AD-006 — Vendor code lives in adapters

**Status:** REV3-LOCKED / inherited

Core logic reasons about worker/capability profiles. Vendor SDKs and provider-specific implementation stay in adapters.

**Consequence:** replacing Claude/Hermes/Fable/DeepSeek/Cursor must not require rewriting mission or truth domains.

---

## AD-007 — Worker environments receive no ambient long-lived credentials

**Status:** ACCEPTED-EDR / REV3-LOCKED

Credential access is brokered, scoped and revocable. Long-lived secrets are never passed to environments executing model-generated code.

**Related readable EDR:** `docs/truth/edr/EDR-0001-subscription-based-worker-credentials.md` and later accepted credential/containment decisions.

---

## AD-008 — Network egress is deny-by-default and admitted by capability

**Status:** ACCEPTED-EDR / REV3-LOCKED

Outbound access is not a general worker privilege. Admitted surfaces use allowlists, brokered credentials, durable side-effect identity and audit/reconciliation rules.

**Related EDR:** `EDR-0015` accepts bounded donor-search egress for DDE-066. General containment/egress remains governed by its own accepted EDRs and implementation state.

---

## AD-009 — Side effects require durable identity and reconciliation semantics

**Status:** REV3-LOCKED

Every side-effecting operation declares a side-effect class, idempotency key and retry/reconciliation behavior.

**Consequence:** uncertain external outcomes enter reconciliation; blind retry is forbidden.

---

## AD-010 — Mission completion is evidence-backed, not self-reported

**Status:** REV3-LOCKED

Workers cannot self-certify completion. Completion requires applicable tests, production call-site evidence and verification records.

**Consequence:** a schema, stub, prompt, UI mock or green unit test alone is insufficient.

---

## AD-011 — Production call-site wiring is part of Definition of Done

**Status:** REV3-LOCKED

A guard, approval type, verifier, telemetry event or service is not considered complete until the real execution/promotion/UI path invokes it.

**Consequence:** chapter gates must map MUST/SHALL clauses to actual call sites.

---

## AD-012 — Planning output is untrusted until validated/promoted

**Status:** REV3-LOCKED / inherited

Candidate mission/task decompositions use the established draft -> validate -> promote pattern rather than directly minting authoritative work graphs.

**Consequence:** Fable/Hermes/Claude or any planner can propose plans but cannot bypass promotion policy.

---

## AD-013 — Fable 5 is preferred as a strategic orchestration worker, not state authority

**Status:** PLANNED / REV3-LOCKED role definition

When a supported Fable 5 interface is actually available and evaluation supports the route, DDE should prefer it for high-level decomposition, architecture review, dependency/risk planning and arbitration.

**Constraints:**

- no fake adapter if the interface is unavailable;
- no authoritative mission state in Fable memory;
- outputs pass ordinary validation/promotion;
- measured fallback exists.

---

## AD-014 — Hermes is the preferred persistent research/coordination harness

**Status:** REV3-LOCKED role definition

Hermes is best used for long-lived research, repository reconnaissance, context-packet assembly, external dependency intelligence, failure triage, recovery preparation and conversational operator assistance.

**Constraints:** Hermes memory is working memory only; authoritative facts are rehydrated from DDE state.

---

## AD-015 — Premium coding models are escalation resources, not default orchestration engines

**Status:** REV3-LOCKED

Claude Code or equivalent high-cost reasoning profiles should be used when complexity/risk justifies them, not for all crawling, dispatch, monitoring and mechanical work.

**Consequence:** quota pressure must be handled by specialization and deterministic validation rather than transferring all work to another premium model.

---

## AD-016 — Lower-cost workers are valid when deterministic gates can arbitrate quality

**Status:** REV3-LOCKED

DeepSeek-class/local/other lower-cost eligible workers should handle bounded implementation, mechanical refactors, test generation and parallel candidates where verification is strong enough to select/reject outputs.

---

## AD-017 — Independent review is preferred for high-risk implementation

**Status:** REV3-LOCKED

The same worker that implements a consequential change should not be the sole reviewer unless deterministic oracles fully cover the relevant risk.

---

## AD-018 — Routing uses eligibility first, optimization second

**Status:** REV3-LOCKED

Routing considers capability, context, safety/containment, quota, provider health, quality history, latency and cost. The cheapest route may not be chosen if it fails required confidence or capability constraints.

---

## AD-019 — Routing learning is promoted through evaluation, not self-modifying authority

**Status:** REV3-LOCKED

Learned routing policies are candidates evaluated by shadow runs, calibration, canaries and rollback. They do not self-promote based on model confidence.

---

## AD-020 — Repository artifacts, not chat history, carry project memory

**Status:** REV3-LOCKED

Engineering sessions must be resumable from repository truth/state plus current code.

**Consequence:** each meaningful tranche updates `IMPLEMENTATION_STATE.md`; major accepted architecture changes update the relevant truth docs/EDRs.

---

## AD-021 — Context is task-specific, provenance-aware and budgeted

**Status:** REV3-LOCKED

DDE should assemble the smallest sufficient context packet rather than shipping entire chat/repository history to each model.

**Consequence:** source rank, taint, input hashes and staleness matter; semantic retrieval does not outrank deterministic truth.

---

## AD-022 — Donor discovery is evidence/reference, not adoption authority

**Status:** ACCEPTED-EDR / REV3-LOCKED

DDE-066 may discover donors through accepted egress, but discovered code is not automatically executable/adopted. Classification and provenance precede use.

**Related:** EDR-0015, signed Frontend Studio charter, Chapter 13.8 rules.

---

## AD-023 — Frontend Studio uses conformance by construction

**Status:** REV3-LOCKED / signed charter

Authoring surfaces should expose token-valid structured values rather than arbitrary style mutation. Button-add, drag/drop, property edits and preview changes go through one structured manifest mutation path.

**Consequence:** important design violations become unauthorable, not merely lint findings after generation.

---

## AD-024 — Frontend quality includes distinctiveness, not only correctness

**Status:** REV3-LOCKED / signed charter

Generated interfaces are evaluated for generic layout fingerprints, hierarchy, believable density, copy, accessibility, motion semantics and rendered quality.

**Consequence:** a functionally correct generic AI dashboard may still fail Definition of Polished.

---

## AD-025 — Visual verification is a real DDE verification capability

**Status:** ACCEPTED-EDR direction / DDE-068 planned implementation

Playwright/rendered screenshots and visual evidence must be executed through the verification architecture and persisted as VerificationRun/Evidence artifacts rather than existing only as an ad-hoc CI script.

---

## AD-026 — VLM critique is rank-9 evidence with bounded revision

**Status:** ACCEPTED-EDR

EDR-0016 accepts the VLM design critic needed by DDE-068.

**Constraints:**

- critique is evidence, not direct mutation authority;
- revision loop is bounded to at most 3 automated cycles;
- residuals escalate to human decision;
- critic cost/provider failure is observable.

---

## AD-027 — External design skills inform encodings; they do not become product oracles

**Status:** REV3-LOCKED / existing signed design-tooling disposition

Useful concepts from strong design tools/skills are harvested into first-party DDE schemas, design dials, lints, scanners and acceptance criteria.

**Consequence:** DDE does not depend on third-party design skills as merge-blocking authorities.

---

## AD-028 — DDE Code must show honest unavailable/empty/degraded states

**Status:** REV3-LOCKED

No fabricated mission, donor, evidence or quality rows may be generated just to make the UI appear populated.

---

## AD-029 — DDE Code is a professional control-plane product, not a collection of stubs

**Status:** REV3-LOCKED

The operator experience should unify Mission Overview, truth/context, work, fleet/routing, worker rooms, Frontend Studio, approvals, verification, integrations and attention state with coherent visual hierarchy and operational honesty.

---

## AD-030 — DDE-069 is Frontend Studio V2 / Live Design Foundation, not a separate mobile mission

**Status:** REV3-LOCKED (resolves a documentation drift; supersedes this AD's earlier text)

DDE-069 is the **DDE Code / Frontend Studio V2 + Live Design Foundation** mission: a host-neutral React/TS/Vite workbench, production PXG/Frontend Contract/Coverage Engine, one unified mutation/candidate/lock architecture, governed design-source adapters, and first-class `Claude /design` integration — per `docs/truth/DEV_PLAN_REV3.md` §6 and the adopted domain architecture `docs/truth/FRONTEND_STUDIO_REV3.md` (AD-036).

This closes a same-day Rev 3.3 drift: `DEV_PLAN_REV3.md` was rewritten (commit `b5753db`, "docs: adopt Rev 3.3 orchestrator attestation truth") to give DDE-069 this scope, but this file, `IMPLEMENTATION_STATE.md` and `RESUME_PROMPT.md` were never updated to match and kept describing DDE-069 as deferred "Mobile/Multi-target Profiles." Web Frontend Studio quality (DDE-068) still gates DDE-069 promotion exactly as this AD originally said — that sequencing constraint is unchanged, only the mission's name/scope was drifted and is now corrected.

Mobile/multi-target work is not deleted or forgotten: it becomes a governed **sub-capability** of DDE-069 (platform-specific design-source adapters — BNA UI/gluestack/React Native Reusables — plus Expo/device runtime verification; `FRONTEND_STUDIO_REV3.md` §11.6, §26, migration phase M13), not a separately numbered deferred mission. See AD-031, unchanged.

**Consequence:** any doc, chapter gate, or agent bootstrap prompt referring to "DDE-069 mobile" as a standalone mission is stale. Treat this AD-030 and `FRONTEND_STUDIO_REV3.md` as authoritative until superseded by an accepted EDR.

---

## AD-031 — One design authority, many renderers

**Status:** PLANNED / REV3-LOCKED direction

Mobile/multi-target rendering (scoped inside DDE-069 per AD-030, not a separate mission) reuses one design/token authority and adds renderer adapters plus target-specific verification. A platform must not fork its own independent design truth.

---

## AD-032 — Costs and quotas are first-class observability/routing inputs

**Status:** REV3-LOCKED

Tokens, model spend, external search calls, screenshots, VLM critique, build minutes and other metered resources are observable and attributable to missions/runs.

---

## AD-033 — Deterministic mechanisms replace model calls where possible

**Status:** REV3-LOCKED

Compilers, validators, lints, state machines, rule tables and test oracles should perform work that does not require probabilistic reasoning.

**Consequence:** lower cost, less quota pressure and more reproducible behavior.

---

## AD-034 — Rev 3 truth docs are living controlled artifacts, not disposable generated notes

**Status:** REV3-LOCKED

`BLUEPRINT_REV3.md`, `DEV_PLAN_REV3.md`, `ARCHITECTURE_DECISIONS.md`, `IMPLEMENTATION_STATE.md` and `RESUME_PROMPT.md` form the human-readable bootstrap set.

**Consequence:** they must remain internally consistent and must be updated deliberately when the project advances. (AD-030's original text drifted from `DEV_PLAN_REV3.md` for several hours before being caught and corrected on 2026-09-04 — see AD-030 itself for the case study.)

---

## AD-035 — Golden visual authority: light-first supersedes the prior dark-first Frontend Studio direction

**Status:** REV3-LOCKED (user-approved change package, 2026-09-03)

The user-approved golden Frontend Studio mockup (1672×941px, approved 2026-09-03) is the canonical DDE visual baseline, per `docs/truth/FRONTEND_STUDIO_REV3.md` decision FS-R3-001. It supersedes the older DDE-069 "Precision Manufacturing Workbench" visual-direction prose in `DEV_PLAN_REV3.md` §6.1 (dark-first; broadly prohibited gradients).

Canonical direction: light-first, neutral, dense, precision-oriented shell; dark theme remains a required derived parity theme, not the golden baseline; DDE application chrome stays gradient-free; a target project being designed/previewed may use gradients when its own Frontend Contract permits them. The dense, high-information-density, no-generic-SaaS-card-grid discipline from the superseded text is retained.

**Consequence:** `DEV_PLAN_REV3.md` §6.1 is annotated as superseded-by-FS-R3-001 in place, preserving the historical text it replaces, rather than silently rewritten. Full architecture: `docs/truth/FRONTEND_STUDIO_REV3.md`.

---

## AD-036 — Frontend Studio Rev 3 domain architecture adopted

**Status:** REV3-LOCKED (user-locked change package, 2026-09-03)

`docs/truth/FRONTEND_STUDIO_REV3.md` is adopted as the canonical Frontend Studio domain architecture. It consolidates the prior Rev 2 Frontend Studio blueprint in full and supersedes `docs/planning/frontend-studio-gui-spec.md` for DDE-069's mission definition — that document's own header states "proposed spec — awaiting charter integration," so it was never formally adopted in the first place. `docs/planning/product-studio-charter.md` and `docs/planning/dde-frontend-ux-playbook.md` remain in force for their signed DDE-065/066/067/068 scope, except where `FRONTEND_STUDIO_REV3.md` explicitly supersedes a visual-direction detail (AD-035).

DDE-068 remains a hard prerequisite for any DDE-069 promotion: `FRONTEND_STUDIO_REV3.md`'s own "DDE-068 DEPENDENCY" clause and `docs/truth/RESUME_PROMPT.md` §3 both hold that Frontend Studio V2 work cannot be marked complete or promoted around the DDE-068 visual-verification gate, even though preparatory schema/UI/runtime work may proceed in isolated, non-promoted packets where sequencing allows.

**Consequence:** an agent bootstrapping into Frontend Studio work must read `FRONTEND_STUDIO_REV3.md` alongside the existing Rev 3 truth set (see updated `RESUME_PROMPT.md`). `frontend-studio-gui-spec.md` is retained for its still-useful mobile/technical detail but is no longer authoritative for DDE-069's mission scope.

---

## AD-037 — Documentation consolidation: one source of truth per subject, superseded/orphaned docs removed or archived

**Status:** USER-LOCKED (2026-09-04)

Per explicit user direction to leave the project "with one source of truth" and remove documents "containing superseded features... to avoid conflicting features, confusion," the following consolidation was executed on 2026-09-04, alongside AD-030/AD-035/AD-036 above:

1. `docs/blueprint/REV_2_0.md` — moved to `docs/blueprint/historical/REV_2_0.md` (not deleted; it remains historical/reference depth per the pre-existing rule at the top of this file). All ~19 in-repo references to the old path were updated to the new path. An archival note was added at the top of the moved file stating it is preserved verbatim, is not updated for accuracy, and naming two facts that have since changed (the deleted `product-constitution.md` stub it references as a bootstrap step, and DDE-069's redefinition under AD-030/AD-036).
2. `docs/planning/comparable-systems-research-2026-08-22.md` and `docs/planning/system-audit-2026-08-22.md` — deleted. Both were confirmed to have zero inbound references anywhere in the repository before deletion (verified by repo-wide grep, not merely asserted).
3. `docs/product-constitution.md` — deleted. It was an empty, never-filled template stub with one inbound reference, inside the now-archived `docs/blueprint/historical/REV_2_0.md`; that reference is addressed by the archival note in (1) rather than by editing the historical document's body text.
4. `docs/planning/frontend-studio-gui-spec.md` — annotated with a supersession banner pointing to `FRONTEND_STUDIO_REV3.md`/AD-036 for DDE-069's mission definition, consistent with AD-036's existing text; the file itself is otherwise retained per AD-036 for its DDE-065..068 GUI/UX detail.

**Consequence:** the repository's superseded/orphaned/empty documentation debt identified during this audit is resolved. Future superseded documents should be handled the same way — archived with a dated note if historically referenced, deleted outright if orphaned and empty — rather than left in place to accumulate drift. This AD does not itself change any DDE-06x/DDE-069 scope decision; those are recorded in AD-030/AD-035/AD-036.

---

## AD-038 — DDE-069 sequencing: domain before UI runtime

**Status:** IMPLEMENTATION-SEQUENCING (2026-09-04). Not a scope change; no
target is added, removed or weakened.

`FRONTEND_STUDIO_REV3.md` section 31 orders the migration M3 (UI runtime and
host bridge) and M4 (golden shell) *before* M5 (read projections) and M6
(PXG/Contract/Coverage). DDE-069 implementation instead built M5/M6 first,
then the DDE-068 binding carry-over, and takes up M3/M4 after.

**Why.** The same document's own governing rule is that no visible control may
exist without a real backing capability, and that a control whose capability is
absent must render a typed unavailable state. Building the shell first means
either (a) building it against nothing and filling it in later — the
"sophisticated mockup" failure mode the mission exists to avoid — or (b)
building every panel twice. Building the domain first lets each golden control
be bound once, against real state, with the binding ledger recording exactly
which controls are real and which are honestly unavailable.

**What this does not change.** M3 and M4 remain required, with the same gates:
host-neutral React/TS/Vite behind `DdeHostBridge`, no `acquireVsCodeApi()` in
feature code, and the canonical shell geometry. The golden-shell gate is
unchanged except that it is now explicitly a *structural* conformance gate
while the AD-035 artifact is missing (see below).

**Consequence.** `docs/truth/FRONTEND_STUDIO_BINDING_MATRIX.md` is the ordering
record: work proceeds by making UNBOUND rows real, not by completing M-numbers
in sequence.

---

## AD-039 — Golden visual authority: the approved artifact is absent from the repository

**Status:** BLOCKED_EXTERNAL (2026-09-04). Owner action required.

AD-035 makes a user-approved 1672x941 Frontend Studio mockup the canonical DDE
visual baseline. During DDE-069 cold-start reconstruction the image was found
to have **never existed in this repository**, verified by `git log --all
--name-only` across every ref and path. `FRONTEND_STUDIO_REV3.md`,
`DEV_PLAN_REV3.md` and AD-035 describe it in prose; prose is not pixels.

**Decision.** Two conformance claims are separated and must never be collapsed:

- `STRUCTURAL` — the implementation matches the normative measurements written
  into `FRONTEND_STUDIO_REV3.md` Part I sections 2-5. Checkable today, and the
  gate M4 is held to in the artifact's absence.
- `PIXEL_REFERENCE` — the rendered implementation matches the approved image.
  `engine.studio.golden_visual.require_pixel_reference` raises
  `CONTEXT_INCOMPLETE` while the artifact is unpinned, so no signoff can claim
  it.

This does not weaken AD-035. The visual law stands; what is refused is the
*claim* that DDE has verified against pixels it cannot read.

**To resolve.** Commit the approved image at
`docs/truth/golden/frontend-studio-shell.png` and record its sha256 in
`docs/truth/golden/GOLDEN_VISUAL_MANIFEST.json`. The manifest state machine
then reports `PINNED` and pixel-reference verification unblocks with no code
change. If the approved artifact cannot be recovered, that is a Project Truth
decision for the owner — either re-approve a regenerated mockup as revision 2,
or amend AD-035 to make the structural specification the sole visual authority.

---

## 1. Known open/partial decisions from the DDE-067 gate

The DDE-067 chapter gate records that EDR-0002, EDR-0003, EDR-0005, EDR-0027 and EDR-0033 remain open/unchanged at that point. Do not infer their resolution from Rev 3 planning language. Read the relevant EDR/Project Truth record before implementing affected behavior.

The same gate states that DDE-068 is the next sequential mission and that accepted EDR-0016 authorizes it.

---

## 2. How to add/change a decision

1. Identify the actual conflict or new requirement.
2. Check whether an accepted EDR already decides it.
3. If the change alters Project Truth, locked contracts, security boundaries or core authority, create/propose an EDR through the ordinary truth path.
4. After acceptance, update the relevant Blueprint Rev 3 section and this decision index.
5. Update `DEV_PLAN_REV3.md` and `IMPLEMENTATION_STATE.md` if sequencing/current state changed.

Do not use this file to bypass the EDR process.