# DDE Development Plan Rev 3.0

**Status:** CANONICAL DELIVERY PLAN  
**Effective:** 2026-09-02  
**Architecture authority:** `docs/truth/BLUEPRINT_REV3.md`  
**Current-state authority:** `docs/truth/IMPLEMENTATION_STATE.md`

---

## 0. Delivery law

This plan exists to turn the Rev 3 blueprint into executable software. It is not a feature wishlist.

Every mission must end with production behavior, tests and evidence. Documentation-only closure is forbidden where the blueprint describes an executable feature.

For each mission:

1. verify current repo state;
2. identify affected blueprint clauses and accepted EDRs;
3. write/adjust authoritative schemas first where contracts change;
4. create a failing contract/invariant test before implementation where practical;
5. implement the service/domain behavior;
6. wire a real production call site;
7. wire Gateway/API/UI when user-facing;
8. implement failure, recovery and idempotency behavior;
9. run focused tests, then `just check`/required CI gates;
10. perform chapter/mission gate review against actual call sites;
11. update `IMPLEMENTATION_STATE.md` with evidence and residuals;
12. update `ARCHITECTURE_DECISIONS.md` only when a decision is genuinely added/changed and create/accept the appropriate EDR if required.

A green test suite is necessary but not sufficient.

---

## 1. Current baseline

The latest verified repository head observed when Rev 3 was created was:

`c30d2969e3205d1a277dd128e8b182137a8892e0` — **DDE-067 Frontend Studio surface** (2026-08-27).

Subsequent commits that create or maintain these Rev 3 SOT files are documentation/control-plane bootstrap work, not evidence that later implementation missions are complete.

The next sequential product mission identified by the DDE-067 chapter gate is **DDE-068 — Visual Verification & Critique Loop**, unblocked by accepted EDR-0016.

---

## 2. Phase R3-0 — Source-of-Truth migration and agent bootstrap

### Goal

Make the repository, not a historic chat thread, sufficient to resume DDE development safely.

### Required outputs

- `docs/truth/BLUEPRINT_REV3.md`
- `docs/truth/DEV_PLAN_REV3.md`
- `docs/truth/ARCHITECTURE_DECISIONS.md`
- `docs/truth/IMPLEMENTATION_STATE.md`
- `docs/truth/RESUME_PROMPT.md`
- `AGENTS.md` points to Rev 3 authority order
- `README.md` points new contributors to Rev 3

### Acceptance gates

- no current bootstrap document calls Rev 2 authoritative;
- Rev 2 remains available as historical depth/reference;
- the new resume prompt requires reading current code and state before execution;
- every future mission has an explicit state-update obligation.

---

## 3. Phase R3-1 — DDE-068 Visual Verification & Critique Loop

**Priority:** P0 — next sequential mission.

### Objective

Complete the quality-enforcement side of Frontend Studio so generated screens are judged from rendered behavior and pixels, not only source linting or agent opinion.

### Implementation slices

#### R3-1A — Visual executor capability

- expose the admitted Playwright/render toolchain behind the DDE verification capability contract;
- create/complete a real executor for visual verification bindings rather than leaving `visual_diff`/judge-like types as schema-only values;
- persist VerificationRun and Evidence records for screenshots/results;
- make execution idempotent and address retry/reconciliation semantics;
- ensure ProductEnvironment is distinct from worker ExecutionEnvironment.

**Gate:** a production verification request can render a target screen, persist evidence and return a typed result through the real service path.

#### R3-1B — DD207+ combination/fingerprint lints

- extend deterministic design lints beyond atomic DD201–DD206 checks;
- detect known generic combinations and repeated AI-dashboard grammar;
- keep thresholds/data deterministic and testable;
- ensure lint results feed the same verification vocabulary rather than a parallel report format.

**Gate:** fixtures that individually pass earlier atomic lints but remain generic-shaped fail the combination gate.

#### R3-1C — Silhouette distinctiveness test

- define a screen-layout fingerprint/silhouette representation;
- build a maintained corpus of generic patterns with provenance;
- compute similarity using deterministic logic before involving a VLM;
- define calibrated blocking thresholds with test fixtures;
- store evidence explaining the near-match.

