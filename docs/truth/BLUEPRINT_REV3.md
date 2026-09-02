# DDE Blueprint Rev 3.0 — Canonical Product & Technical Architecture

**Status:** CANONICAL SOURCE OF TRUTH  
**Effective:** 2026-09-02  
**Supersedes for forward development:** `docs/blueprint/REV_2_0.md`  
**Repository:** `Vanguduza/dde`  
**Human-readable authority:** this document, subject to the authority rules below.

---

## 0. Purpose

DDE is a **software manufacturing control plane**, not an autonomous coding agent and not a thin wrapper around any model vendor. It owns durable product truth, mission state, context policy, routing policy, capability governance, execution admission, verification, evidence, approvals, cost/accounting policy, and the operator experience required to supervise software production.

External model APIs, coding agents, agent harnesses, CLIs, browsers and design tools are **replaceable workers or capabilities**. They may reason and execute work, but they never become authoritative for project state.

Rev 3 converts DDE from a large architecture conversation and a collection of planning documents into a repository-governed operating system for development. Every feature described here must resolve to executable contracts, production call sites, state transitions, tests and evidence. A documented idea is not an implemented feature.

---

## 1. Authority and precedence

When sources disagree, use this precedence order:

1. **Accepted Project Truth records** written through `engine/truth/**` — constitution, accepted requirements and accepted EDR rows.
2. **`docs/truth/BLUEPRINT_REV3.md`** — canonical human-readable architecture and product contract.
3. **`docs/truth/ARCHITECTURE_DECISIONS.md`** — readable decision index and Rev 3 locked design decisions; accepted EDR rows outrank summaries here.
4. **`docs/truth/DEV_PLAN_REV3.md`** — canonical delivery sequence and gate plan.
5. **`docs/truth/IMPLEMENTATION_STATE.md`** — current verified implementation snapshot.
6. Binding mission charters, chapter-gate records and specialist specifications under `docs/planning/**`.
7. Legacy blueprint `docs/blueprint/REV_2_0.md` and historical planning documents.
8. Code comments, model memory, chat history and agent opinion.

`docs/blueprint/REV_2_0.md` remains historical and may still contain deeper background material. It does **not** override Rev 3 for new work.

No agent may silently resolve a conflict by choosing a convenient source. Contract-changing divergence requires an EDR or explicit Project Truth amendment.

---

## 2. Non-negotiable system invariants

1. **One authority per mutable state domain.** No duplicate source of truth.
2. **Project Truth is durable and append/audit oriented.** Agents do not mutate it as a side effect of coding.
3. **Schemas lead code.** `schemas/**` remains the contract SSOT; generated contracts are never hand-edited.
4. **Workers are untrusted.** Model output is a proposal until validated and promoted through deterministic gates.
5. **All side effects are explicit.** Every side-effecting operation declares a side-effect class, durable identity, idempotency key and reconciliation strategy.
6. **No ambient secrets in worker environments.** Credentials are broker-issued, scoped, revocable and short-lived where possible.
7. **Evidence before completion.** A mission cannot become complete because an agent says it is complete.
8. **Production call-site proof.** A contract, service or guard that exists only in tests or documentation is not considered implemented.
9. **No fake UI state.** DDE surfaces show honest empty, disabled, unavailable and degraded states rather than fabricated data.
10. **Cost is a routing dimension, never a reason to violate safety or correctness.**
11. **Model diversity is a reliability mechanism.** Do not make a premium model absorb all orchestration, implementation and review responsibilities.
12. **The repository carries project memory.** Chat sessions are disposable clients and must not be required to reconstruct project intent.

---

## 3. System topology

DDE has five intentionally separate environments.

### 3.1 Authoring environment

Cursor, VS Code, DDE Code, terminals and chat clients. These are operator surfaces and worker launch points. They may cache local state but are never authoritative.

### 3.2 DDE Core

The control plane. Owns:

- Project Truth
- missions and work graphs
- requirement and artifact provenance
- context assembly policy
- model/harness routing policy
- capability leases and credentials
- execution admission
- approvals and governance
- verification runs
- evidence
- cost and routing telemetry
- recovery and reconciliation state

### 3.3 Execution environments

Disposable sandboxes for model-generated or agent-executed code. Default posture is isolated filesystem, deny-by-default egress, no ambient credentials and explicit capability leases.

### 3.4 Product environments

Throwaway or staged deployments of software DDE is manufacturing. They are test targets for end-to-end, visual, accessibility, performance and product verification. They are distinct from worker execution sandboxes.

### 3.5 Worker providers and harnesses

