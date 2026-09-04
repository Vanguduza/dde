# DDE Blueprint Rev 3 — Consolidated Canonical Edition

**Canonical repository path:** `docs/truth/BLUEPRINT_REV3.md`  
**Status:** **CANONICAL HUMAN-READABLE ARCHITECTURE SOURCE OF TRUTH**  
**Effective:** 2 September 2026  
**Consolidated revision:** Rev 3.3 — Dial Depth-and-Breadth Hardened  
**Repository:** `Vanguduza/dde`  
**Product implementation baseline inherited:** DDE-067 (`c30d2969e3205d1a277dd128e8b182137a8892e0`)  
**Repository-memory baseline inherited:** Rev 3 source-of-truth bootstrap through `fcc3e542ebc98ce769ec7ca74de72887dc5e5c02`  
**Companion implementation authority:** `docs/truth/DEV_PLAN_REV3.md`  
**Supersedes for forward architecture work:** legacy Blueprint Rev 2 and all standalone Rev 3 addenda/amendments once this consolidated edition is adopted.

> This edition consolidates the original DDE Blueprint Rev 3.0, the Rev 3 quantum audit and realization findings, the Rev 3.1 Operational Hardening / Adaptive Routing amendment, the Claude `/design` + high-value Opal integration addendum, and the September 2026 orchestrator-control/serving-model-attestation findings from live Dial Main development into one architecture. The source documents and incident discussions remain historical evidence; they are no longer competing forward-development authorities.

> **Dial depth-and-breadth rule:** a capability is not fully specified unless the blueprint defines its authority, contract, state, runtime path, failure semantics, evidence, security boundary, observability, operator surface, testability and migration relationship. **Rev 3.3 makes this rule mechanically enforceable through the normative traceability, contract, state, failure, security, operations, parity and certification appendices in this document.**

---

# 1. Purpose

DDE is a **governed software manufacturing control plane**.

It transforms authoritative product intent into verified, releasable software through replaceable AI workers, deterministic services and controlled human gates while preserving:

- product and architecture truth;
- project identity and configuration integrity;
- mission/task state;
- execution traceability and provenance;
- security and data-egress boundaries;
- deterministic governance;
- change ownership;
- evidence inheritance and selective invalidation;
- recoverability and continuation;
- provider, cost, quota and context control;
- serving-model identity honesty and orchestrator-control attestation;
- verification independence;
- adaptive routing from verified experience;
- cross-platform feature completeness;
- professional visual and interaction quality.

DDE is **not** a chat wrapper, IDE skin, prompt collection, static model router, autonomous coding agent, no-code workflow runtime, or model-memory control plane.

The consolidated system boundary is:

```text
USER / PRODUCT OWNER
        │
        ▼
PROJECT IDENTITY + BOOTSTRAP
        │
        ▼
┌────────────────────────────────────────────────────────────────────┐
│                            DDE CORE                                │
│ Truth · Missions · Policy · Context · Routing · Capability         │
│ Change Governance · Evidence · Verification · Recovery · Learning  │
└───────────────────────────────┬────────────────────────────────────┘
                                │
                    governed runtime contracts
                                │
      ┌─────────────────────────┼──────────────────────────┐
      ▼                         ▼                          ▼
STRATEGIC ROLE             WORKER FLEET                 HERMES
Fable preferred       Opus/Sonnet/Haiku/Codex/     context, research,
Opus fallback          DeepSeek/local/specialists   experience intelligence
      │                         │                          │
      └─────────────────────────┼──────────────────────────┘
                                ▼
                   isolated WorkerSession
                  + Workspace + ChangePacket
                                │
                 ┌──────────────┴──────────────┐
                 ▼                             ▼
         PRODUCT IMPLEMENTATION          DESIGN GATE
                                        Claude Design or
                                      other certified provider
                 │                             │
                 └──────────────┬──────────────┘
                                ▼
                     REAL PRODUCT RENDER
                                ▼
                deterministic + independent
                    verification / evidence
                                ▼
                       integration gate
                                ▼
                   experience + learning
```

The foundational law is:

> **Models may propose, execute, design, retrieve and critique. DDE owns authoritative state, admissibility, lineage, routing policy, evidence and promotion.**

The operational corollary is:

> **Models occupy roles; model identities are not architectural roles.**

---

# 2. Authority hierarchy

The repository exposes one unambiguous authority hierarchy.

```text
1. Accepted Project Truth records / accepted EDRs
2. docs/truth/BLUEPRINT_REV3.md
3. Active policy versions + schema-generated contracts
4. docs/truth/DEV_PLAN_REV3.md
5. Durable mission/task/workflow definitions
6. docs/truth/IMPLEMENTATION_STATE.md as an evidence-backed current-state projection
7. Specialist specifications / chapter gates / historical audits
8. Legacy blueprint and superseded addenda
9. Implementation comments, chat history, agent memory and model opinion
```

### 2.1 Two canonical forward-development documents

For human-readable forward development there are exactly two primary canonical documents:

- **Blueprint Rev 3** — what DDE is, its invariants, contracts and target architecture.
- **Development Plan Rev 3** — how the repository reaches that architecture, in what dependency order, with what acceptance gates.

`ARCHITECTURE_DECISIONS.md` is an index of accepted/locked decisions, not a third competing architecture.  
`IMPLEMENTATION_STATE.md` is a factual current-state projection, not target architecture.  
`RESUME_PROMPT.md` is a bootstrap helper, not authority.

### 2.2 Conflict rules

1. An agent may never promote its own memory, chat summary or recommendation to Project Truth.
2. Model-generated plans remain untrusted until DDE validation and promotion.
3. A client UI never becomes a second source of mission/task/design/workflow state.
4. No adapter writes DDE Core tables directly outside its sanctioned service boundary.
5. Accepted EDRs remain durable history; supersession is explicit.
6. A standalone addendum may not remain forward-authoritative after its decisions are absorbed here.
7. A material conflict with Project Truth requires EDR/change-control, not convenient interpretation.
8. Documentation claiming runtime capability must be checked against production capability state/evidence.

---

# 3. Five environment law

The five environments remain separate.

## 3.1 Authoring Environment

Human IDE, terminal, mobile client, Cursor, Claude Code interactive shell, etc.

- not authoritative;
- may request commands;
- may display projections;
- may not mutate Core storage directly.

## 3.2 DDE Core

Authoritative control plane.

Owns:

- Project Truth;
- requirements;
- missions/tasks/attempts;
- routing decisions;
- harness and worker registry;
- policies;
- approvals;
- context records;
- evidence;
- verification;
- recovery;
- learning;
- immutable audit history.

## 3.3 ExecutionEnvironment

Disposable environment in which a worker executes.

Properties:

- workspace-bound;
- capability-limited;
- deny-by-default network;
- no ambient long-lived credentials;
- journaled side effects;
- replaceable.

## 3.4 ProductEnvironment

The software DDE is building, deployed for evaluation.

It is not the worker sandbox.

It is the target for:

- API probes;
- browser tests;
- mobile/device tests;
- screenshots;
- accessibility checks;
- performance checks;
- visual critique.

## 3.5 Worker Provider

Any model API, harness, local model or deterministic runner.

Providers are:

- replaceable;
- non-authoritative;
- measurable;
- health-checked;
- quota-aware;
- capability-scoped.

---

# 4. Core manufacturing lifecycle

Every meaningful DDE-controlled change follows an evidence-producing manufacturing chain.

```text
ProjectIdentity
    ↓
RuntimeRoot authorization
    ↓
Session bootstrap + EffectiveExecutionConfiguration
    ↓
BootstrapReceipt
    ↓
Mission intake
    ↓
Project Truth / requirements
    ↓
Context compilation
    ├── deterministic source set
    ├── Hermes retrieval/research
    └── ContinuationPackage when resuming
    ↓
Priority / risk evaluation
    ↓
OrchestratorModelState
    ├── desired model/role
    ├── configured/requested model
    └── serving-model evidence / control level
    ↓
StrategicOrchestratorLease
    └── authoritative occupancy only where the harness/runtime can actually control or attest it
    ↓
Execution-plan proposal
    ↓
Deterministic plan validation / human gate where required
    ↓
TaskExecutionDescriptor + ExecutionStrategy
    ↓
Experience lookup
    ↓
Capability/worker routing
    ↓
WorkspaceLease + ChangePacket
    ↓
WorkerSession / DesignSession
    ↓
Implementation / Try-Live candidate
    ↓
ProductEnvironment real render
    ↓
Verification
    ├── deterministic
    ├── integration
    ├── security
    ├── accessibility
    └── visual / independent critique
    ↓
EvidenceValidityGraph update
    ↓
StagingManifest + accepted packet scope
    ↓
Integration / release gate
    ↓
ExperienceRecord + routing telemetry
    ↓
Hermes experience distillation / policy-candidate discovery
```

No stage may be silently skipped because an AI reports completion.

### 4.1 Material UI branch

For material user-facing work:

```text
Task / current live state
    ↓
DesignGateDecision
    ↓
DesignGateway
    ↓
certified DesignProvider
    ↓
DesignCandidate(s)
    ↓
Try-Live isolated implementation
    ↓
real LIVE candidate
    ↓
iterate / branch / compare
    ↓
PROMOTE
    ↓
immutable design-version + code-revision pair
    ↓
verification
    ↓
ship eligibility
```

Provider artboards are design artifacts. **Only a code-backed ProductEnvironment candidate may be labelled LIVE.**

### 4.2 Continuation law

A long-running manufacturing chain must be resumable from repository/core state without replaying an entire chat. At context pressure or session loss, DDE emits a `ContinuationPackage`, checkpoints state and resumes through a fresh certified session rather than continuing high-risk work with unsafe context.

---

# 5. Strategic orchestration, model-control truth and dynamic role occupancy

DDE owns durable orchestration state. External models may perform strategic reasoning, but **configured intent, actual serving-model identity and authoritative role occupancy are separate facts**.

The live Dial Main incident established a new foundational rule:

> **DDE may never upgrade a desired, configured, requested, inferred or expected model identity into a claim about the model actually serving a running session without evidence.**

The general law is:

```text
DESIRED ≠ CONFIGURED ≠ SERVING
```

unless authoritative runtime evidence proves equality.

The same honesty rule applies elsewhere:

```text
configured capability ≠ functioning capability
installed harness ≠ healthy harness
requested route ≠ executed route
tests requested ≠ tests executed
scheduled update ≠ installed update
```

## 5.1 Rejected static topology

The following is not an architectural truth:

```text
Fable = strategy
Opus = specialist
Sonnet = implementation
Haiku = cheap work
Codex = coding
```

Those may be temporary priors. They may never hard-code the fleet.

DDE separates:

1. **orchestrator policy intent** — which model/profile DDE wants for the strategic seat;
2. **configured/requested model** — what the launcher/harness is asked to start;
3. **serving-model identity** — what model the provider/runtime is actually using;
4. **orchestrator occupancy** — a DDE-governed role claim that is authoritative only when control/attestation evidence is sufficient; and
5. **worker eligibility** — which certified worker configurations may execute bounded subordinate tasks.

## 5.2 `OrchestratorModelState`

Every strategic session records the three distinct truths:

```yaml
OrchestratorModelState:
  session_id:
  mission_id:
  project_id:

  desired:
    model_profile:
    reason:
    policy_hash:

  configured:
    model:
    configuration_source:
    configured_at:

  serving:
    model:
    exact_model_id:
    evidence_source:
    confidence:
    attested_at:

  control_capability:
    OCL_0_UNCONTROLLED |
    OCL_1_CONFIGURED |
    OCL_2_LAUNCH_CONTROLLED |
    OCL_3_RUNTIME_CONTROLLED_ATTESTED

  compliance:
    CONFIRMED |
    REQUESTED_UNATTESTED |
    MISMATCH |
    UNKNOWN
```

`serving.model` remains unknown when the runtime does not expose authoritative evidence.

A bootstrap/status message may say:

```text
DESIRED=fable
CONFIGURED=fable
SERVING=unknown
COMPLIANCE=REQUESTED_UNATTESTED
```

It may not shorten that to `FABLE_ACTIVE`.

## 5.3 Orchestrator control levels

DDE certifies each harness/runtime against four orchestrator-control levels.

### OCL-0 — uncontrolled

DDE cannot reliably select or observe the parent-session model.

```text
desired: maybe known
configured: unknown
serving: unknown
```

### OCL-1 — configured

DDE can configure what a future/new session should request, but cannot prove what model is serving the running session.

```text
desired: Fable
configured: Fable
serving: UNKNOWN
```

This is the current repo-level Claude Code limitation observed during Dial Main development.

### OCL-2 — launch controlled

A DDE-owned launcher/API creates the session with an explicit model request and records the runtime/provider acknowledgement where available. Serving identity is still not called authoritative unless attested.

### OCL-3 — runtime controlled and attested

DDE can select/pin the model through the supported runtime and obtain authoritative serving-model identity.

Only OCL-3 may unconditionally support UI/status language such as:

```text
Fable is currently orchestrating
```

For OCL-0/OCL-1/OCL-2, wording must reflect the actual evidence level.

## 5.4 `ModelServingEvidence`

```yaml
ModelServingEvidence:
  evidence_id:
  session_id:
  source:
    PROVIDER_RESPONSE |
    SDK_SESSION_METADATA |
    HARNESS_RUNTIME |
    LAUNCHER_ACK |
    UI_DISCLOSURE |
    INFERRED |
    NONE

  requested_model:
  reported_model:
  exact_model_id:

  confidence:
    AUTHORITATIVE |
    HIGH |
    INFERRED |
    UNKNOWN

  captured_at:
```

Only an evidence source certified for serving-model attestation may produce `AUTHORITATIVE`.

## 5.5 `StrategicOrchestratorLease`