**Gate:** palette-swapped clones of a generic layout are still blocked.

#### R3-1D — Believable-density gate

- convert current density guidance into an executable score/check;
- reject lorem/`Item 1`/unrealistically sparse placeholder surfaces where the screen cannot be judged honestly;
- preserve explicitly marked sample data so it cannot be mistaken for production data.

#### R3-1E — Reduced-motion semantics

- assert that reduced-motion mode removes or minimizes spatial animation while preserving state transitions and comprehension;
- use Playwright evidence against real generated fixtures/screens.

#### R3-1F — VLM critique worker

- implement accepted EDR-0016 behind a worker/capability adapter;
- screenshot -> rubric critique -> durable critique artifact;
- critique is rank-9 evidence, never direct mutation authority;
- bounded revision count <= 3;
- after bound exhaustion, require human decision rather than silently continuing;
- account for critic cost and provider failure.

#### R3-1G — Bounded revise loop

- consume critique artifacts through the ordinary authoring/planning command path;
- each revision is a structured manifest/code change with provenance;
- re-run deterministic and visual gates after each revision;
- prevent a VLM from self-applying unreviewed edits outside allowed mutation surfaces.

#### R3-1H — Pixel sign-off / Definition-of-Polished integration

- ensure the approval vocabulary exists through the canonical contract path;
- block promotion/merge when required visual gates have not passed;
- surface residual findings and evidence in DDE Code.

### DDE-068 exit criteria

- all eight Definition-of-Polished categories defined by the signed charter are executable where applicable;
- visual verification is called from a production promotion path;
- no UI quality badge can be produced without recorded evidence;
- bounded VLM loop and human escalation are proven in tests;
- chapter-gate document maps every MUST/SHALL to a production call site;
- `IMPLEMENTATION_STATE.md` marks DDE-068 complete only after this evidence exists.

---

## 4. Phase R3-2 — Orchestration and worker-specialization layer

**Priority:** P0/P1 after DDE-068 core gates are usable.

### Objective

Make DDE use the right worker for the right job while keeping mission state, authority and verification inside DDE.

### R3-2A — Worker profile contract hardening

Ensure every worker/harness profile exposes:

- task capability classes;
- supported tools;
- context limits;
- expected latency;
- measured quality dimensions;
- cost/quota model;
- provider health;
- containment/credential tier;
- allowed autonomy level;
- verification eligibility.

Vendor names stay in adapters/registry, not in core decision logic.

### R3-2B — Fable 5 orchestration profile

When Fable 5 is actually available through a supported interface:

- implement it as a replaceable strategic orchestration worker profile;
- best-fit tasks: mission decomposition, cross-domain architecture review, dependency analysis, risk planning and arbitration;
- never allow Fable to own mission state or directly promote its own plans;
- route Fable outputs through draft -> validate -> promote;
- benchmark it against at least one alternative planning profile and a deterministic baseline;
- do not ship a fake adapter when the provider interface is unavailable.

If Fable 5 is unavailable, this slice stays `BLOCKED_EXTERNAL`, while the generic orchestration contract proceeds.

### R3-2C — Hermes role implementation

Harden Hermes for persistent, tool-rich coordination tasks:

- repository reconnaissance;
- evidence/research gathering;
- context-packet preparation;
- dependency/license intelligence;
- failure triage/recovery packet preparation;
- scheduled or long-lived operator assistance where supported;
- Gateway/MCP conversational control.

Hermes may maintain working memory, but authoritative facts must be rehydrated from DDE state and provenance.

### R3-2D — Premium coding/review profile

Use Claude Code or equivalent premium reasoning workers only for complexity/risk bands where measured value is higher.

Implement explicit routing rules so premium workers do not become default dispatchers, crawlers or mechanical-refactor agents.

### R3-2E — Lower-cost parallel workers

Use DeepSeek-class/local/other eligible workers for bounded coding, tests, mechanical refactors and candidate generation where deterministic verification can adjudicate.

### R3-2F — Independent reviewer policy

For high-risk changes, do not allow implementation and sole review to be the same worker profile unless a deterministic oracle fully covers the relevant risk.