Claude Code, DeepSeek-class workers, Hermes, Cursor-backed workers, Fable 5 when available, local models and future providers. Every provider is behind a DDE adapter/profile and can be replaced without changing Project Truth.

---

## 4. Core control-plane domains

### 4.1 Truth domain

Owns constitutions, approved requirements, accepted EDRs and immutable provenance. Only `engine/truth/**` writes authoritative truth records.

### 4.2 Mission domain

Turns approved intent into durable mission graphs. Mission/task states must be explicit state machines. Typical progression:

`draft -> validated -> approved -> queued -> running -> verifying -> completed`

with explicit branches for blocked, paused, cancelled, failed, retryable, reconciliation-required and human-review states.

A worker cannot directly promote its own task to completed.

### 4.3 Context domain

Builds the smallest sufficient, provenance-carrying context packet for a task. Retrieval is governed, rank-aware and budgeted. Long chat history is not a context strategy.

Required characteristics:

- deterministic core inputs first;
- semantic retrieval only through approved policy;
- source rank and taint retained;
- explicit token/context budget;
- compression and summarization artifacts are versioned;
- no retrieved rank-9/10 material can silently modify rank-1/2/3 truth.

### 4.4 Routing domain

Chooses the best eligible worker/profile using task type, capability need, complexity, historical quality, latency, context size, price, provider health, quota and risk.

Routing must support:

- deterministic rules;
- calibrated scores from observed runs;
- shadow evaluation;
- canary promotion;
- rollback;
- health-based eviction;
- quota-aware fallback;
- independent verification routing.

### 4.5 Capability domain

All privileged actions pass through explicit capabilities. Examples: filesystem write, browser, GitHub, database mutation, package installation, network egress, secret access and deployment.

Capabilities require scope, actor, task/run identity, expiry/revocation and side-effect classification.

### 4.6 Verification and evidence domains

Verification is a first-class execution stage, not a final prompt asking a model whether its code looks correct.

Evidence may include:

- contract/unit/integration/e2e results;
- schema generation checks;
- migration forward/reverse proof;
- runtime traces;
- screenshot/visual evidence;
- accessibility results;
- performance measurements;
- security checks;
- deterministic invariant results;
- human approval records.

A VerificationRun records the binding, inputs, executor, result, evidence references and residual risk.

---

## 5. Orchestration strategy — Fable 5, Hermes and worker fleet

### 5.1 Principle

DDE itself remains the durable orchestrator of **state and governance**. No external agent harness owns DDE truth or mission state.

Within that boundary, DDE should use specialized orchestration capabilities rather than forcing one premium model to perform every role.

### 5.2 Fable 5 — preferred high-level reasoning/orchestration profile when available

Fable 5 is the preferred **strategic orchestration worker** when the environment provides a supported, testable adapter and its measured quality justifies the route.

Best-fit responsibilities:

- decompose complex cross-domain missions;
- identify dependencies and risky assumptions;
- choose worker specialization plans;
- synthesize audits across code, tests and documentation;
- design recovery/verification plans;
- arbitrate conflicting candidate approaches;
- perform high-value architecture reviews.

Fable 5 must **not** become a hidden single point of control. If unavailable, DDE executes the same mission contract using deterministic planning plus other eligible reasoning profiles. Fable-specific memory or task state is never authoritative.

### 5.3 Hermes — persistent operator/research harness

Hermes is best used for tasks where persistence, tool use, browsing/research, memory, scheduled follow-up and multi-step coordination matter more than highest-cost code synthesis.

Preferred Hermes use cases:

- long-lived research and evidence gathering;
- repository reconnaissance and task preparation;
- assembling context packets and provenance maps;
- dependency/license intelligence;
- documentation correlation;
- monitoring external dependencies or queued work;
- triaging failures and preparing recovery packets;
- maintaining worker-facing summaries from durable DDE state;
- operator assistance and conversational control of DDE via Gateway/MCP.

Hermes must not directly become Project Truth, bypass approvals, hold unrestricted credentials, or self-certify completion.

### 5.4 Claude Code / premium reasoning coding workers

Use for tasks where reasoning quality materially changes outcome:

- difficult implementation slices;
- architecture-sensitive refactors;
- security/recovery logic;
- complex bug diagnosis;
- final review of high-risk patches.

Do not use a premium worker as the default dispatcher, crawler, documentation reader and test babysitter if cheaper/deterministic mechanisms can perform those jobs.

### 5.5 DeepSeek-class and lower-cost workers

Use for bounded implementation, mechanical refactors, test expansion, documentation/code synchronization, static analysis assistance and parallel candidate generation where deterministic verification can arbitrate quality.

### 5.6 Independent review