`StrategicOrchestratorLease` remains the **target native DDE role-occupancy contract**, but it must not overclaim current integrations.

```yaml
StrategicOrchestratorLease:
  lease_id:
  project_id:
  mission_id:
  worker_session_id:
  role: STRATEGIC_ORCHESTRATOR

  desired_model_profile:
  configured_model:
  serving_model_evidence_id:
  control_level:

  occupant:
    model_endpoint_id:
    worker_profile_id:
    harness_installation_id:

  state:
    REQUESTED_UNATTESTED |
    ACTIVE_ATTESTED |
    FALLBACK_REQUESTED_UNATTESTED |
    FALLBACK_ACTIVE_ATTESTED |
    REPROMOTION_PENDING |
    RELEASED |
    FAILED

  previous_occupant:
  acquisition_reason:
  fallback_reason:
  reset_deadline:
  policy_hash:
  acquired_at:
  released_at:
```

For an OCL-1 harness, the lease records **requested/configured strategic intent**, not a fabricated live occupant.

For an OCL-3 harness, `ACTIVE_ATTESTED`/`FALLBACK_ACTIVE_ATTESTED` may represent real runtime occupancy.

Role changes emit normalized events carrying the control level and evidence status.

## 5.6 Current Claude Code transitional reality

The current repo-level Claude Code setup can configure the model requested for the **next session** but cannot, from repository code alone:

- determine which model is actually serving a running parent session;
- force a running parent session to change its model;
- prove that configured `fable` equals serving Fable.

Therefore current scripts/settings such as a model-tier controller are interpreted as:

```text
SET NEXT SESSION DESIRED/CONFIGURED MODEL = FABLE
```

or:

```text
SET NEXT SESSION DESIRED/CONFIGURED MODEL = OPUS FALLBACK
```

not:

```text
DEMOTE/PROMOTE THE MODEL OF THIS RUNNING SESSION
```

Session-start output must use language such as `CONFIGURED=fable` and explicitly disclose that configured state is not serving-model attestation.

The current truth for such a session is allowed to be:

```yaml
desired: fable
configured: fable
serving: unknown
control_capability: OCL_1_CONFIGURED
compliance: REQUESTED_UNATTESTED
```

This limitation is a typed capability gap, not a routing failure and not permission to hide the uncertainty.

## 5.7 Worker/subagent routing remains separately governable

The orchestrator-control gap does **not** invalidate subordinate routing.

Where the harness exposes controlled subagent/worker dispatch, DDE may still route bounded packets to certified workers and record the actual worker/model execution evidence independently.

When a parent session is attested Fable:

```text
ORCHESTRATOR
  Fable

ELIGIBLE SUBORDINATE CANDIDATES
  Opus
  Sonnet
  Haiku
  Codex
  DeepSeek
  local/specialist/future certified workers
```

Opus is not parked merely waiting for Fable failure; it remains an ordinary subordinate candidate and may receive any bounded task for which the empirical router selects its worker configuration.

No permanent rule says `Opus = specialist only`, `Sonnet = implementation only` or `Haiku = mechanical only`.

## 5.8 Fable unavailable / fallback

When Fable becomes unavailable or quota-exhausted, the action depends on orchestrator-control level.

For OCL-1 current Claude Code style integration:

```text
record provider/reset evidence
→ configure next session for Opus fallback
→ disclose SERVING=unknown until new-session evidence exists
```

For an OCL-3 runtime:

```text
Fable attested unavailable
→ acquire fallback strategic lease for best certified fallback
→ Opus initially preferred where policy/evidence supports it
→ remove the active fallback occupant from conflicting subordinate eligibility
```

The architecture must never pretend an OCL-1 configuration write changed the already-running parent model.

## 5.9 Fable restoration

Provider reset/health recovery also respects control level.

At OCL-1:

```text
reset deadline / recovery evidence
→ configure next session Fable-preferred
→ CONFIGURED=fable
→ SERVING=unknown
```

At OCL-3:

```text
Fable recovery attested
→ repromotion eligibility
→ safe atomic checkpoint
→ Fable acquires ACTIVE_ATTESTED strategic lease
→ Opus releases strategic lease
→ Opus returns to ordinary eligible worker pool
```

No stale fallback state and no premium-model creep are permitted.

## 5.10 Model-attestation honesty rule for high-risk work

If a task requires a specific orchestrator class/model and the current state is:

```text
DESIRED=Fable
CONFIGURED=Fable
SERVING=unknown
```

DDE may not certify:

```text
Fable orchestration complete
```

It must expose:

```text
Desired: Fable
Configured: Fable
Serving: Unattested
Requirement: Fable-class strategic review/orchestration
Status: model-specific orchestration not certifiable from current parent session
```

Policy may then:

1. continue where the task does not require model-specific attestation;
2. dispatch a **bounded, explicitly controlled Fable worker/subagent packet** where that satisfies a review/reasoning requirement;
3. request a fresh externally controlled session;
4. wait for an OCL-3-capable runtime;
5. block if the requirement truly demands attested parent orchestration.

A bounded Fable subagent result proves:

```text
Fable reviewed/executed this packet
```

It does **not** prove:

```text
Fable orchestrated the parent session
```

## 5.11 Strategic planning contract

The strategic reasoning path receives a bounded `MissionOrchestrationContext` and returns a schema-valid proposal. Production path remains:

```text
StrategicOrchestratorService.propose
→ PlanningRegistryService.submit_draft
→ deterministic validation
→ approval where required
→ promote_draft
```

The model never writes the authoritative task graph directly.

At OCL-1/OCL-2, any model-specific attribution attached to the parent reasoning must carry its serving-evidence status.

## 5.12 Sparse use

Strategic orchestration/reasoning is justified for:

- ambiguity resolution;
- cross-domain decomposition;
- architecture/migration planning;
- dependency and risk arbitration;
- recovery after repeated or systemic failures;
- route disputes;
- high-impact integration review.

It is not justified for grep, formatting, boilerplate, routine CRUD, mechanical tests or simple edits.

---

# 6. Hermes persistent intelligence role

Hermes is DDE's persistent **context, research, continuity and experience-intelligence substrate**. It is not a second control plane.

### 6.1 Memory domains

```text
Hermes Memory
├── Project Memory
├── Research Memory
├── Skill Memory
├── Operator Memory
├── Failure Memory
└── Execution Experience Memory
```

Authoritative raw runtime telemetry remains in DDE storage. Hermes receives derived/indexed records for semantic retrieval and pattern discovery.

### 6.2 Core Hermes capabilities

Hermes may:

- scout repositories and Project Truth;
- gather external research/evidence under policy;
- build context candidates;
- curate reusable lessons;
- retrieve prior design decisions;
- prepare continuation/recovery context;
- identify repeated failure signatures;
- correlate task families with successful worker configurations;
- propose workflow/playbook candidates;
- propose routing insights;
- answer provenance questions;
- assist operator interaction through Gateway/MCP.

Hermes must not:

- silently rewrite Project Truth;
- choose a merge/release;
- overwrite empirical telemetry;
- promote a routing policy;
- certify its own memory as evidence;
- become the sole store of design/workflow history.

### 6.3 ExperienceRecord

Every meaningful independently verifiable worker attempt produces an experience record keyed to the **full worker configuration**, not only a model name:

```yaml
ExperienceRecord:
  task_signature:
    domain:
    platform:
    framework:
    operation:
    risk_class:
    blast_radius:
    ambiguity:
    context_volume:
    verification_type:
  worker_configuration:
    model:
    model_version:
    provider:
    harness:
    harness_version:
    worker_profile:
    skills_manifest_hash:
    tool_policy_hash:
    context_strategy:
    execution_environment:
  outcome:
    completed:
    verified:
    first_pass_verified:
    attempts:
    rework_turns:
    regression_count:
    escaped_defects:
    human_intervention:
  economics:
    input_tokens:
    output_tokens:
    cache_tokens:
    reasoning_tokens:
    duration_ms:
    provider_cost:
    effective_cost:
  failure_signatures: []
  verification_refs: []
```

Only independently verified outcomes strongly influence routing.

### 6.4 ExperienceScout

Before route selection Hermes may produce `ExperienceContext`:

- similar task families;
- successful configurations;
- failure patterns;
- escalation patterns;
- evidence count;
- freshness;
- confidence.

This is routing evidence, not routing authority.

### 6.5 RoutingInsightCandidate

Hermes may propose a policy candidate, but promotion is:

```text
Hermes insight
→ offline replay
→ holdout evaluation
→ shadow
→ canary
→ governed policy promotion
```

### 6.6 ContinuityScout and ProvenanceScout

On resume Hermes may identify prior decisions, unresolved findings, previous verification, affected code and prior route failures. Provenance queries must resolve from durable DDE identifiers such as requirement → task → ChangePacket → WorkerRun → VerificationRun → commit.

---

# 7. Worker, harness and runtime-capability model

DDE routes **worker configurations**, not model names.

```text
WorkerConfiguration =
  model + model_version
  + provider
  + harness + harness_version
  + worker_profile
  + certified skills/tools
  + context strategy
  + execution environment
  + policy hashes
```

### 7.1 Persistent authorities

The target persistent fleet model includes:

```text
harnesses
harness_installations
harness_versions
worker_profiles
worker_profile_capabilities
worker_profile_certifications
model_endpoints
model_capabilities
provider_capacity_snapshots
runtime_capability_certifications
```

The Router and Worker Manager must query the same authority.

### 7.2 Capability truth levels

DDE distinguishes:

```text
documented capability
installed capability
certified capability
measured capability
```

Only **certified installed** capabilities may be relied on in production routing/lifecycle logic.

### 7.3 Version-specific discovery

Every exact harness installation publishes/certifies what it actually supports, including where applicable:

- persistent session;
- session resume;
- session start/stop/failure hooks;
- rate-limit events;
- instructions-loaded event;
- runtime model switching;
- explicit model request/pinning;
- serving-model identity/attestation;
- provider acknowledgement of model selection;
- fallback visibility/control;
- provider usage;
- quota/reset metadata;
- structured output;
- tool interception;
- cwd/project-root binding;
- project-configuration discovery.

A vendor documentation page is not proof that the installed version exposes a capability.

### 7.4 Model-control capability contract

Every orchestration-capable harness records:

```yaml
ModelControlCapabilities:
  can_request_model:
  can_pin_exact_model:
  can_read_serving_model:
  can_change_model_mid_session:
  can_resume_session_with_new_model:
  provider_acknowledges_model:
  fallback_visible:
  fallback_controllable:
  certified_orchestrator_control_level:
```

A harness that can only write configuration for a future session is OCL-1 even if the configuration key is named `model`.

### 7.5 Certification lifecycle

```text
discovered
→ smoke-tested
→ contract-tested
→ shadow
→ certified
→ measured
```

A changed model/harness/profile/tool/skill/config identity becomes stale until re-certified according to risk.

### 7.6 Role certification

A worker may be certified for multiple roles. Example:

```yaml
opus_configuration:
  orchestration_capable: true
  implementation_capable: true
  review_capable: true
  security_reasoning_capable: true
```

Certification does not imply current role occupancy.

---

# 8. Agent interoperability

## 8.1 AgentInteropLayer

DDE exposes one internal interoperability boundary:

```text
Worker Manager
    ↓
AgentInteropLayer
    ├── Codex Native
    ├── Claude Native
    ├── DeepSeek Native
    └── ACP
         └── Hermes / future agents
```

ACP is the baseline compatibility protocol.

Native bridges are retained when they expose richer capabilities.

## 8.2 Capability negotiation

Each harness advertises an `AgentCapabilityDescriptor` including:

- streaming;
- session resume;
- session fork;
- structured output;
- tool events;
- usage reporting;
- model switching;
- permission requests;
- subagents;
- background execution;
- checkpointing;
- worktree support;
- vision;
- browser;
- MCP.

DDE routing never assumes all agents implement the same protocol semantics.

---

# 9. WorkerSession

WorkerSession is a first-class durable runtime object.

A WorkerRun represents one attempt/turn/execution.

WorkerSession represents the long-lived harness/session lineage.

Minimum state:

```yaml
worker_session_id:
tenant_id:
project_id:
mission_id:
task_id:
harness_installation_id:
worker_profile_id:
provider_session_ref:
model_endpoint_id:
workspace_id:
execution_environment_id:
state:
context_package_hash:
tool_policy_hash:
session_config_hash:
created_at:
last_activity_at:
```

Lifecycle:

```text
OPENING
  ↓
ACTIVE
  ├── PAUSED → RESUMING → ACTIVE
  ├── DETACHED → RESUMING → ACTIVE
  ├── FAILED
  └── CLOSED
```

Session identity is mandatory for resumable native Codex, Claude, Hermes and similar workers.

---

## 9.1 Consolidated WorkerSession additions

A durable session also binds:

```yaml
WorkerSession:
  ...
  project_identity_id:
  bootstrap_receipt_id:
  effective_config_hash:
  orchestrator_model_state_id:
  model_serving_evidence_id:
  orchestrator_lease_id:
  context_budget_id:
  context_pressure_state:
  continuation_package_id:
  change_packet_ids: []
```

Session start is illegal until a valid `BootstrapReceipt` exists for the project/root relationship.

## 9.2 ContextBudget

```yaml
ContextBudget:
  maximum:
  consumed:
  remaining:
  task_estimate:
  checkpoint_threshold:
  strategic_start_threshold:
  state:
    HEALTHY | PRESSURE | CHECKPOINT_REQUIRED | UNSAFE_FOR_HIGH_RISK_WORK
```

When remaining context is below the strategic threshold, high-risk financial/security/migration work must not start. DDE checkpoints and resumes it in a fresh session.


---

# 10. Execution strategy

Task classification, execution strategy, harness selection, model selection and environment allocation are separate decisions.

## 10.1 TaskExecutionDescriptor