### R3-2G — Quota-aware fallback

- model provider unavailable/quota exhausted -> reroute only to eligible profiles;
- never silently widen autonomy/capabilities;
- record fallback cause;
- preserve cost and quality telemetry;
- prevent one premium fallback from absorbing all delegated work.

### Exit criteria

A representative mission can be decomposed, routed to specialized workers, verified independently, recovered from provider failure and reconstructed from recorded events without relying on chat history.

---

## 5. Phase R3-3 — DDE Code / Frontend Studio professional product redesign

**Priority:** P1, may run in parallel with isolated backend work after DDE-068 contracts stabilize.

### Objective

Make DDE Code visually and operationally fit its role as a professional software-manufacturing control plane.

### R3-3A — Information architecture audit

Consolidate the shell around:

- Mission Overview;
- Project Truth / Context;
- Missions / Work in Flight;
- Fleet / Routing;
- Harness rooms;
- Frontend Studio;
- Approvals;
- Verification / Evidence;
- Integrations;
- Activity / Attention.

Remove views that are redundant, stub-like or developer-internal unless deliberately in an advanced/debug surface.

### R3-3B — Visual system

- establish a first-party DDE visual language with semantic tokens;
- professional typography and spacing hierarchy;
- coherent iconography;
- deliberate density suitable for control-plane work;
- responsive layout rules;
- dark/light behavior if supported;
- accessible contrast/focus/error/warning/success states;
- restrained purposeful motion.

### R3-3C — Honest operational states

Every panel must implement:

- loading;
- empty;
- unavailable;
- permission denied;
- degraded;
- error;
- active/running;
- blocked/pending approval;
- completed/evidence-backed.

No fake rows are allowed to make the UI look complete.

### R3-3D — Frontend Studio authoring UX

Complete the signed GUI specification with one structured mutation path for:

- button/add element;
- drag/drop/reorder;
- token-bound property editing;
- responsive state editing;
- live preview;
- before/after;
- apply/revert/version history;
- donor/reference browsing and adoption state;
- verification findings and critique actions.

### R3-3E — Visual regression of DDE itself

Use the same DDE visual gate philosophy on DDE Code/Studio surfaces: screenshots, accessibility and reduced-motion evidence become release gates for the operator UI.

### Exit criteria

DDE Code is not merely wired; it is demonstrably coherent, accessible and evidence-tested across primary workflows.

---

## 6. Phase R3-4 — Reliability, recovery and production-call-site closure

**Priority:** P1.

### Objective

Close known cases where contracts or policies exist but are partial, test-only or not wired through all production paths.

### Work classes

- promotion gate partial implementation;
- failure attribution closure;
- routing telemetry correctness;
- sequence/event push/listing gaps;
- credential broker real-provider paths;
- T2/container containment enforcement and residuals;
- external-effect reconciliation;
- durable session/resume behavior;
- approval production call sites;
- evidence binding completeness.

Before implementing any item, consult `docs/planning/gap-closure-record.md` and the relevant EDR/chapter gate to avoid duplicating closed work.

### Exit criteria

No item is closed because its type/schema exists. Closure requires a real call-site map and recovery evidence.

---

## 7. Phase R3-5 — Routing intelligence and evaluation

**Priority:** P1/P2 after baseline telemetry is trustworthy.

### Objective

Move from hand-authored heuristics to evidence-calibrated routing without giving learning systems direct policy authority.

### Slices

- normalized run outcome telemetry;
- quality/cost/latency attribution;
- task-class-specific scorecards;
- shadow routing evaluation;
- replay/evaluation fixtures;
- calibration;
- canary promotion;
- rollback;
- provider-health eviction;
- experience eligibility filtering;
- governed promotion of learned policy.

### Rule

Learned routing changes are candidates until deterministic evaluation and promotion gates accept them.

---

## 8. Phase R3-6 — Context and repository-memory optimization

**Priority:** P1/P2.

### Objective

Reduce token waste and reasoning errors by making DDE context small, current and provenance-aware.

### Slices

- task-specific context manifests;
- retrieval budget policies;
- source-rank enforcement;
- semantic retrieval quality evaluation;
- durable summaries with input hashes;
- staleness detection;
- repository-state snapshots;
- change-focused context after each mission;
- context-quality telemetry.