The worker that implements a high-risk change should not be the only reviewer. DDE should prefer independent verification profiles or deterministic oracles for consequential work.

---

## 6. Reliability architecture

DDE must convert model uncertainty into observable state.

### 6.1 Assumption control

Before side-effecting implementation, task packets must state:

- known facts;
- unresolved facts;
- contracts being changed;
- expected production call sites;
- verification bindings;
- rollback/recovery path.

Agents should verify repository facts rather than infer them from filenames or chat summaries.

### 6.2 Two-phase work promotion

Planning/decomposition output is untrusted until validated. Candidate graphs or task plans use the established draft -> validate -> promote path rather than minting authoritative graph state directly.

### 6.3 Bounded retries

Retries are policy-controlled and require idempotency. Side effects are never blindly replayed. A failed side effect enters reconciliation when its outcome is uncertain.

### 6.4 Failure attribution

DDE distinguishes at least:

- model reasoning failure;
- tool/capability failure;
- environment failure;
- dependency failure;
- contract violation;
- verification failure;
- provider/quota failure;
- operator block;
- ambiguous external side effect.

Routing learning must not punish a model for infrastructure faults or reward it for unverifiable success.

---

## 7. Security and data handling

1. No personal/project-sensitive data is exported merely to improve agent convenience.
2. Secret material is only read through the capability broker path.
3. T2/model-generated execution is containerized/contained according to accepted EDRs and current implementation capability.
4. Outbound egress is deny-by-default except accepted, allowlisted capabilities such as DDE-066 donor discovery.
5. Every externally sourced artifact retains provenance and taint.
6. Donor code is never executed simply because it was discovered.
7. Dependency admission records license, maintenance signal and reason for use.
8. Generated code must not silently widen network, filesystem or autonomy policy.

---

## 8. Frontend Studio — product-generation system

Frontend Studio is not a prompt box with a preview. It is a governed product-generation workbench that turns approved product intent into distinctive, usable, verifiable interfaces.

### 8.1 Pipeline

`Approved PRD -> Art Direction -> Generation Prompt -> Donor Discovery -> Structured Screen/Manifest Authoring -> Live Preview -> Visual Verification -> Bounded Critique/Revision -> Human/Policy Gate -> Implementation Graph`

### 8.2 Existing mission chain

- **DDE-065:** deterministic generation-prompt compiler.
- **DDE-066:** donor discovery and feature-function taxonomy.
- **DDE-067:** Frontend Studio surface and Gateway consumption wiring.
- **DDE-068:** visual verification and critique loop.
- **DDE-069:** multi-target/mobile profiles, provisionally planned.

### 8.3 Conformance by construction

The authoring UI must make invalid design states difficult or impossible to express:

- token-valid color/type/space/motion selectors;
- structured manifest mutations rather than arbitrary DOM/style patches;
- reusable semantic roles;
- provenance-aware donor adoption;
- design-system constraints before generation, not only lint after generation.

### 8.4 Distinctiveness and anti-generic design

Generated products must not default to generic AI-dashboard grammar. DDE's design quality system combines:

- product-specific visual concept and design read;
- deliberate variance, motion and density controls;
- donor/reference research by product function;
- silhouette/fingerprint checks against generic layouts;
- DD201+ design lints and combination lints;
- believable sample-data density;
- copy quality gates;
- screenshot-based critique;
- bounded revision with evidence;
- accessibility and reduced-motion proof.

Third-party design skills can inform research, but DDE encodes useful concepts into first-party schemas, compilers, scanners and verification rules. External skills are not merge-blocking oracles.

### 8.5 Frontend Studio operator experience

The DDE Code / Studio surface must present DDE as a professional manufacturing control plane rather than a collection of developer stubs.

Primary information architecture:

- Mission Overview;
- System/connection health;
- Project Truth and context;
- Missions/work in flight;
- Fleet and routing;
- Hermes / Fable / Claude / DeepSeek worker rooms as available profiles;
- Frontend Studio;
- Approvals;
- Verification/evidence;
- Integration state;
- Activity/attention queue.

Visual design should prioritize hierarchy, scanability, calm density, professional typography, coherent iconography, accessible states and meaningful motion. Decorative complexity must never hide system state.

---

## 9. Donor/reference architecture

Donor discovery is research, not implementation authority.

Each donor/reference result must record:

- source URI/provider;
- product feature/function category;
- classification/license state;
- provenance/taint;
- adoption decision;
- affected artifact(s).

Unknown or rejected sources do not become implementation inputs. Adoption of donor-derived code requires the existing approval path.

---

## 10. DDE Code and Gateway boundary

`interfaces/**` is a client of DDE Core. It must not read/write core tables directly.