Every routable task has a structured descriptor:

```yaml
domain:
platform:
language:
framework:
operation:
risk_class:
blast_radius:
novelty:
ambiguity:
context_volume:
cross_repo_scope:
read_scope:
write_scope:
required_tools:
network_requirement:
visual_requirement:
security_requirement:
expected_duration:
parallelizability:
verification_type:
budget_class:
latency_priority:
quality_priority:
```

Free-text keyword guessing is not authoritative classification.

## 10.2 ExecutionStrategy

Supported strategies include:

```text
DIRECT
PLAN_THEN_IMPLEMENT
PLAN_IMPLEMENT_REVIEW
INVESTIGATE_THEN_IMPLEMENT
SPECIALIST_FANOUT
PARALLEL_IMPLEMENTATIONS
IMPLEMENT_THEN_RED_TEAM
VISUAL_ITERATION_LOOP
MIGRATION_WITH_ROLLBACK_PROOF
```

Strategy selection precedes harness selection.

---

# 11. Adaptive routing intelligence

Routing is capability/risk legality first and optimization second.

### 11.1 Hard gates

A candidate is excluded before ranking if it fails any required constraint, including:

- certified capability;
- environment compatibility;
- security/risk class;
- declared write scope;
- platform/product support;
- provider health;
- quota/capacity;
- verification independence;
- approval/policy;
- context sufficiency.

A cheaper worker may never override a failed hard gate.

### 11.2 Initial priors

Until enough evidence exists, DDE may use heuristic priors such as:

- Fable often strong at strategic orchestration;
- Opus often strong at difficult bounded reasoning/implementation;
- Sonnet often strong at general engineering;
- Haiku often useful for low-cost mechanical work;
- Codex often strong for coding-intensive work;
- DeepSeek useful for economical fan-out;
- deterministic tools best for mechanical invariants.

These are bootstrap priors, not identities. Their influence decays as verified evidence accumulates.

### 11.3 Target utility

Among legal candidates:

```text
utility =
    p_verified_success
  - λ_cost        × expected_effective_cost
  - λ_latency     × expected_latency
  - λ_rework      × expected_rework
  - λ_quota       × quota_pressure
  - λ_context     × context_miss_risk
  - λ_operational × operational_risk
  - λ_human       × expected_human_intervention
```

The objective is:

> **Select the cheapest certified configuration sufficiently likely to achieve the required verified outcome, while allowing a premium configuration to win when reliability, rework, latency or risk justify total effective cost.**

### 11.4 Learn configurations, not brands

Performance aggregates at multiple levels:

```text
model
model + task family
model + harness
model + harness + task family
model + worker profile
full WorkerConfiguration
```

A harness/skill/context change can materially alter model performance.

### 11.5 Escalation learning

DDE learns sequences as well as winners:

```text
Sonnet → Opus only on failure signature X
Haiku → Sonnet
Codex → Opus independent review
Fable orchestrates → Sonnet implements → Opus verifies
```

`EscalationPolicy` is evidence-backed and versioned.

### 11.6 Controlled exploration

Low-risk work may shadow/canary promising alternatives. Financial, security, migration and other high-risk work require stricter certification before exploration.

### 11.7 Freshness/version decay

Historical evidence weight considers sample confidence, freshness, task similarity and worker-configuration similarity. New model/harness versions may inherit only a cautious discounted prior.

### 11.8 Route Critic

A model Route Critic is invoked only for low deterministic confidence, close candidates, novel/high-risk tasks, prior route failure or planner/router disagreement. Its opinion remains evidence for DDE policy, not policy by itself.

---

# 12. Provider capacity, quota and probe economics

Provider state is first-class routing input.

### 12.1 Capacity states

```text
AVAILABLE
DEGRADED
QUOTA_PRESSURE
RATE_LIMITED
EXHAUSTED
COOLDOWN_UNTIL_RESET
REPROMOTION_ELIGIBLE
AUTH_REQUIRED
UNHEALTHY
```

`ProviderCapacitySnapshot` stores:

```yaml
provider:
model:
observed_at:
state:
concurrency:
recent_failures:
auth_state:
next_reset_at:
reset_source:
reset_confidence:
safety_margin_ms:
estimated_probe_cost:
p95_latency:
current_cost_metadata:
```

### 12.2 Reset policy

Prefer:

```text
reliable passive reset signal
→ cheap active probe if justified
→ expensive active probe only when expected value exceeds cost
```

Do not burn large token budgets merely to discover a Boolean already supplied by authoritative provider metadata.

### 12.3 Premium-capacity conservation

Quota scarcity never causes silent premium-model role expansion. DDE separately controls:

- strategic-orchestrator consumption;
- ordinary premium worker consumption;
- review consumption;
- design-provider consumption;
- probe consumption.

Telemetry must expose premium-model creep.

### 12.4 Unknown values

Unknown cost/usage/capacity is represented as unknown, not zero or healthy.

## 12.5 Configuration is not serving-model evidence

Provider capacity/reset state may justify changing the **desired/configured model for a future session**, but it does not prove that a running parent session changed models.

Capacity records therefore bind separately to:

```text
desired_model
configured/requested_model
serving_model_evidence
orchestrator_control_level
```

A timed reset may make Fable `REPROMOTION_ELIGIBLE`; only an attesting runtime may promote that fact directly to `Fable ACTIVE_ATTESTED`.

---

# 13. Workspace, ChangePacket and commit governance

Execution isolation alone is insufficient. Every controlled mutation has explicit ownership.

### 13.1 WorkspaceLease

One editing session operates inside an authorized workspace/worktree. Parallel work requires non-conflicting ownership based on declared file/symbol/contract scopes.

### 13.2 ChangePacket

```yaml
ChangePacket:
  packet_id:
  project_id:
  mission_id:
  task_id:
  worker_run_id:
  workspace_id:
  declared_read_scope: []
  declared_write_scope: []
  expected_generated_paths: []
  parent_commit:
  base_tree_hash:
  touched_paths: []
  diff_hash:
  staged_paths: []
  staged_diff_hash:
  provenance_refs: []
  gate_refs: []
  state:
    PLANNED | ACTIVE | READY_FOR_REVIEW | ACCEPTED |
    REWORK_REQUIRED | REJECTED | QUARANTINED | COMMITTED
```

A commit must be attributable to accepted ChangePackets.

### 13.3 Rejection semantics

`REJECTED` is operational:

```text
REJECTED
→ identify packet-owned mutations
→ quarantine / revert / isolate
→ verify accepted baseline
→ record RejectionDisposition
```

Rejected work may never remain anonymous dirty state for a later worker to sweep into a commit.

### 13.4 StagingManifest

```yaml
StagingManifest:
  packet_id:
  declared_paths: []
  actual_changed_paths: []
  staged_paths: []
  unexpected_paths: []
  staged_diff_hash:
  reviewer:
  result: PASS | BLOCK
```

Normal controlled flow:

```text
accepted ChangePacket
→ explicit/hunk-scoped staging
→ staged-diff verifier
→ scope comparison
→ commit manifest
→ commit
```

Unexpected staged paths block the commit.

Broad staging such as `git add -A` requires an explicit bulk-maintenance packet or explicit governed override.

### 13.5 WriteOwnershipGraph

Before parallel dispatch DDE checks:

- file overlap;
- symbol overlap;
- generated-contract overlap;
- schema/migration contention;
- shared lockfiles;
- integration hotspots.

Concurrency is bounded by dependency, write-scope, provider, verification and operator-attention capacity—not agent count.

---

# 14. Nested delegation

Nested worker delegation is allowed only under explicit policy.

`DelegationPolicy` includes:

```yaml
max_depth:
max_children:
allowed_operations:
forbidden_operations:
required_child_telemetry:
```

Children may not:

- mutate Project Truth;
- approve;
- merge;
- alter routing policy;
- alter credential policy;
- escape parent write scope.

Important cross-task dependencies are promoted into DDE TaskGraph nodes rather than hidden indefinitely inside a worker.

---

# 15. Context, continuation and evidence-aware compilation

Context is a runtime resource, not an unbounded chat transcript.

### 15.1 Context Compiler

For each task compile the smallest sufficient package from:

1. accepted Project Truth / requirements;
2. active policies/contracts;
3. affected schemas and code;
4. current verified state/evidence;
5. relevant historical decisions;
6. bounded Hermes research/retrieval;
7. explicit unresolved facts;
8. verification expectations.

Every item retains provenance, authority rank, freshness and taint.

### 15.2 No repository dumping

The compiler favors exact path/range/semantic retrieval around the task. Full-repository context is exceptional and must be justified.

### 15.3 ContinuationPackage

```yaml
ContinuationPackage:
  continuation_id:
  project_id:
  mission_id:
  task_id:
  authoritative_requirements: []
  accepted_decisions: []
  current_branch:
  base_commit:
  current_head:
  working_tree_state:
  active_change_packet:
  completed_steps: []
  unresolved_findings: []
  next_exact_action:
  required_evidence: []
  forbidden_rework: []
  context_package_hash:
  created_at:
```

A fresh worker can resume from this package without replaying old chat.

### 15.4 Evidence-aware continuation

The compiler must identify:

```text
what remains trusted
what changed
what evidence was invalidated
what requires re-verification
what must not be reworked
```

Previously verified work is not re-audited merely because a new session starts.

### 15.5 Data-egress minimization

Provider context is allowlisted. Secrets, user records, production data, credentials, private unrelated documents and unrelated repository material are excluded unless an explicit capability/policy requires them.

---

# 16. Truth and drift compiler

REV 3 introduces a `TruthCompiler`.

It produces a machine-readable capability realization matrix:

```text
specified
contracted
wired
executable
observable
verified
```

The system must detect contradictions such as:

- README claims live adapter while `start()` is fail-closed;
- UI calls a worker active while no certified adapter exists;
- accepted EDR text still claims proposed;
- old mission says an item is open after a later mission closes it;
- route profile maps to nonexistent worker;
- current model catalog references removed provider/model;
- enum is advertised though no production writer can emit it.

`just truth-check` becomes a release/chapter-gate requirement.

---

## 16.1 EvidenceValidityGraph

Verification evidence has explicit dependency/invariant bindings.

```text
verified component
+ no relevant dependency/invariant change
= evidence remains valid
```

A changed invariant traverses the graph and invalidates only dependent evidence.

## 16.2 RegressionInvalidationGraph and DeltaAuditPlan

A change produces a `DeltaAuditPlan` describing:

- preserved evidence;
- invalidated evidence;
- required regression checks;
- prohibited blanket rework;
- residual uncertainty.

This eliminates the false choice between “trust everything forever” and “re-audit the whole repository after every change”.


---

# 17. Verification

## 17.1 Independent authority

The producer of a change cannot be its sole authoritative verifier.

Generator identity is derived automatically from actual TaskAttempt/WorkerRun history, not optional caller hints.

For high-risk work where feasible:

```text
planner != implementer != semantic verifier
```

## 17.2 Fresh-context review

A semantic verifier receives:

- requirements;
- acceptance criteria;
- architecture constraints;
- diff;
- runnable product;
- deterministic evidence.

It does not inherit the implementer transcript.

## 17.3 Deterministic-first

Deterministic evaluators remain authoritative for things they can prove:

- compile/build;
- tests;
- schema;
- API;
- database;
- security/static analysis;
- accessibility rules;
- visual geometry;
- token conformance;
- screenshot diffs.

Model critics augment, not replace, deterministic evidence.

---

## 17.1 Verification lineage

Every VerificationRun binds to exact:

- requirement/acceptance criterion;
- task/change packet;
- code revision;
- design version when applicable;
- runtime/environment identity;
- verifier/oracle identity;
- evidence artifacts.

## 17.2 Independent verification

High-risk implementation must not be accepted solely by the worker that created it unless deterministic oracles fully cover the relevant risk.

## 17.3 Evidence inheritance

A new commit does not erase all prior proof. The EvidenceValidityGraph determines selective reuse/invalidation.


---

# 18. Failure, recovery and stuck detection

DDE preserves its journal/checkpoint/recovery architecture.

Add a failure fingerprint:

```text
hash(
  failure_class,
  failing_tests,
  error_signatures,
  touched_scope,
  attempted_strategy
)
```

Policy:

```text
same fingerprint >= 2
    → fresh-context retry or alternate worker

same fingerprint >= 3
    → stop ordinary retry
    → Fable/root-cause orchestration review
```

Infinite expensive repair loops are forbidden.

---

## 18.1 PriorityOverride

A reproduced high-severity defect may pre-empt planned phase order.

```yaml
PriorityOverride:
  source_task:
  overriding_issue:
  severity:
  financial_impact:
  security_impact:
  blast_radius:
  persistence:
  justification:
  superseded_order:
  return_point:
```

Plan sequence never outranks an active money/security/system-integrity defect.

## 18.2 Context-safe recovery

Recovery may require a fresh WorkerSession when context is pressured. Resuming with a ContinuationPackage is preferred over forcing an exhausted session through the riskiest remaining work.


---

# 19. Multi-platform product manufacturing

A product feature is not complete because one vertical slice passes.

Each feature may span:

- backend;
- database;
- Android;
- iOS;
- web;
- admin/ERP;
- RBAC;
- security;
- offline/sync;
- analytics;
- notifications;
- visual/accessibility.

## 19.1 Shared contract spine

For cross-platform features, establish first:

- domain model;
- API;
- events;
- permissions;
- validation;
- errors;
- analytics;
- security constraints;
- interaction intent.

Then parallelize platform work.

## 19.2 Feature Completion Ledger

Example:

```text
Requirement semantics      PASS
Backend                    PASS
Database                   PASS
Android                    PASS
Web                        PASS
RBAC                       PASS
Security                   PASS
Accessibility              PASS
Visual                     PASS
Offline                    PASS
Analytics                  PASS
Negative cases             PASS
```

