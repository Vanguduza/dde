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

`docs/truth/BLUEPRINT_REV3.md` is the canonical human-readable architecture. `docs/blueprint/REV_2_0.md` remains historical depth/reference.

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

## AD-030 — Web Frontend Studio quality closes before multi-target expansion

**Status:** PLANNED

DDE-069 mobile/multi-target profiles are sequenced after the web Frontend Studio verification loop is evidence-complete enough to avoid multiplying an immature pipeline.

---

## AD-031 — One design authority, many renderers

**Status:** PLANNED / REV3-LOCKED direction

Multi-target/mobile support reuses one design/token authority and adds renderer adapters plus target-specific verification. A platform must not fork its own independent design truth.

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

**Consequence:** they must remain internally consistent and must be updated deliberately when the project advances.

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