Every state-changing UI action routes through a Gateway/API/MCP command with a durable identity/idempotency key where required. The UI must not invent unavailable list data or locally synthesize authoritative rows.

DDE Code should provide a unified product shell for local Windows use while retaining Codespaces/cloud operation as a supported development/runtime path.

---

## 11. Model-agnostic adapter architecture

Vendor/provider logic lives behind adapters. The core reasons about capabilities and profiles, not vendor-specific SDK types.

Every worker profile declares at least:

- harness/adapter;
- eligible task classes;
- context limits;
- tool/capability support;
- cost model;
- latency/health metadata;
- credential tier;
- containment tier;
- verification history.

Fable, Hermes, Claude Code, DeepSeek, Cursor and future workers plug into this profile model.

---

## 12. Cost and quota architecture

DDE treats tokens, model spend, search calls, screenshots, VLM critique, build minutes and external API usage as measurable resources.

Routing must prefer the **cheapest eligible path that preserves the required confidence and safety**, not simply the cheapest model.

Premium reasoning is reserved for decisions where it changes expected outcome. Deterministic compilers, scanners, validators and tests replace model work whenever possible.

When a provider quota is constrained, DDE degrades by rerouting eligible tasks; it does not silently widen the scope of another premium model until that provider becomes a new bottleneck.

---

## 13. Observability and learning

Every mission should be reconstructable from event/evidence history:

- who/what proposed the work;
- which context was used;
- which worker/profile ran;
- which capabilities were leased;
- what changed;
- what verification ran;
- what failed and why;
- what cost was incurred;
- what was approved or rejected.

Routing learning may use this history only through governed promotion/calibration paths. Self-reported model confidence is not sufficient quality evidence.

---

## 14. Definition of implemented

A DDE feature is **implemented** only when all applicable items are true:

1. authoritative contract/schema exists;
2. service/domain behavior exists;
3. production call site uses it;
4. persistence/state transition is durable where required;
5. UI/API/Gateway path is wired if user-facing;
6. capability/security policy is enforced;
7. failure/recovery behavior exists;
8. automated tests cover the contract and important failure path;
9. verification/evidence demonstrates behavior;
10. docs and `IMPLEMENTATION_STATE.md` reflect reality.

A schema without a caller, a button without a command, a guard without production wiring, a model prompt without a verification loop, or a planning document without executable behavior is **not complete**.

---

## 15. Mission completion gate

Before a mission can be declared done:

- relevant blueprint sections are mapped to code paths;
- `just check` or the equivalent mission-specific CI set is green;
- chapter/mission gate confirms MUST/SHALL clauses at real call sites;
- migrations are proven forward/reverse when applicable;
- recovery and idempotency are proven for side effects;
- visual/UI work includes rendered evidence and accessibility checks as applicable;
- residuals are named rather than hidden;
- `docs/truth/IMPLEMENTATION_STATE.md` is updated.

Mechanical CI success alone is not chapter sign-off.

---

## 16. Rev 3 delivery priorities

Rev 3 prioritizes:

1. make repository SOT/bootstrap discipline operational;
2. finish DDE-068 visual verification and critique loop;
3. implement measured orchestration/routing roles for Fable/Hermes/premium/low-cost workers without surrendering DDE state authority;
4. harden DDE Code and Frontend Studio into a modern professional operator product;
5. close remaining production-call-site, telemetry, recovery and credential/containment gaps;
6. expand Frontend Studio to multi-target/mobile through DDE-069 only after the web pipeline is evidence-complete;
7. continuously replace prompt-only policy with deterministic constraints and measurable verification.

The executable sequence is maintained in `DEV_PLAN_REV3.md`.

---

## 17. Repository-memory operating model

Each engineering session must be resumable without the historic ChatGPT thread.

Start from:

1. `AGENTS.md`
2. `docs/truth/BLUEPRINT_REV3.md`
3. `docs/truth/ARCHITECTURE_DECISIONS.md`
4. `docs/truth/DEV_PLAN_REV3.md`
5. `docs/truth/IMPLEMENTATION_STATE.md`
6. the relevant mission charter/chapter gate

At the end of a meaningful implementation tranche, write the real result back to repository state. Chat summaries are disposable.

---

## 18. Change control

Rev 3 is versioned. Material architecture changes require:

- evidence of the current behavior;
- an explicit proposed change;
- affected invariants/contracts;
- migration/recovery implications;
- an EDR when Project Truth or a locked architecture decision changes;
- an updated blueprint revision or amendment once accepted.

Do not rewrite history to make implementation appear consistent. Preserve the decision trail and record the delta.