Only the required complete matrix yields `VERIFIED COMPLETE`.

---

# 20. Design Intelligence and Design Gateway architecture

REV 3 separates creative visual exploration, deterministic design-system conformance and real product implementation.

```text
requirements + references + current live state
        ↓
DesignGateDecision
        ↓
DesignIntent / DesignContextCompiler
        ↓
DesignGateway
        ↓
certified DesignProvider
        ├── ClaudeDesignAdapter
        └── future certified providers
        ↓
3–5 divergent DesignCandidates where policy permits
        ↓
DesignArtifact versions
        ↓
Try-Live implementation in isolated workspace
        ↓
real ProductEnvironment candidate
        ↓
branch / compare / refine
        ↓
human promotion gate
        ↓
ProductDesignAuthority + immutable design/code pair
        ↓
conformance implementation
        ↓
deterministic + accessibility + visual verification
        ↓
bounded repair
        ↓
evidence / ship eligibility
```

### 20.1 DesignProvider boundary

DDE defines a provider-neutral contract:

```text
DesignProvider
└── ClaudeDesignAdapter
    ├── provider-supported design operations
    ├── design-system synchronization
    ├── import/export/handoff
    └── optional interactive /design invocation
```

DDE does not bind its state machine to one preview command or provider UI.

### 20.2 DesignGateway responsibilities

`DesignGateway`:

- classifies whether a design stage is mandatory;
- compiles the design brief/context;
- enforces egress/minimum-context policy;
- routes to a certified provider;
- synchronizes approved design-system context;
- starts/resumes design sessions;
- versions candidates;
- captures comments/decisions;
- records promotion/rejection;
- creates implementation handoff;
- binds implementation to the selected design version;
- records provenance/provider identity;
- fails closed when a mandatory design capability is unavailable.

It does not decide Project Truth, merge code or skip verification.

### 20.3 Design Gate

Normally mandatory for:

- new screens/workflows;
- substantial redesigns;
- new navigation/information hierarchy;
- dashboards/onboarding/checkout;
- rebrands/design-system migrations;
- high-impact responsive adaptations;
- explicitly bespoke visual directions.

Policy-controlled bypass may apply to copy-only changes, layout-preserving bug fixes, accessibility corrections without redesign, deterministic component substitutions and tiny token-level corrections.

Every bypass creates an auditable `DesignGateDecision`.

### 20.4 DesignArtifact

A normalized artifact stores:

- project/task/session/provider/version/status;
- requirements/audience/target surfaces;
- design-system hash and allowed components/tokens;
- candidate refs/previews;
- selected candidate;
- human review and timestamp;
- structured handoff/asset manifest;
- provider/adapter/source-context provenance.

Promoted versions are immutable.

### 20.5 Design System Registry

Records component/token inventories, typography, spacing, semantic colors, assets, icon/motion policies, accessibility, breakpoints, hashes and provider-sync identifiers.

A stale design-system hash requires resynchronization or an explicit compatibility decision.

### 20.6 Design Skill Registry

External design skills/guidelines are immutable, pinned, licensed, scanned, evaluated and certified inputs. They advise design generation but never outrank ProductDesignAuthority or become merge-blocking oracles.

### 20.7 Design competition

Major surfaces may use multiple certified design configurations. Empirical design-routing telemetry records candidate quality, revision burden, verification success, latency and cost.

---

# 21. Visual verification

Visual verification evaluates the **real product**, not only prototype markup.

```text
build product
  ↓
start ProductEnvironment
  ↓
seed fixtures
  ↓
navigate workflow
  ↓
capture screenshots / traces
  ↓
DOM/layout/accessibility metrics
  ↓
multimodal critique
  ↓
VisualVerificationResult
```

Hard metrics include:

- clipping/overflow;
- tap target size;
- contrast;
- focus;
- token conformance;
- viewport integrity;
- alignment;
- spacing rhythm;
- truncation;
- responsive behavior;
- required-state coverage;
- reduced-motion semantics;
- screenshot diff;
- icon-family consistency.

Subjective rubric dimensions include:

- hierarchy;
- typography;
- composition;
- distinctiveness;
- interaction clarity;
- motion quality;
- believability;
- platform fidelity;
- brand coherence;
- professional polish.

A subjective score cannot override hard functional/accessibility failures.

Visual repair loops are bounded.

---

## 21.1 Design/code binding

Visual verification references both:

```text
promoted DesignArtifact version
+
exact promoted implementation revision
```

A beautiful design artboard is never accepted as proof of implemented software.

## 21.2 PreviewRuntimeAdapter

Platform-neutral contract:

```text
START
RELOAD
SET_STATE
SET_VIEWPORT
CAPTURE_SCREENSHOT
CAPTURE_STRUCTURE
CAPTURE_ACCESSIBILITY
REPORT_RUNTIME_ERROR
STOP
```

Implementations may use web fast refresh, Android incremental deploy/live-edit where certified, or deterministic incremental rebuilds.

## 21.3 Badges are semantic

- `DESIGN` — provider-rendered artboard/design artifact.
- `LIVE` — actual application code running from a candidate workspace.
- `VERIFIED` — live candidate that passed applicable gates.

These labels may not be used decoratively.


---

# 22. DDE Code and Frontend Studio are production tools

DDE Code is not a collection of agent dashboards.

Its primary UX is:

```text
Project
  → Mission
    → Product
      → Design
      → Work
      → Quality
      → Decisions
      → Evidence
```

Fleet/model detail is secondary.

The main interface must answer:

- what is being built;
- what is complete;
- what is blocked;
- what is executing;
- what changed;
- why a worker was selected;
- what failed;
- what requires attention;
- what evidence exists;
- whether the real product is closer to verified completion.

---

## 22.1 DDE-native orchestration studio

The operator surface additionally exposes the real manufacturing graph:

```text
Mission Overview
Execution Graph
Node Inspector
Design Review
Run Comparison
Workflow Library
Workflow Composer
```

These are projections/controls over DDE runtime state, never a parallel workflow database.


---

# 23. DDE Code visual identity — Precision Manufacturing Workbench

DDE Code adopts a distinct **product-tool** design register.

The design serves engineering work; decoration never outranks information.

## 23.1 Character

- precise;
- modern;
- technical;
- calm;
- trustworthy;
- dense but legible;
- visually distinctive without novelty for novelty's sake.

## 23.2 Composition

Prefer:

- structural rails;
- split panes;
- contextual inspectors;
- timelines;
- tables;
- evidence strips;
- compact status treatments;
- purposeful whitespace.

Avoid:

- dashboard card grids everywhere;
- glassmorphism;
- gradient decoration;
- giant marketing headers;
- pill spam;
- nested cards;
- empty decorative charts;
- generic SaaS hero grammar.

## 23.3 Visual system

REV 3 requires a new design-token version for DDE Code.

The existing token sheet remains historical until migration.

The new system must provide:

- multiple semantic surface levels;
- clear canvas/workbench/editor distinction;
- strong text hierarchy;
- disciplined one-accent identity;
- status colors used sparingly;
- one icon family;
- data/mono typography;
- accessible light/dark modes;
- reduced motion.

The DDE Code workbench may use a bundled/open-source professional font family only after licensing/provenance admission. A suitable direction is an engineering-oriented sans + mono pairing rather than Segoe UI as the entire identity.

## 23.4 UI architecture

The current string-rendered HTML surfaces remain temporary scaffolding.

REV 3 permits a componentized webview runtime after dependency EDR/admission.

Preferred approach:

```text
React + TypeScript + Vite
DDE generated CSS custom-property tokens
CSS Modules / authored CSS
no Tailwind/shadcn visual dependency
minimal third-party behavior dependencies
```

Rationale:

- Frontend Studio is now an IDE-class product surface;
- three-pane canvas/inspector/timeline workflows are expensive to maintain as giant HTML strings;
- both VS Code Webview and Electron can consume the same built assets;
- components become independently testable and visually verifiable.

No UI framework becomes authoritative state.

All mutations still go through the Gateway.

---

# 24. DDE Code information architecture

Top-level workbench:

```text
Projects
Missions
Product
Design
Quality
Decisions
Fleet
Evidence
Settings
```

## 24.1 App shell

Recommended desktop shell:

```text
┌───────────────────────────────────────────────────────────────────────────┐
│ DDE / Project / Mission        Command/Search        Core • Ready   User │
├──────┬────────────────────────────────────────────────────────────────────┤
│      │ context/sidebar                                             │      │
│ rail │                                                            │ insp │
│      │                    WORKBENCH                                │ ect  │
│      │                                                            │ or   │
│      │                                                            │      │
├──────┴────────────────────────────────────────────────────────────┴──────┤
│ Activity / Evidence / Verification drawer                               │
└───────────────────────────────────────────────────────────────────────────┘
```

## 24.2 Command palette

A global command palette is required for:

- project/mission navigation;
- create/stop/resume;
- open evidence;
- run verification;
- change design breakpoint;
- inspect route;
- approvals.

Keyboard-first interaction is first-class.

---

# 25. Frontend Studio V2 — live co-design and implementation workbench

Frontend Studio is a professional visual product-engineering workbench in which design intent and real implementation converge without surrendering DDE authority.

### 25.1 Primary modes

```text
Brief → Explore → References → Build → Motion → Verify → Ship
```

**Brief** — intent, requirements, design register, states, targets, active DesignAuthority.  
**Explore** — divergent design candidates/artboards, provenance, rationale, branch/reject/select.  
**References** — screenshots, URLs, video, donors, Figma/design refs, licenses and extracted design DNA.  
**Build** — structure/assets + real live canvas + contextual inspector + verification/activity drawer.  
**Motion** — selected-element/flow motion with governed tokens/contracts.  
**Verify** — viewport/state matrices, deterministic findings, visual diff, accessibility, VLM/critic evidence and repair history.  
**Ship** — readiness, remaining gates, sign-off, evidence bundle and merge eligibility.

### 25.2 Claude `/design` as a first-class capability

Claude Design is surfaced through a visible `Design with Claude` action, not hidden as CLI syntax. The durable boundary is the DDE DesignGateway.

Primary actions:

```text
[Design with Claude] [Try live] [Compare] [Promote] [Verify]
```

Provider identity is visible for provenance and operator choice.

### 25.3 The live-design loop

```text
real live canvas
  ↓ select screen/element
DesignEditContext
  ↓
DesignGateway / ClaudeDesignAdapter
  ↓
design candidate(s)
  ↓ Try live
LiveEditWorkspace
  ↓
certified implementation worker
  ↓
PreviewRuntimeAdapter
  ↓
REAL LIVE CANDIDATE
  ├── deterministic direct edit
  ├── ask design provider to refine
  ├── branch
  └── compare
  ↓
PROMOTE
  ↓
immutable design-version + code-revision pair
  ↓
VERIFY
  ↓
APPROVE / SHIP
```

The human promotion/sign-off gate is immutable. Exploratory micro-edits before promotion may iterate without approval spam inside the isolated workspace.

### 25.4 Three editing lanes

**Lane A — deterministic direct edit**

For known design-system changes: spacing, typography, semantic colors, alignment, legal component swap, visibility/state, copy and approved motion tokens. Inspector emits typed Gateway commands; no model call is required.

**Lane B — contextual AI design edit**

For aesthetic/ambiguous requests such as hierarchy, premium feel, density, reference adaptation or responsive recomposition. DDE sends only selected live context plus governed constraints. Returned candidates do not mutate accepted code until `Try live` / `Apply candidate`.

**Lane C — divergent design mode**

For new screens/major redesign:

```text
Design with provider
→ multiple artboards
→ compare/refine
→ select
→ Try live
```

### 25.5 Design Dock

The dock exposes:

- selected scope;
- current screen/state/viewport;
- design-system version;
- reference count;
- constraints;
- natural-language intent;
- modes: refine / alternatives / match reference / responsive adaptation / reseed.

It is not a raw chat-history dump.

### 25.6 Candidate strip

Every candidate has a semantic lifecycle:

```text
DESIGN
BUILDING
LIVE
LIVE · warnings
PROMOTED
VERIFIED
DISCARDED
```

### 25.7 Inspector integration

Tabs:

```text
Properties | Layout | Type | Appearance | Motion | Data | Provenance | Claude Design
```

The provider tab shows intent, session, candidate lineage, requirement coverage, design-system version, status and governed actions.

### 25.8 DesignEditContext

Selection uses stable element anchors and compiles a minimal normalized context:

```yaml
DesignEditContext:
  task_id:
  base_revision:
  target:
    screen_id:
    state_id:
    stable_anchor:
    scope:
  viewport:
    platform:
    breakpoint:
    width:
    height:
  visual_evidence:
    viewport_screenshot_ref:
    selected_crop_ref:
    surrounding_crop_ref:
    accessibility_snapshot_ref:
  structure:
    component_name:
    parent_anchor:
    child_anchors: []
    legal_drop_zones: []
  design_system:
    version:
    hash:
    allowed_components: []
    allowed_tokens: []
  requirements:
    requirement_refs: []
    mandatory_states: []
    accessibility_constraints: []
  references:
    approved_reference_refs: []
  code_scope:
    allowed_file_refs: []
    forbidden_file_refs: []
  user_intent:
```

Repository dumping is forbidden.

### 25.9 LiveEditWorkspace

`Try live` creates/reuses an isolated workspace:

```yaml
LiveEditWorkspace:
  live_edit_id:
  task_id:
  design_session_id:
  candidate_id:
  base_revision:
  workspace_ref:
  preview_runtime_ref:
  status: BUILDING | LIVE | FAILED | DISCARDED | PROMOTED
  patch_ref:
  render_ref:
```

The implementation bridge creates an ordinary governed TaskExecutionDescriptor and routes a certified worker. Design provider and coding worker may be the same vendor but remain separate DDE roles.