### Exit criteria

A new worker can resume a mission from DDE state + repository artifacts without receiving the historic chat thread or entire repository.

---

## 9. Phase R3-7 — DDE-069 Mobile / multi-target profiles

**Priority:** P2; do not begin as a distraction before web Frontend Studio is evidence-complete.

### Objective

Extend one product design truth into target-specific renderers without duplicating design authority.

Potential targets include Android/mobile and additional supported UI stacks.

### Requirements

- one token/design authority;
- target renderer adapters;
- target-specific accessibility and interaction rules;
- platform donor classification/provenance;
- per-target screenshot/e2e verification;
- no target adapter may bypass the canonical generation/verification path.

---

## 10. Phase R3-8 — Packaging, release and operational hardening

### Objective

Make Windows/local and cloud/Codespaces paths reproducible and supportable.

### Slices

- deterministic installer/build provenance;
- migration safety;
- health/readiness checks;
- update/rollback strategy;
- credential setup honesty;
- signing where configured;
- backup/recovery expectations;
- structured logs and operator diagnostics;
- release evidence bundle.

---

## 11. Cross-cutting security gate

Every phase must preserve:

- no ambient worker secrets;
- deny-by-default egress except accepted capabilities;
- explicit capability lease scopes;
- no direct core-table writes from interfaces;
- no vendor SDK in `engine/core/**`;
- no unclassified donor execution;
- no unsafe retry of side effects;
- no silent autonomy widening;
- no export of sensitive project/user data for convenience.

---

## 12. Cross-cutting cost gate

Each new model/tool-dependent feature records:

- what deterministic work replaces model calls;
- eligible low-cost profiles;
- high-reasoning escalation conditions;
- maximum bounded retries/critique cycles;
- quota failure behavior;
- telemetry needed to improve future routing.

---

## 13. Mission packet template

Every implementation mission should start with a packet containing:

### Intent
What user/product behavior must exist after this mission?

### Authority
Which Blueprint Rev 3 clauses, accepted EDRs and schemas govern it?

### Current evidence
What currently exists in code/tests/UI? Include concrete paths and commit/head.

### Gaps
Which behavior is absent, partial, stubbed or not wired?

### Contract changes
Which schemas/events/API/Gateway contracts change?

### Production call sites
Where will the feature actually run?

### Failure/recovery
How does it fail, retry, reconcile, cancel and resume?

### Verification
Which deterministic tests/oracles/visual/human gates prove it?

### Cost/security
Which capabilities, credentials, providers and budgets are involved?

### Exit evidence
What exact evidence permits `IMPLEMENTATION_STATE.md` to change to COMPLETE?

---

## 14. State vocabulary for this plan

Use these labels in `IMPLEMENTATION_STATE.md`:

- `COMPLETE_EVIDENCED` — implemented, wired and proven;
- `IMPLEMENTED_PARTIAL` — real code exists but important call-site/gate/recovery work remains;
- `IN_PROGRESS` — active mission;
- `PLANNED` — accepted plan, not started;
- `BLOCKED_DECISION` — requires Project Truth/EDR/human decision;
- `BLOCKED_EXTERNAL` — depends on unavailable provider/interface/tool;
- `DEFERRED` — intentionally sequenced later;
- `HISTORICAL` — retained for reference, not current work.

Never use `done` without evidence.

---

## 15. Immediate next execution order

Unless repository facts changed after this document was written, resume in this order:

1. verify current `main` head and working tree;
2. verify Rev 3 SOT migration is intact;
3. read `docs/planning/dde-067-chapter-gate.md` and DDE-068 charter sections;
4. audit current verification/oracle/visual code against DDE-068 requirements;
5. implement DDE-068 in vertical slices R3-1A through R3-1H with chapter gates;
6. update implementation state;
7. begin orchestration specialization work only after DDE-068 has a stable verification contract, except isolated adapter/profile research that does not alter authoritative state.

If the codebase has advanced beyond this sequence, update `IMPLEMENTATION_STATE.md` from evidence first, then continue from the first incomplete dependency.