### 25.10 Bidirectional refinement

The next design request may use the **actual current live candidate** after deterministic inspector edits. This enables:

```text
real live state → design provider → candidate → real live state → design provider ...
```

### 25.11 Direct manipulation law

- known token/component edits compile deterministically;
- drag/resize is interpreted as semantic intent/legal layout operation;
- arbitrary inline style generation is not the default;
- freeform composition can be delegated to design generation;
- provider changes are normalized against the design system before implementation.

### 25.12 Provider canvas policy

DDE does not depend on iframe/native embedding. Provider surface modes may include:

```text
NATIVE_EMBED        optional if officially/security supported
EXTERNAL_EDITOR     provider artifact editor
DDE_CANDIDATE_VIEW  required fallback
```

DDE's live canvas remains authoritative for real application state.

### 25.13 No second mutation path

Raw commands move to a developer/debug drawer. Normal typed controls compile into the exact same Gateway/API/MCP command path. UI convenience never bypasses Core.

---

# 26. Mission Workspace, Execution Graph and workflow control

The Mission Workspace presents one coherent operational view of a mission rather than a collection of agent chats.

### 26.1 Execution Graph

The graph is projected from actual TaskGraph/WorkerSession/DesignSession/events/evidence.

It must show:

- dependencies;
- parallelism;
- retries;
- fallbacks;
- human gates;
- strategic desired/configured/serving-model state and attested-orchestrator transitions where supported;
- design branches;
- verification nodes;
- integration nodes;
- terminal outcomes.

There is no manually maintained duplicate graph truth.

### 26.2 Node Inspector

Every executable node can expose, subject to security policy:

- normalized inputs;
- context manifest and hashes;
- routing candidates and decision evidence;
- worker/model/harness/provider identity;
- effective configuration hash;
- tool/capability events;
- workspace/change packet;
- artifacts and diff;
- costs/usage;
- validation/verification;
- failure/recovery state.

Hidden chain-of-thought is neither required nor persisted.

### 26.3 Localized runtime actions

Governed controls may include:

```text
replay exact
reroute
fork
compare
retry bounded
cancel
resume
open evidence
```

Every action preserves lineage and policy gates.

### 26.4 Run Comparison

Compare worker/design/workflow variants by:

- verified outcome;
- changed artifacts;
- evidence;
- cost;
- latency;
- rework;
- human intervention;
- failure signatures.

### 26.5 Workflow Registry / Playbooks

Reusable workflows are versioned capability-oriented definitions, not fixed model macros.

Candidate lifecycle:

```text
observed successful pattern
→ candidate
→ offline evaluation
→ shadow/canary
→ promoted playbook
→ versioned/revocable/deprecated
```

Hermes can discover candidates; DDE promotes them.

### 26.6 Workflow Composer

A visual composer may author graphs, but it is a **compiler front-end to DDE's validated workflow model**, not an orchestrator.

Requirements:

- illegal edges blocked;
- mandatory gates not deletable without policy authorization;
- capability satisfiability checked before execution;
- nodes express capabilities/constraints rather than gratuitous provider pinning;
- Project Truth cannot be mutated merely by drawing a memory/agent node;
- compiled workflow produces the same authoritative runtime objects/events as non-visual authoring.

### 26.7 DDE-native Opal adoption rule

Adopt the high-value concepts—clarity, real execution graph, node-level observability, replay/reroute/fork/compare, reusable playbooks and visual composition—without adopting Opal as a runtime dependency or second source of orchestration truth.

---

# 27. Route explainability

Every persisted route decision is renderable without model-generated explanation.

The UI shows:

- hard gates;
- selected profile/model;
- expected verified success;
- expected cost/latency/rework;
- quota state;
- alternatives;
- exclusion reasons;
- policy version.

This becomes the `Why this route?` panel.

---

# 28. Attention Budget

Human attention is a governed resource.

Classes:

```text
IMMEDIATE
REVIEW_QUEUE
DAILY_SUMMARY
INFORMATIONAL
```

Immediate interruption is reserved for:

- destructive operations;
- security/privacy/payment risk;
- unreconciled external side effects;
- systemic architecture contradiction.

Routine completion does not interrupt the operator.

---

# 29. Dogfooding law

DDE must eventually use its own design/verification pipeline to develop DDE Code.

Bootstrap sequence:

1. owner ratifies Frontend Studio V2 DesignAuthority manually;
2. DDE-068 visual verification becomes operational;
3. Studio V2 is rebuilt using that authority;
4. subsequent DDE Code UI changes go through the same design gates as generated products.

This prevents a design engine whose own interface is exempt from its quality rules.

---

# 30. Security, data egress and executable supply-chain invariants

External agent/design skills, MCPs, plugins, harnesses and design providers are supply-chain inputs.

### 30.1 Immutable admission

Every executable version is:

- source-identified and hash-pinned;
- license-classified;
- prompt-injection/tool-scope scanned where applicable;
- capability-scoped;
- evaluated;
- certified.

Workers launch with explicit skills, MCPs, plugins, tools, network policy, environment variables, model and context package. Ambient developer-home configuration is never reproducible production configuration.

### 30.2 No personal-data export

DDE's no-personal-data-export constraint applies at every provider gateway. A design or coding provider receives only the minimum approved code/design/task context.

Secrets, user records, production data, credentials, private unrelated documents and unrelated repository content are not transmitted for convenience.

### 30.3 Egress ledger

Externally transmitted context records:

- provider;
- task/session;
- allowlisted paths/artifacts;
- redactions;
- data classification;
- policy version;
- source hashes;
- timestamp.

### 30.4 Managed updates — no blind auto-update

Hermes, Claude Code, Codex harnesses, DeepSeek, MCP servers, skills, plugins and other executable components may not silently replace active certified versions.

`ToolUpdateManager` lifecycle:

```text
CURRENT
→ UPDATE_AVAILABLE
→ DOWNLOADED
→ QUARANTINED
→ CERTIFYING
→ CERTIFIED_CANDIDATE
→ CANARY
→ PROMOTED
```

Failure branches to rejected/rollback.

Risk classes:

- **A:** non-executable metadata/content — lighter checks;
- **B:** bounded executable components — contract tests + canary;
- **C:** core runtime/control-plane components — full certification, stronger approval and rollback proof.

Historical performance remains keyed to exact old versions. A new version inherits only a cautious discounted prior.

---

# 31. Health semantics

`healthy` must not mean only "adapter object exists".

Health dimensions include:

```text
installation_present
protocol_ready
auth_valid
provider_reachable
profile_certified
quota_available
toolchain_ready
environment_ready
```

A fail-closed policy shell is not represented as a live executable worker in normal product UX.

---

## 31.1 Project/session bootstrap health

A healthy worker session additionally requires:

```text
project_identity_valid
runtime_root_authorized
bootstrap_receipt_pass
effective_configuration_reconstructable
configured_model_truthful
serving_model_claim_evidence_valid_or_explicitly_unknown
context_budget_safe
```

An adapter object existing in memory is never sufficient health proof.

A session can be healthy while `SERVING=unknown`; what is forbidden is representing that unknown as an attested model. Model-specific orchestration certification requires sufficient serving-model evidence for the task's risk policy.

## 31.2 Tool update health

A newer available version does not make the active certified version unhealthy. Promotion occurs only after update certification; failed candidates leave the stable version active.


---

# 32. Capability-realization status

Every major capability exposes:

```text
SPECIFIED
CONTRACTED
WIRED
EXECUTABLE
OBSERVABLE
VERIFIED
```

Example:

```text
Claude Path A
SPECIFIED      yes
CONTRACTED     yes
WIRED          yes
EXECUTABLE     yes
RESUMABLE      no
ROUTABLE       no
USAGE_REAL     no
VERIFIED       limited
```

A chapter gate must identify the highest truthful state achieved.

---

# 33. Definition of done for DDE missions

A mission cannot be declared complete based only on tests or documentation.

It must answer:

## Contract

- authoritative shape?
- versioning?
- owner/source?

## Mutation

- exact production writer?
- idempotency?
- transaction boundary?

## Read

- exact production reader?
- Gateway/operator accessibility?

## Runtime

- non-test execution path?

## Evidence

- real evidence rather than placeholders?

## Failure

- typed failure and recovery?

## UX

- real state displayed without fabrication?

## Integration

- real end-to-end path verified?

## Drift

- documentation/UI cannot overclaim capability?

If the answer is not yes, the capability remains partial and is named.

---

# 34. REV 3 migration and operational-safety principles

REV 3 is evolutionary. Do not rebuild working DDE Core or erase evidence to satisfy the new architecture.

### 34.1 Preserve

Do not:

- delete working mission/task/evidence infrastructure;
- replace deterministic governance with an agent;
- bypass existing Gateway command paths;
- invalidate durable evidence wholesale;
- renumber DDE-068 through DDE-083;
- re-audit already verified work unless a dependency/invariant invalidates its evidence;
- introduce parallel sources of truth.

Do:

- add missing runtime producers/consumers;
- converge duplicate registries;
- add project/bootstrap identity;
- add durable sessions and continuation;
- wire real telemetry;
- add packet-scoped mutation governance;
- improve truthful UI projections;
- absorb addenda into canonical docs;
- migrate incrementally behind tests and chapter gates.

### 34.2 REV-3A Operational Safety Gate

Before further numbered product work after canonical consolidation, apply a short repository/runtime-safety gate with these required outcomes:

- project identity enforcement;
- no unrelated-root configuration contamination;
- explicit desired/configured/serving orchestrator-model state;
- control-level and serving-model attestation disclosure;
- Fable/Opus next-session fallback/restoration semantics for config-only runtimes and true occupancy semantics only for attested runtimes;
- worker-pool eligibility rules;
- context checkpoint rule;
- packet-scoped mutable work;
- rejected-work disposition;
- staging-scope guard;
- continuation checkpoint format;
- evidence inheritance / no blanket re-audit.

This gate does **not** renumber DDE-068…DDE-083.

### 34.3 Historical source disposition

The original Rev 3.0 blueprint, Rev 3 quantum audit, Rev 3.1 amendment and Claude Design/Opal integration addendum remain historical evidence. Once consolidated decisions are adopted here, implementation agents must not treat those documents as separate forward authorities.

---

# 35. Consolidation source ledger

This canonical edition incorporates the following source classes:

### 35.1 Repository baseline

Audited/current repository areas include:

- `README.md`, `AGENTS.md`;
- `docs/truth/**`;
- legacy `docs/blueprint/historical/REV_2_0.md`;
- Frontend Studio planning/charters/chapter gates;
- planning/routing/worker registries;
- Worker Manager;
- studio compiler/frontend;
- Claude/Cursor and other adapters;
- DDE Studio shared UI;
- design-token schemas;
- verification and evidence services.

### 35.2 Rev 3 source material

- original DDE Blueprint Rev 3.0;
- DDE Rev 3 Development & Realisation Plan;
- DDE Quantum Audit / Implementation & Design Intelligence Blueprint;
- canonical Rev 3 resume/bootstrap discipline.

### 35.3 Rev 3.1 operational-hardening material

Absorbed decisions include:

- project identity before configuration;
- dynamic role occupancy;
- adaptive worker-configuration routing;
- Hermes execution-experience intelligence;
- provider capacity/reset economics;
- context budgets/continuations;
- ChangePackets/rejection/staging scope;
- evidence inheritance/delta audit;
- managed tool updates;
- REV-3A safety gate;
- desired/configured/serving model separation;
- OCL-0…OCL-3 orchestrator-control certification;
- `ModelServingEvidence` and model-attestation honesty;
- truthful interpretation of current Claude Code model-tier configuration as next-session intent rather than live-session control.

### 35.4 Frontend/design integration material

Absorbed decisions include:

- DesignGateway/provider-neutral DesignProvider;
- Claude `/design` as a first-class Frontend Studio capability;
- live design/code loop;
- DesignArtifact/Design System Registry;
- ARTBOARD vs LIVE vs VERIFIED semantics;
- execution graph/node inspector;
- replay/reroute/fork/compare;
- reusable workflows/playbooks;
- DDE-native Workflow Composer;
- Opal as inspiration only, not runtime authority.

### 35.5 Authority note

External source links/research explain feasibility and inspiration but do not outrank accepted DDE Project Truth or this consolidated architecture.

---

# 36. Final architectural statement

DDE Rev 3's consolidated target is:

> **DDE owns truth, state, policy, admissibility, lineage and evidence. Project identity is established before configuration. Strategic model control is represented truthfully as desired, configured/requested and serving state: Fable is the preferred strategic model, Opus is the initial fallback when selected, but DDE claims live role occupancy only to the level the exact harness/runtime can actually control and attest. Configured is never silently upgraded to serving. When Fable is genuinely active, Opus remains a normal subordinate worker candidate; when Opus genuinely occupies the strategic seat it leaves conflicting subordinate eligibility, and when Fable is restored Opus returns to the ordinary worker pool. All bounded work is routed across certified worker configurations according to capabilities and verified historical performance. Hermes remembers, retrieves and discovers patterns but never becomes routing or truth authority. Every code mutation belongs to a ChangePacket, every rejection has a disposition, every controlled commit proves staged scope, and prior evidence is inherited until a changed dependency specifically invalidates it. Context, provider quota, serving-model evidence and executable-tool versions are governed runtime resources. Frontend Studio exposes Claude `/design` through a DDE-owned DesignGateway and closes a bidirectional loop between design artifacts and real isolated live application candidates; provider artboards are never mislabeled as implementation. The same real runtime is projected as an execution graph, node inspector, run comparison, workflow library and policy-compiled Workflow Composer. Deterministic and independent verification decide completion.**

That is the single canonical human-readable architecture for DDE Rev 3.

---

# Appendix A — Canonical runtime object catalogue

The following objects are first-class or required target contracts. Names may map to existing schemas/services where already implemented; do not create duplicates solely to match this list.

| Domain | Canonical objects |
|---|---|
| Identity/bootstrap | `ProjectIdentity`, `RuntimeRoot`, `SessionBootstrapContract`, `EffectiveExecutionConfiguration`, `BootstrapReceipt` |
| Mission/planning | `Mission`, `TaskGraph`, `PlanDraft`, `OrchestratorModelState`, `ModelServingEvidence`, `StrategicOrchestratorLease`, `RoleTransition`, `PriorityOverride` |
| Execution | `TaskExecutionDescriptor`, `ExecutionStrategy`, `WorkerSession`, `WorkerRun`, `WorkspaceLease`, `ChangePacket` |
| Change governance | `DeclaredWriteSet`, `RejectionDisposition`, `StagingManifest`, `CommitManifest`, `WriteOwnershipGraph` |
| Fleet | `HarnessInstallation`, `HarnessRuntimeCapabilities`, `ModelControlCapabilities`, `WorkerConfiguration`, `WorkerProfileCertification`, `ProviderCapacitySnapshot` |
| Context | `ContextPackage`, `ContextBudget`, `ContinuationPackage` |
| Evidence | `VerificationRun`, `Evidence`, `EvidenceValidityGraph`, `RegressionInvalidationGraph`, `DeltaAuditPlan` |
| Learning | `ExperienceRecord`, `ExperienceContext`, `RoutingInsightCandidate`, `EscalationPolicy` |
| Design | `DesignGateDecision`, `DesignSession`, `DesignEditContext`, `DesignArtifact`, `DesignSystemRegistry`, `LiveEditWorkspace`, `ProductDesignAuthority` |
| Preview | `PreviewRuntimeAdapter`, render/accessibility/structure evidence |
| Workflow UX | `ExecutionGraphProjection`, `NodeInspectionRecord`, `WorkflowDefinition`, `WorkflowPlaybook`, `WorkflowCandidate` |
| Updates | `ToolUpdateCandidate`, `ToolUpdateCertification`, rollback/promotion records |

## A.1 Contract non-duplication rule

If an existing accepted object already owns the domain, extend it through schema/change control rather than minting a parallel concept.

---

# Appendix B — Cross-cutting event taxonomy

At minimum DDE must be able to represent durable events for:

```text
ProjectResolved
BootstrapPassed / BootstrapFailed
OrchestratorModelDesired / OrchestratorModelConfigured / ServingModelAttested / ServingModelUnknown / ServingModelMismatch
RoleAcquired / RoleReleased / RoleRepromotionPending
PlanProposed / PlanValidated / PlanRejected / PlanPromoted
RouteEvaluated / WorkerSelected / RouteFallback
SessionOpened / SessionPaused / SessionResumed / SessionClosed
ContextPressure / ContinuationCreated
ChangePacketOpened / ChangePacketAccepted / ChangePacketRejected / RejectionDispositioned
StageVerified / CommitBlocked / CommitAccepted
DesignRequested / DesignCandidatesReady / CandidateTriedLive / DesignPromoted
PreviewStarted / PreviewReloaded / RuntimeError
VerificationStarted / VerificationPassed / VerificationFailed
EvidenceInvalidated / EvidenceInherited
ProviderCapacityChanged / ResetObserved
ExperienceRecorded / RoutingInsightProposed / PolicyPromoted
ToolUpdateDetected / ToolUpdateCertified / ToolUpdatePromoted / ToolRollback
```

Provider-native events are normalized into DDE events and never become Core contracts directly.

---

# Appendix C — Dial depth-and-breadth capability closure matrix

A feature can be called `VERIFIED` only when all applicable questions have evidence.

| Dimension | Required proof |
|---|---|
| Authority | One owner/source of mutable truth is named. |
| Contract | Versioned schema/typed boundary exists. |
| Mutation | Exact writer, idempotency and transaction/side-effect boundary are known. |
| Read | Exact reader/API/Gateway path exists. |
| Runtime | Non-test production execution path is exercised. |
| State | Legal transitions, terminal states and retries are defined. |
| Failure | Typed failure, cancellation, recovery and reconciliation are defined. |
| Security | Capability, secret, network, data-egress and tenant/project scope are enforced. |
| Evidence | Real output/verification is persisted and attributable. |
| UX | Operator/client sees honest states and can perform permitted actions. |
| Observability | Events, usage, cost, latency and provenance are inspectable. |
| Runtime truth/attestation | Requested/configured state is distinguished from observed/attested runtime state; unknown remains unknown. |
| Learning | Any adaptive use is evidence-gated and cannot self-promote. |
| Migration | Existing implementation/evidence is retained or explicitly superseded. |
| Tests | Unit/contract/integration/e2e/chaos coverage is appropriate to risk. |
| Drift | Docs/UI cannot overclaim the actual realization state. |

States remain:

```text
SPECIFIED → CONTRACTED → WIRED → EXECUTABLE → OBSERVABLE → VERIFIED
```

A planning document alone never advances a capability beyond `SPECIFIED`.

# Appendix D — Canonical capability traceability and realization model

This appendix is **normative**. It converts the Dial depth-and-breadth rule from prose into a mandatory traceability contract. No capability may be promoted to `VERIFIED` unless DDE can resolve the complete chain below from durable identifiers and evidence.

```text
Project Truth / accepted EDR
        ↓
RequirementAtom
        ↓
Capability
        ↓
AcceptanceCriterion
        ↓
Command / Query / API / Event / Data Contract
        ↓
Owner Service / Adapter / Projection
        ↓
Production Call Site
        ↓
State Transition / Side Effect
        ↓
ChangePacket / WorkerRun
        ↓
VerificationRun
        ↓
Evidence
        ↓
CapabilityCertification
        ↓
Release / Product Surface
```

## D.1 Stable identifiers

Every durable traceable object uses a stable identifier that survives refactors and presentation changes.

Minimum identifier families:

```text
REQ-*      RequirementAtom
CAP-*      Capability
AC-*       AcceptanceCriterion
CMD-*      CommandContract
QRY-*      QueryContract
API-*      ApiContract
EVT-*      EventContract
DAT-*      DataContract / authoritative entity
SM-*       StateMachine
FAIL-*     FailureContract
SEC-*      SecurityControl
OBS-*      ObservabilityContract
SLO-*      ServiceLevelObjective / engineering budget
SURF-*     Product/OperatorSurface
TEST-*     VerificationScenario
MIG-*      MigrationContract
CERT-*     CapabilityCertification
```

Identifiers are semantic references, not file paths. Refactoring a module does not silently create a new capability identity.

## D.2 CapabilityTrace contract

DDE shall expose a generated/readable projection equivalent to:

```yaml
CapabilityTrace:
  capability_id:
  title:
  authority_refs: []
  requirement_refs: []
  acceptance_refs: []
  realization_state: SPECIFIED | CONTRACTED | WIRED | EXECUTABLE | OBSERVABLE | VERIFIED
  owner:
    service:
    module:
    team_or_role:
  contracts:
    commands: []
    queries: []
    apis: []
    events: []
    data: []
    state_machines: []
    failures: []
    security_controls: []
    observability: []
    service_budgets: []
  production_paths:
    writers: []
    readers: []
    call_sites: []
    adapters: []
  surfaces: []
  migrations: []
  verification_scenarios: []
  evidence_refs: []
  certification_ref:
  inherited_evidence_refs: []
  invalidated_evidence_refs: []
  residuals: []
```

The persisted source may be normalized across several tables/files. The **projection must be reconstructable** without a model inferring missing links.

## D.3 Traceability laws

1. No accepted requirement may exist without at least one owning capability or an explicit `DEFERRED/REJECTED` disposition.
2. No capability may exist without an authority reference.
3. No mutating UI action may exist without a command contract.
4. No operator-visible state may be fabricated from local UI-only state when an authoritative projection exists.
5. No production writer may be unowned.
6. No external side effect may occur without an auditable command/attempt/side-effect lineage.
7. No event may be emitted without a versioned event contract and named owner.
8. No stored authoritative field may be introduced without a data owner, lifecycle and migration rule.
9. No capability may be labelled `VERIFIED` without a current certification whose evidence remains valid.
10. No generated trace projection may become a third human architecture source of truth; it is a machine-derived projection of accepted contracts and runtime evidence.

## D.4 Realization-state transition evidence

### `SPECIFIED → CONTRACTED`

Requires:

- authority and requirement references;
- acceptance criteria;
- owning service/domain;
- typed command/query/API/event/data boundaries as applicable;
- state/failure/security semantics;
- migration disposition.

### `CONTRACTED → WIRED`

Requires:

- production writer/reader bindings;
- real Gateway/API/MCP/UI call sites;
- adapter registration where external capability is involved;
- dependency injection/registry binding;
- no test-only seam presented as production wiring.

### `WIRED → EXECUTABLE`

Requires:

- non-test execution through the real owner;
- durable state transition or real read result;
- idempotency and side-effect semantics exercised;
- typed failure path exercised;
- real environment identity captured.

### `EXECUTABLE → OBSERVABLE`

Requires:

- event/trace correlation;
- metrics or usage telemetry appropriate to the capability;
- operator-visible truthful state;
- provenance and failure reason inspectable;
- service-budget measurements where applicable.

### `OBSERVABLE → VERIFIED`

Requires:

- acceptance criteria mapped to verification scenarios;
- independent/deterministic evidence appropriate to risk;
- security and migration evidence where relevant;
- current evidence-validity result;
- `CapabilityCertification` recorded.

## D.5 Requirement and capability closure query

At Rev 3 release-candidate stage DDE must answer, without model guesswork:

```text
show requirement REQ-x
→ owning CAP-y
→ current realization state
→ exact commands/queries/contracts
→ code owners/call sites
→ current state machine/failure contracts
→ security/egress controls
→ tests and latest verification evidence
→ evidence validity
→ exposed surfaces
→ release eligibility / residuals
```

The inverse query must also work: from a code owner, API, event, UI action or evidence item, resolve the requirements/capabilities it serves.

---

# Appendix E — Command, query, API, event and data contract atlas

This appendix is **normative** for all newly introduced or materially changed capabilities.

## E.1 Command contract

Every state-changing operation has one command owner and an envelope equivalent to:

```yaml
CommandEnvelope:
  command_id:
  command_type:
  schema_version:
  project_id:
  actor:
    actor_type:
    actor_id:
    capability_grants: []
  correlation_id:
  causation_id:
  idempotency_key:
  expected_revision:
  payload:
  policy_context:
  issued_at:
```

Command handling must define:

- authorization point;
- validation point;
- idempotency scope and retention;
- optimistic/pessimistic concurrency rule;
- transaction boundary;
- side-effect journal/outbox behavior;
- success result;
- typed rejection/failure result;
- emitted events;
- audit record.

A UI, CLI, model, harness or adapter may request a command. None may bypass its owner.

## E.2 Query contract

Read paths use explicit projections rather than ad-hoc table access from clients.

```yaml
QueryEnvelope:
  query_id:
  query_type:
  schema_version:
  project_id:
  actor:
  correlation_id:
  consistency_requirement: STRONG | BOUNDED_STALE | EVENTUAL
  filters:
  pagination:
  projection_version:
```

Each query names:

- source projection/owner;
- authorization and redaction rules;
- consistency semantics;
- pagination/cursor semantics where collections are possible;
- freshness indicator when stale data can affect decisions;
- error/degraded response contract.

## E.3 API contract

Gateway/API boundaries must provide:

- versioning/compatibility policy;
- authentication and authorization;
- correlation/trace identifiers;
- request size and timeout budgets;
- idempotency for mutations;
- typed error bodies;
- rate/abuse controls where externally reachable;
- pagination for unbounded collections;
- explicit deprecation and removal window;
- generated contract tests.

Provider-native APIs are translated by adapters. They never leak provider-specific state into Core contracts unless intentionally normalized.

## E.4 Event envelope

Durable events use an envelope equivalent to:

```yaml
DdeEvent:
  event_id:
  event_type:
  schema_version:
  project_id:
  aggregate_type:
  aggregate_id:
  aggregate_revision:
  correlation_id:
  causation_id:
  producer:
  occurred_at:
  recorded_at:
  payload:
  sensitivity:
```

Event requirements:

- at-least-once delivery is assumed unless a transport explicitly proves stronger semantics;
- consumers are idempotent;
- duplicate and out-of-order handling is defined;
- event schema compatibility is tested;
- poison/dead-letter handling is observable;
- replay does not repeat irreversible side effects;
- projection rebuilds are distinguishable from new business events.

## E.5 Data ownership

Every authoritative entity/aggregate declares:

```yaml
DataOwnership:
  data_contract_id:
  owner_service:
  authoritative_store:
  primary_key:
  project_scope:
  sensitivity:
  retention:
  mutable_by: []
  read_by: []
  indexes: []
  invariants: []
  migration_strategy:
  backup_class:
  deletion_or_tombstone_rule:
```

Rules:

1. One domain owns writes to an authoritative aggregate.
2. Cross-domain reads occur through supported projections/contracts, not shared-table mutation.
3. Every cent, token, quota unit, attempt, design promotion, evidence decision and external effect represented by DDE must remain attributable to an owner and lineage.
4. Derived projections may be rebuilt; authoritative evidence/truth history may not be silently rewritten.
5. Schema changes require forward/backward migration semantics and evidence-impact analysis.

## E.6 Transaction and side-effect boundary

For commands that touch both Core state and an external system:

```text
validate + authorize
→ record intended transition / outbox or side-effect journal
→ commit authoritative state
→ execute effect through certified adapter
→ persist effect result
→ reconcile ambiguity
→ emit normalized outcome event
```

A network timeout after an external request is an **ambiguous effect**, not automatically a failure or automatic retry. Reconciliation must determine whether the effect occurred before replaying.

---

# Appendix F — Canonical state-machine atlas

Every durable runtime object with non-trivial lifecycle must expose a state machine, legal transitions, transition authority and terminal semantics. String labels without transition rules are insufficient.

## F.1 Universal state-machine rules

Each state machine declares:

- stable aggregate identifier;
- state enum and schema version;
- legal transitions;
- command(s) permitted in each state;
- actor/capability permitted to request each transition;
- guard conditions;
- durable event emitted;
- timeout/deadline behavior;
- retry/recovery behavior;
- terminal states;
- reconciliation path for ambiguous transitions;
- migration behavior when state schema changes.

Illegal transitions fail closed and are recorded as rejected attempts when operationally relevant.

## F.2 Bootstrap state machine — `SM-BOOTSTRAP`

```text
UNRESOLVED
  → IDENTITY_RESOLVED
  → CONFIG_COMPILED
  → PREFLIGHTING
  → PASS

UNRESOLVED / IDENTITY_RESOLVED / CONFIG_COMPILED / PREFLIGHTING
  → FAIL

PASS
  → EXPIRED / INVALIDATED
```

No worker session or controlled mutation may start without a non-expired `PASS` BootstrapReceipt bound to the same project/runtime root/effective configuration.

## F.3 Orchestrator model state and strategic lease

### `SM-ORCHESTRATOR-MODEL`

```text
UNKNOWN
→ DESIRED
→ CONFIGURED

CONFIGURED
→ REQUESTED_UNATTESTED
→ SERVING_ATTESTED
→ MISMATCH

REQUESTED_UNATTESTED
→ SERVING_ATTESTED | MISMATCH | CLOSED

SERVING_ATTESTED
→ REPROMOTION_PENDING | FALLBACK_PENDING | CLOSED
```

`CONFIGURED` never implies `SERVING_ATTESTED`.

### `SM-STRATEGIC-LEASE`

For OCL-0/OCL-1/OCL-2:

```text
REQUESTED
→ REQUESTED_UNATTESTED
→ RELEASED | FAILED
```

For OCL-3:

```text
REQUESTED
→ ACTIVE_ATTESTED
→ REPROMOTION_PENDING
→ RELEASED

REQUESTED
→ FALLBACK_ACTIVE_ATTESTED
→ REPROMOTION_PENDING
→ RELEASED

ACTIVE_ATTESTED / FALLBACK_ACTIVE_ATTESTED
→ FAILED
```

Lease transfer occurs only at a safe atomic checkpoint. A strategic occupant cannot remain simultaneously eligible for ordinary subordinate work in the same protected scope if policy forbids dual occupancy. An OCL-1 configuration change must never be recorded as a live lease transfer.

## F.4 Worker session — `SM-WORKER-SESSION`

```text
CREATED
→ BOOTSTRAPPED
→ READY
→ RUNNING
→ CHECKPOINTING
→ PAUSED
→ RESUMING
→ RUNNING
→ COMPLETED
```

Alternate exits:

```text
READY/RUNNING/CHECKPOINTING/PAUSED/RESUMING
→ CANCELLED | FAILED | EXPIRED
```

A failed/expired session may produce a continuation but may not pretend to have completed an in-flight task.

## F.5 ChangePacket — `SM-CHANGE-PACKET`

```text
DECLARED
→ OPEN
→ IMPLEMENTED
→ VERIFYING
→ ACCEPTED
→ STAGED
→ COMMITTED
```

Alternate paths:

```text
OPEN/IMPLEMENTED/VERIFYING
→ REJECTED
→ DISPOSITION_REQUIRED
→ DISPOSITIONED

OPEN/IMPLEMENTED/VERIFYING/ACCEPTED/STAGED
→ CANCELLED
```

`REJECTED` is not terminal until mutations are dispositioned. `STAGED` requires exact accepted write-set verification.

## F.6 Design candidate — `SM-DESIGN-CANDIDATE`

```text
REQUESTED
→ DESIGN_READY
→ TRY_LIVE_PENDING
→ LIVE_CANDIDATE
→ COMPARED
→ PROMOTED
→ VERIFYING
→ VERIFIED
```

Alternate paths:

```text
DESIGN_READY/LIVE_CANDIDATE/COMPARED
→ REJECTED | SUPERSEDED

PROMOTED/VERIFYING
→ VERIFICATION_FAILED
```

`DESIGN_READY` is never `LIVE`. `PROMOTED` is not `VERIFIED`.

## F.7 Verification — `SM-VERIFICATION`

```text
REQUESTED
→ RUNNING
→ PASSED | FAILED | INCONCLUSIVE | BLOCKED
```

A provider/tool failure may produce `INCONCLUSIVE/BLOCKED`; it must not be converted into `PASSED` because the implementation appears plausible.

## F.8 Workflow run — `SM-WORKFLOW-RUN`

```text
CREATED
→ VALIDATED
→ READY
→ RUNNING
→ PAUSED
→ RUNNING
→ COMPLETED
```

Alternate paths:

```text
VALIDATED/READY/RUNNING/PAUSED
→ CANCELLED | FAILED
```

Fork/reroute/replay create new lineage-aware run/attempt records; they do not rewrite the original run history.

## F.9 Tool update — `SM-TOOL-UPDATE`

```text
DETECTED
→ QUARANTINED
→ CERTIFYING
→ CERTIFIED
→ CANARY
→ PROMOTED
```

Alternate paths:

```text
QUARANTINED/CERTIFYING/CANARY
→ REJECTED

PROMOTED
→ ROLLBACK_REQUIRED
→ ROLLED_BACK
```

An update may not transition directly from `DETECTED` to `PROMOTED` for executable components in the governed toolchain.

---

# Appendix G — Failure, recovery and eventuality matrix

A feature is incomplete if it specifies only the happy path. The following classes are mandatory baseline eventualities; each implementing mission must bind them to typed errors, operator states, events and tests.

| Failure/eventuality | Required behavior | Forbidden behavior | Evidence required |
|---|---|---|---|
| Wrong/unregistered project root | Fail bootstrap closed; identify mismatch; no session start | Inherit nearest config or continue with warning | bootstrap contract test + audit event |
| Stale/invalid bootstrap receipt | Re-resolve identity/config and require new receipt | Continue using stale effective config | expiry/invalidation test |
| Fable unavailable/exhausted | OCL-1: configure next session for fallback and disclose serving unknown; OCL-3: acquire attested fallback lease by policy | Claim the running parent changed model because settings changed; make Opus orchestrator and universal worker | configured-state + serving-evidence/control-level + pool-eligibility evidence |
| Fable returns mid-task | OCL-1: configure next session Fable-preferred; OCL-3: mark repromotion pending and transfer at atomic checkpoint | Claim Fable active from reset/config alone; interrupt unsafe mutation or keep attested fallback indefinitely | transition/control-level/attestation recovery test |
| Serving model unavailable/unattested | Preserve `SERVING=unknown`; disclose limitation; route bounded attested worker packet where policy permits | Infer serving model from `settings.json`, startup preference or model-tier state | ModelServingEvidence/unknown-state test |
| Provider quota/health unknown | Treat capacity with uncertainty penalty or ineligible by risk policy | Assume healthy/unlimited | capacity provenance + route reason |
| Provider request timeout | Classify retryability/ambiguity; reconcile where side effect possible | Blind retry irreversible actions | failure/reconciliation evidence |
| Worker crash | Persist last durable state; cancel/expire leases; resume from continuation if safe | Mark task complete from partial output | crash/recovery integration test |
| Context pressure | Checkpoint before unsafe work; create ContinuationPackage | Continue high-risk work beyond budget | context-threshold test |
| Context package stale | Recompile affected context slices and record provenance | Reuse stale assumptions silently | freshness/invalidation evidence |
| Workspace contamination | Quarantine or fail packet; compute unexpected diff | Sweep changes into current packet | contamination test |
| Rejected packet mutations | Require disposition and protect later staging | Leave anonymous mutations in shared tree | rejection-disposition test |
| Broad staging attempt | Block unless explicit bulk-maintenance authorization | `git add -A` ordinary packet | staging-scope test |
| Merge conflict | Rebase/reconcile under new packet or controlled continuation | Resolve by discarding unrelated accepted work | conflict lineage evidence |
| Evidence dependency changed | Invalidate only dependent evidence | Blanket re-audit or retain invalid evidence | EvidenceValidityGraph test |
| Evidence missing/corrupt | Mark certification incomplete; recover from immutable store if possible | Reconstruct PASS from memory/chat | integrity test |
| Design provider unavailable | Wait/degrade/route approved alternate according to DesignGateDecision | Silently bypass mandatory design gate | design-provider outage test |
| Artboard generation succeeds but Try-Live fails | Keep design artifact; mark live implementation failed | Label artboard LIVE | design/live semantic test |
| Product preview crashes | Surface runtime failure and preserve logs/state | Show stale screenshot as live | preview recovery test |
| Visual critic unavailable | Apply policy: deterministic-only if allowed, otherwise block/inconclusive | Auto-pass required independent critique | verifier policy evidence |
| Event duplicated | Idempotent consume | Duplicate side effect/state transition | replay test |
| Event out of order | Version/sequence guard, reconcile/rebuild projection | Apply stale transition over newer state | ordering test |
| Event transport unavailable | Persist outbox/backlog and surface degraded state | Drop authoritative event silently | transport outage test |
| Core DB temporarily unavailable | Fail/queue safely according to operation semantics; preserve idempotency | Fall back to local untracked authority | outage test |
| Migration fails | Stop/rollback/restore according to migration plan; keep last good schema | Continue with partially migrated truth | migration rehearsal |
| Disk/storage pressure | Protect accepted truth/evidence first; pause nonessential writes | Evict authoritative history without policy | capacity/degradation test |
| Secret unavailable/expired | Mark capability unavailable; re-auth path | Embed/fallback to stale plaintext secret | secret lifecycle test |
| Network denied by policy | Fail with explainable capability denial | Worker bypasses egress policy | sandbox/egress test |
| Prompt-injection/tool-instruction conflict | Apply policy/authority hierarchy; quarantine untrusted instruction | Allow retrieved content to grant capabilities | adversarial test |
| Tool/plugin update regresses | Stop canary, rollback pinned certified version | Auto-promote latest | update-certification test |
| Human approval not received | Pause/expire by explicit deadline policy | Treat silence as approval | approval-timeout test |
| Operator cancels | Cooperative cancellation + side-effect reconciliation + final state | Abandon ambiguous work without record | cancellation test |

## G.1 Failure classes

DDE uses a minimum classification vocabulary:

```text
VALIDATION
AUTHORIZATION
CAPABILITY_UNAVAILABLE
PROVIDER_UNAVAILABLE
QUOTA_EXHAUSTED
TIMEOUT
AMBIGUOUS_EXTERNAL_EFFECT
CONFLICT
CONTEXT_UNSAFE
POLICY_DENIED
DEPENDENCY_UNAVAILABLE
INTEGRITY_FAILURE
MIGRATION_FAILURE
VERIFICATION_FAILED
VERIFICATION_INCONCLUSIVE
CANCELLED
INTERNAL_ERROR
```

Provider-specific error codes are preserved as diagnostics but normalized into DDE failure classes.

## G.2 Retry law

Retries require an explicit classification:

```text
NEVER
SAFE_IMMEDIATE
SAFE_WITH_BACKOFF
REQUIRES_RECONCILIATION
REQUIRES_NEW_CONTEXT
REQUIRES_NEW_WORKSPACE
REQUIRES_HUMAN
```

A model is not permitted to infer retry safety for irreversible external effects from prose alone.

## G.3 Degraded mode law

A degraded mode must state:

- which capability is unavailable;
- which read/write operations remain allowed;
- whether evidence quality changes;
- whether promotion is blocked;
- what operator action restores full service.

A degraded UI that hides a required verification/provider outage and still offers `Promote/Ship` is a correctness defect.

---

# Appendix H — Security and trust-boundary architecture

Security is enforced at command, execution, provider, storage and update boundaries. Model alignment or provider promises are not substitutes for controls.

## H.1 Trust zones

```text
Zone 0 — Accepted Project Truth / Core authoritative storage
Zone 1 — DDE trusted services and policy engine
Zone 2 — local authoring clients / operator UI
Zone 3 — isolated ExecutionEnvironment / worker workspace
Zone 4 — external model/provider/harness APIs
Zone 5 — external research/web/package/plugin/tool sources
Zone 6 — ProductEnvironment under test
```

Data/capabilities crossing zones require an explicit contract and audit trail.

## H.2 Principal types

Minimum principal classes:

```text
HUMAN_OPERATOR
DDE_SERVICE
STRATEGIC_WORKER
EXECUTION_WORKER
DESIGN_PROVIDER
VERIFIER
HERMES_SCOUT
AUTOMATION
EXTERNAL_ADAPTER
```

Authorization decisions bind principal + project + capability + resource + action + policy version. Model identity alone never grants authority.

## H.3 Capability security

Workers receive the minimum task-scoped grants required, such as:

```text
repo.read
repo.write:<declared-set>
command.request:<types>
provider.call:<provider>
network.egress:<allowlist>
secret.use:<handle>
product.preview
verification.request
artifact.write:<scope>
```

Capabilities expire with the relevant lease/session and are not ambient credentials.

## H.4 Secrets

Secrets must:

- remain outside prompts/logs/evidence unless a sanitized reference is required;
- be injected through handles/scoped environment mechanisms;
- have project/provider scope;
- support rotation/revocation;
- never be committed to repository truth;
- be redacted from captured stdout/stderr/events where feasible;
- cause capability unavailability when missing rather than fallback to insecure defaults.

## H.5 Data egress

The locked no-personal-data-export rule remains. In addition:

- context compiler labels sensitivity and provider eligibility;
- outbound payloads record provider, purpose, data classes, hashes/refs and policy decision;
- retrieval content is untrusted by default;
- secrets and forbidden data classes are stripped before provider calls;
- external research cannot become Project Truth without promotion;
- provider logging/training settings, where configurable, are part of certification metadata.

## H.6 Prompt injection and retrieved-content attacks

Retrieved repository/web/docs content is data, not authority. DDE must resist instructions inside retrieved content that attempt to:

- alter system/project authority;
- request secrets;
- broaden filesystem/network scope;
- bypass verification;
- change routing policy;
- approve/promote their own output;
- install/update executable tools.

The Context Compiler preserves provenance and trust level. Tool calls remain subject to policy independent of model text.

## H.7 Repository mutation security

- ChangePacket write sets define allowed mutable scope.
- symlink/path traversal/escaped-root writes fail closed.
- generated/build outputs have explicit ownership rules.
- staging manifests compare accepted paths against actual index content.
- executable permission changes and workflow/security-policy file changes are high-risk mutations requiring stronger review.

## H.8 Supply-chain security

For harnesses, CLIs, MCP servers, plugins, skills and packages:

- exact version/source/digest is recorded where available;
- update detected != update accepted;
- certification uses isolated/quarantine environment;
- capability and egress deltas are diffed;
- release notes are advisory, not evidence;
- canary and rollback are mandatory for governed executable updates;
- suspicious provenance blocks promotion.

## H.9 Audit integrity

Security-relevant audit records are append-oriented and include correlation/actor/policy version. Operators may append corrections/supersession; they may not silently rewrite historical authorization, route, verification, update or promotion decisions.

---

# Appendix I — Observability, service budgets, performance and capacity

DDE shall be diagnosable without asking a model to reconstruct what probably happened.

## I.1 Three observability layers

### Control-plane telemetry

- command/query/API latency and errors;
- mission/task/attempt state transitions;
- lease/session/workspace lifecycle;
- event backlog/consumer lag;
- database/storage health;
- migration/version state.

### AI/provider telemetry

- model/provider/harness/profile/version;
- input/output/cache/reasoning tokens where exposed;
- duration;
- cost;
- retries;
- quota/reset/health facts and provenance;
- route score/explanation;
- context utilization;
- verification/rework outcome.

### Product/design telemetry

- ProductEnvironment startup/render health;
- preview reload/build/runtime errors;
- visual verification duration/outcome;
- accessibility/performance measurements;
- DesignGateway latency/candidate counts;
- Try-Live/promote/verification lineage.

## I.2 Correlation law

The following identifiers must be traceable across logs/events/evidence where applicable:

```text
project_id
mission_id
task_id
attempt_id
command_id
correlation_id
route_decision_id
worker_session_id
worker_run_id
workspace_lease_id
change_packet_id
design_session_id
verification_run_id
commit/revision
```

## I.3 Service-budget model

Every production-relevant service/capability class must publish an engineering budget with:

```yaml
ServiceBudget:
  scope:
  operation:
  latency_target:
  availability_target:
  error_budget:
  timeout:
  concurrency_limit:
  queue_limit:
  payload_or_context_limit:
  provider_excluded_time_rule:
  measurement_window:
  evidence_ref:
```

Rev 3 architecture does not freeze arbitrary universal latency numbers before benchmark evidence. DDE-083 must establish and certify release-profile values. Until then, individual missions set provisional budgets that are explicit, measured and revisable only through accepted plan/EDR changes.

## I.4 Performance invariants

Regardless of final numeric budgets:

1. interactive UI reads must not synchronously wait on premium-model calls when a persisted projection can answer;
2. expensive provider calls run asynchronously/cancellably where the workflow permits;
3. unbounded collections require pagination/virtualization;
4. event handlers and workers use backpressure rather than unbounded fanout;
5. context packages enforce token/byte budgets;
6. screenshots/artifacts/logs have retention/storage limits;
7. verification fanout has concurrency/cost limits;
8. route selection has a deterministic fallback when learning services are slow/unavailable;
9. operator surfaces expose degraded/backlogged state rather than freezing silently.

## I.5 Capacity envelope

Each release profile publishes a tested capacity envelope rather than claiming infinite scale:

```yaml
CapacityEnvelope:
  deployment_profile:
  concurrent_projects:
  concurrent_worker_sessions:
  concurrent_product_previews:
  verification_parallelism:
  event_rate:
  artifact_write_rate:
  database_size_tested:
  artifact_store_size_tested:
  provider_rate_assumptions:
  bottleneck:
  degradation_point:
  tested_at_commit:
  evidence_ref:
```

Capacity beyond the certified envelope is unsupported until measured or explicitly accepted as risk.

## I.6 Alerting/attention policy

Alerts map to actionable conditions, not raw telemetry noise. Minimum operator attention classes:

```text
BLOCKING — cannot safely continue/promote
ACTION_REQUIRED — human decision/credential/reconciliation needed
DEGRADED — capability reduced but safe bounded work may continue
WARNING — approaching quota/context/storage/service budget
INFORMATIONAL — completed/changed state with no action required
```

The Attention Center groups correlated symptoms into one incident/task where possible.

---

# Appendix J — Deployment, migration, backup, disaster recovery and operational lifecycle

Rev 3 must remain operable across supported DDE deployment profiles without changing authority semantics.

## J.1 Deployment profiles

At minimum architecture supports these logical profiles where product packaging chooses to enable them:

```text
LOCAL WORKSTATION
  DDE Code / VS Code / Electron + local Core services + local/remote providers

SELF-HOSTED CORE
  persistent Core/Event/Artifact services + multiple authoring clients/workers

HYBRID
  local authoring/execution with governed remote Core/provider components
```

A deployment profile may change placement, not ownership. There is still one authoritative Core per project scope.

## J.2 Configuration and environment promotion

Configuration is separated into:

- versioned non-secret configuration;
- secret references;
- environment/deployment bindings;
- policy versions;
- provider/harness installation facts.

Promotion between development/test/release profiles records a configuration manifest. No environment inherits arbitrary user-home/global config before ProjectIdentity is established.

## J.3 Migration contract

Every persistent-schema or authority-changing migration declares:

```yaml
MigrationContract:
  migration_id:
  from_version:
  to_version:
  affected_owners: []
  invariants_changed: []
  forward_steps: []
  rollback_or_restore_strategy:
  compatibility_window:
  backfill_strategy:
  evidence_impact:
  downtime_or_online_mode:
  preflight_checks: []
  postflight_checks: []
```

Migrations are rehearsed against representative data before release. A failed migration may not leave mixed authority versions unmarked.

## J.4 Backup classes

Data is classified at minimum as:

```text
A — irreplaceable authority/history
    Project Truth, accepted EDRs, mission/task history, route decisions,
    approvals, capability certifications, evidence metadata, audit lineage

B — expensive/reconstructable operational state
    projections, experience indexes, provider telemetry, cached context metadata

C — reproducible/transient
    build outputs, disposable workspaces, regenerated caches
```

Backup/restore policy protects Class A most strongly. Artifact bytes required to prove accepted evidence inherit the protection needed by their certification.

## J.5 Recovery objectives

Exact RPO/RTO values are deployment-profile release contracts established and tested during DDE-083. Non-negotiable semantic objectives are:

- accepted Project Truth and immutable decision history are not silently lost;
- restored state is internally consistent to a known point;
- ambiguous in-flight external effects are reconciled before replay;
- restored evidence validity is recomputed where dependencies changed;
- worker/workspace leases from the failed instance expire safely;
- recovery is proven by rehearsal, not documentation alone.

## J.6 Operational lifecycle

DDE release operations include:

```text
preflight
→ backup/restore-point verification
→ schema/config compatibility check
→ deploy/update
→ smoke verification
→ provider/harness capability probes
→ event/projection health check
→ golden mission slice
→ promote or rollback
```

---

# Appendix K — Cross-platform product-surface parity contract

DDE Code, Frontend Studio, CLI, MCP/API and any supported web/mobile/desktop clients are **projections and command requesters over the same Core**, not separate products with divergent truth.

## K.1 Surface classes

```text
AUTHORING_SURFACE   VS Code/Cursor/editor integration
DESKTOP_SURFACE     Electron/native desktop shell
WEB_SURFACE         browser-hosted operator/workbench surfaces where supported
CLI_SURFACE         deterministic command-line automation
MCP_SURFACE         governed agent/tool integration
API_SURFACE         programmatic service boundary
MOBILE_SURFACE      optional constrained monitoring/approval surface where supported
```

## K.2 Parity rule

A capability declares one of:

```text
REQUIRED_ALL         must exist on every supported general-purpose surface
REQUIRED_OPERATOR    must exist on primary operator surfaces
REQUIRED_AUTOMATION  must exist on CLI/MCP/API where automation is expected
HOST_SPECIFIC        meaningful only on named host(s)
READ_ONLY_PARITY     mutation unavailable but truthful read/provenance required
NOT_APPLICABLE       explicit rationale
```

No missing surface is silently treated as parity.

## K.3 Mutation parity

Equivalent mutations from different hosts resolve to the same command contract and authorization rules. Host adapters may translate presentation/transport, never business authority.

## K.4 State-language parity

Semantic labels such as:

```text
DESIGN
LIVE
VERIFIED
BLOCKED
DEGRADED
WAITING_APPROVAL
CONTEXT_PRESSURE
FALLBACK_ACTIVE
```

must mean the same underlying state across surfaces.

## K.5 Offline/degraded clients

A disconnected/offline-capable client may cache projections and queue explicitly supported commands, but must:

- display freshness/connection state;
- never fabricate authoritative acceptance/promotion;
- revalidate authorization/revision on reconnect;
- resolve conflicts through Core commands;
- prevent stale high-risk approvals when policy requires current state.

---

# Appendix L — Acceptance, certification and release-evidence ledger

Testing is evidence production. A green suite is necessary but not sufficient when the suite does not exercise the production contract.

## L.1 CapabilityCertification

A capability reaches `VERIFIED` only with a durable record equivalent to:

```yaml
CapabilityCertification:
  certification_id:
  capability_id:
  capability_version:
  project_or_product_scope:
  realization_state: VERIFIED
  authority_refs: []
  acceptance_refs: []
  implementation_revision:
  configuration_hashes: []
  contract_versions: []
  verification_runs: []
  evidence_refs: []
  security_evidence_refs: []
  migration_evidence_refs: []
  performance_evidence_refs: []
  platform_parity_refs: []
  inherited_evidence_refs: []
  evidence_validity_snapshot:
  residuals: []
  certified_at:
  certifier_policy_version:
```

## L.2 Verification pyramid by risk

Minimum evidence classes:

```text
UNIT
CONTRACT
PROPERTY/INVARIANT
INTEGRATION
PRODUCTION-PATH / REAL-CALL
E2E
SECURITY/ADVERSARIAL
MIGRATION/RESTORE
PERFORMANCE/CAPACITY
CHAOS/RECOVERY
VISUAL/ACCESSIBILITY (UI work)
HUMAN/DOMAIN APPROVAL (where policy requires)
```

Not every capability requires every class, but omission must be risk-justified in the certification.

## L.3 Chapter-gate evidence package

Every mission gate emits a package that resolves:

- blueprint clauses implemented;
- requirement/capability IDs;
- changed contracts/schema;
- code owners and production call sites;
- state/failure/security changes;
- migration/evidence-invalidation effects;
- operator surfaces;
- test/verification results;
- performance/capacity observations where relevant;
- unresolved residuals;
- `PASS`, `PASS-WITH-EDR` or `FAIL`.

## L.4 ReleaseCertification

A Rev 3 release candidate is eligible only if:

1. all release-critical capabilities have current valid `CapabilityCertification`;
2. no high-severity traceability orphan exists;
3. no required surface falsely overclaims realization state;
4. migrations/restore are rehearsed;
5. security/update certification gates pass;
6. tested capacity envelope and service budgets are published;
7. golden and chaos missions pass at the candidate revision;
8. evidence validity is recomputed after final integration;
9. release manifest binds exact code/config/policy/tool versions.

## L.5 Certification invalidation

A certification becomes `STALE/INVALID` when a dependency classified as evidence-relevant changes. DDE must identify the smallest required re-verification set through the EvidenceValidityGraph rather than either trusting stale proof or restarting the entire audit.

---

# Appendix M — Dial depth-and-breadth closure standard

The Rev 3 architecture is considered **Dial-grade complete as a specification** only when each applicable capability can answer every row below from canonical contracts or generated trace projections.

| Closure dimension | Required answer |
|---|---|
| Why | Which accepted requirement/decision creates the capability? |
| Who owns truth | Which service/aggregate is authoritative? |
| What is the contract | Which typed commands, queries, APIs, events and data schemas apply? |
| Where it executes | Which production call sites/adapters/environments execute it? |
| How it changes state | Which state machine and transaction/side-effect boundaries apply? |
| What can fail | Which typed eventualities, retry and reconciliation rules apply? |
| Who may use it | Which principals/capabilities/security policies authorize it? |
| What may leave DDE | Which data-egress policy/provider eligibility applies? |
| How it is observed | Which events, metrics, traces, usage/cost and operator states apply? |
| How fast/how much | Which service budget and tested capacity envelope apply? |
| Where humans see/control it | Which surfaces and parity classification apply? |
| How it survives change | Which migration, backup, restore and rollback contracts apply? |
| How it is proven | Which verification scenarios/evidence/certification prove it? |
| How proof ages | Which dependencies invalidate or preserve its evidence? |
| How it ships | Which release gate and exact revision/config/tool manifest includes it? |

The development plan is responsible for realizing this architecture without turning these appendices into documentation-only ceremony.

**Rev 3.3 hardening does not change the inherited product baseline, does not claim these target contracts are already implemented, and does not alter the locked implementation order `REV-3A → DDE-068 … DDE-083`.**
