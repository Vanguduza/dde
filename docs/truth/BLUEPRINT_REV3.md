# DDE Blueprint Rev 3 — Consolidated Canonical Edition

**Canonical repository path:** `docs/truth/BLUEPRINT_REV3.md`  
**Status:** **CANONICAL HUMAN-READABLE ARCHITECTURE SOURCE OF TRUTH**  
**Effective:** 2 September 2026  
**Consolidated revision:** Rev 3.2  
**Repository:** `Vanguduza/dde`  
**Product implementation baseline inherited:** DDE-067 (`c30d2969e3205d1a277dd128e8b182137a8892e0`)  
**Repository-memory baseline inherited:** Rev 3 source-of-truth bootstrap through `fcc3e542ebc98ce769ec7ca74de72887dc5e5c02`  
**Companion implementation authority:** `docs/truth/DEV_PLAN_REV3.md`  
**Supersedes for forward architecture work:** legacy Blueprint Rev 2 and all standalone Rev 3 addenda/amendments once this consolidated edition is adopted.

> This edition consolidates the original DDE Blueprint Rev 3.0, the Rev 3 quantum audit and realization findings, the Rev 3.1 Operational Hardening / Adaptive Routing amendment, and the Claude `/design` + high-value Opal integration addendum into one architecture. The source documents remain historical evidence; they are no longer competing forward-development authorities.

> **Dial depth-and-breadth rule:** a capability is not fully specified unless the blueprint defines its authority, contract, state, runtime path, failure semantics, evidence, security boundary, observability, operator surface, testability and migration relationship.

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

It supports:

- API probes;
- UI rendering;
- integration tests;
- screenshot capture;
- accessibility checks;
- performance checks;
- visual verification.

## 3.5 Worker Provider

External model/harness runtime:

- Fable;
- OpenAI Codex;
- Claude Agent SDK / Claude Code;
- DeepSeek Harness;
- Hermes via ACP;
- future harnesses.

Providers are replaceable.

They never own authoritative project state.

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
StrategicOrchestratorLease
    ├── Fable preferred occupant when certified/available
    └── Opus temporary occupant when fallback policy selects it
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

# 5. Strategic orchestration and dynamic role occupancy

DDE owns durable orchestration state. External models may occupy a **strategic reasoning role**, but the role exists independently of the model.

### 5.1 Rejected static topology

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

1. **orchestrator occupancy** — who currently holds the strategic-orchestrator seat; and
2. **worker eligibility** — which certified worker configurations may execute a bounded task.

### 5.2 StrategicOrchestratorLease

The role is represented by a durable runtime object:

```yaml
StrategicOrchestratorLease:
  lease_id:
  project_id:
  mission_id:
  worker_session_id:
  role: STRATEGIC_ORCHESTRATOR
  occupant:
    model_endpoint_id:
    worker_profile_id:
    harness_installation_id:
  state:
    ACTIVE | FALLBACK_ACTIVE | REPROMOTION_PENDING | RELEASED | FAILED
  previous_occupant:
  acquisition_reason:
  fallback_reason:
  reset_deadline:
  policy_hash:
  acquired_at:
  released_at:
```

Role changes emit `RoleTransition` and `RoleOccupancyEvent`.

### 5.3 Fable available

When Fable is installed, certified, policy-eligible and provider capacity permits:

```text
Fable = strategic-orchestrator occupant
```

The subordinate candidate pool may include:

```text
Opus
Sonnet
Haiku
Codex
DeepSeek
local models
specialist profiles
future certified workers
```

Opus remains an ordinary candidate and is selected only when task evidence justifies it.

### 5.4 Fable unavailable

When Fable is exhausted, unhealthy or ineligible, DDE acquires the strategic lease for the best certified fallback. The locked initial fallback is an Opus-class strategic profile when available:

```text
Opus = temporary strategic-orchestrator occupant
Opus = removed from ordinary subordinate pool while occupying
other certified workers continue bounded execution
```

This prevents quota transfer from turning Opus into both orchestrator and universal executor.

### 5.5 Fable restoration

Provider reset/health recovery does not immediately interrupt unsafe work. At the next atomic checkpoint:

```text
Fable recovery confirmed
    ↓
repromotion eligibility
    ↓
atomic checkpoint
    ↓
Fable acquires lease
    ↓
Opus releases lease
    ↓
Opus returns to ordinary eligible worker pool
```

No stale fallback state and no premium-model creep are permitted.

### 5.6 Strategic planning contract

The strategic occupant receives a bounded `MissionOrchestrationContext` and returns a schema-valid proposal. Production path remains:

```text
StrategicOrchestratorService.propose
→ PlanningRegistryService.submit_draft
→ deterministic validation
→ approval where required
→ promote_draft
```

The model never writes the authoritative task graph directly.

### 5.7 Sparse use

Strategic orchestration is justified for:

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
- provider usage;
- quota/reset metadata;
- structured output;
- tool interception;
- cwd/project-root binding;
- project-configuration discovery.

A vendor documentation page is not proof that the installed version exposes a capability.

### 7.4 Certification lifecycle

```text
discovered
→ smoke-tested
→ contract-tested
→ shadow
→ certified
→ measured
```

A changed model/harness/profile/tool/skill/config identity becomes stale until re-certified according to risk.

### 7.5 Role certification

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

DDE supports multiple agent interfaces.

## 8.1 Harness-native APIs

Preferred for production execution when supported:

- Codex app-server / thread runtime;
- Claude Agent SDK;
- DeepSeek Harness;
- other vendor-native agent interfaces.

## 8.2 ACP

ACP is the preferred general interoperability boundary for external/local agents such as Hermes.

Expected interface:

```text
ACP client
    ↓
ACP agent
    ↓
capability negotiation
    ↓
DDE policy mapping
    ↓
WorkerSession
```

DDE must not assume every ACP agent supports:

- session resume;
- file read/write;
- terminal;
- cancellation;
- branching;
- tool streaming;
- usage reporting.

Discover capabilities and fail closed.

## 8.3 MCP

MCP remains the tool/resource plane.

It is not the authoritative mission state plane.

---

# 9. WorkerSession

WorkerRun is one execution attempt.

WorkerSession is the durable harness conversation/runtime lineage.

Minimum contract:

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
created_at:
last_activity_at:
context_package_hash:
tool_policy_hash:
session_config_hash:
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

## 9.1 Consolidated WorkerSession additions

A durable session also binds:

```yaml
WorkerSession:
  ...
  project_identity_id:
  bootstrap_receipt_id:
  effective_config_hash:
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

A worker may delegate only if policy allows it.

Child execution is never invisible.

Nested hierarchy:

```text
Mission
  ↓
Task
  ↓
TaskAttempt
  ↓
WorkerRun
  ↓
DelegationRequest
  ↓
Child Task / Child WorkerRun
```

Child execution inherits:

- tenant/project;
- context restrictions;
- environment policy;
- write scope;
- budget;
- external-effect rules;
- approval requirements.

Parent worker may not expand child authority beyond its own lease.

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

Documentation and UI claims must not drift from runtime truth.

Create machine-generated/validated views such as:

```text
capability realization
worker inventory
adapter health
mission status
verification coverage
policy activation
```

`just truth-check` should fail on known classes of drift.

Examples:

- README claims Cursor bridge live while adapter is fail-closed;
- UI claims worker healthy while auth missing;
- mission marked complete while mandatory verification absent;
- generated contract stale;
- model profile referenced but not certified.

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

Verification determines completion.

## 17.1 Independent by default

Implementer and verifier should differ for high-impact work where practical.

Use:

- deterministic tests;
- static analysis;
- API probes;
- visual verification;
- security validation;
- VLM critics;
- specialist review models.

## 17.2 Verification dependency graph

Map:

```text
requirement
→ implementation evidence
→ verification result
→ release gate
```

## 17.3 Visual verification

See Design Intelligence section.

## 17.4 Stuck detection

Use runtime signals rather than only wall-clock timeout:

- no progress events;
- repeated identical failure;
- same patch cycles;
- repeated permissions;
- tool retry loops;
- context saturation.

Escalation options:

```text
retry same
change strategy
change worker
Fable recovery plan
human intervention
```

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

All failure paths are first-class.

Failure classes include:

```text
POLICY
CAPABILITY
PROVIDER
MODEL
HARNESS
ENVIRONMENT
BUILD
TEST
VERIFICATION
INTEGRATION
EXTERNAL_EFFECT
BUDGET
TIMEOUT
CANCELLED
HUMAN_BLOCKED
```

Worker retry policy distinguishes retry-safe vs reconciliation-required effects.

Recovery artifacts persist before suspension where possible.

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

Feature completeness is semantic before visual.

## 19.1 Logical contract spine

For each product capability:

```text
FeatureContract
  ├─ states
  ├─ actions
  ├─ validation
  ├─ permissions
  ├─ recovery
  ├─ API/data contract
  └─ acceptance semantics
```

Platform implementations:

```text
web
android
windows
future
```

map to the same logical contract when behavior is intended to match.

## 19.2 FeatureCompletionLedger

Per feature/platform:

```text
NOT_STARTED
CONTRACT_READY
IMPLEMENTED
BEHAVIOR_VERIFIED
UX_VERIFIED
ACCESSIBILITY_VERIFIED
COMPLETE
```

Green web slice does not imply Android completion.

## 19.3 Golden mission fixture

Maintain a representative cross-platform mission that exercises:

- backend;
- web;
- Android;
- Windows/client when applicable;
- offline/retry;
- verification;
- evidence.

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

A design is not accepted because the producing model says it is good.

## 21.1 Evidence

For each target:

```text
screen × state × viewport × theme × motion-mode
```

capture:

- screenshot;
- DOM/accessibility snapshot when supported;
- deterministic metric result;
- visual diff;
- VLM critique artifact;
- repair lineage.

## 21.2 Deterministic metrics

Include:

- overflow;
- overlap;
- clipping;
- contrast;
- touch target;
- responsive breakpoints;
- density;
- generic silhouette/fingerprint;
- excessive card/pill/gradient/glass pattern;
- required-state coverage.

## 21.3 VLM critic

Critic receives actual renders.

It may assess:

- hierarchy;
- composition;
- product identity;
- visual polish;
- desktop/mobile suitability;
- genericness;
- discoverability.

Critique is rank-9 evidence.

## 21.4 Bounded repair

Default:

```text
max 3 visual repair cycles
```

Then human review.

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

DDE Code is not secondary developer tooling.

It is the operator interface for the factory.

Frontend Studio is not a demo tab.

It is a production subsystem for design/implementation/verification.

Required client types:

```text
VS Code / Cursor extension
Electron desktop
future web/mobile clients
```

All use Gateway/API/MCP.

No direct Core DB access.

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
- strategic-orchestrator transitions;
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

Every route should answer:

```text
Why this strategy?
Why this worker?
Why this model?
Why not the cheaper candidate?
Why was fallback used?
What quota influenced this?
What evidence supports the decision?
```

The UI should derive the answer from stored facts rather than generate a fresh model essay.

---

# 28. Attention Budget

AI increases parallelism faster than human review capacity.

DDE must control operator interruption.

Attention classes:

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

## 31.1 Project/session bootstrap health

A healthy worker session additionally requires:

```text
project_identity_valid
runtime_root_authorized
bootstrap_receipt_pass
effective_configuration_reconstructable
context_budget_safe
```

An adapter object existing in memory is never sufficient health proof.

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
- explicit strategic-orchestrator occupancy;
- Fable/Opus fallback/restoration semantics;
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
- legacy `docs/blueprint/REV_2_0.md`;
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
- REV-3A safety gate.

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

> **DDE owns truth, state, policy, admissibility, lineage and evidence. Project identity is established before configuration. A strategic-orchestrator role is dynamically occupied—Fable preferred when available and certified, Opus a temporary fallback when selected—while all ordinary work is routed across certified worker configurations according to capabilities and verified historical performance. Hermes remembers, retrieves and discovers patterns but never becomes routing or truth authority. Every code mutation belongs to a ChangePacket, every rejection has a disposition, every controlled commit proves staged scope, and prior evidence is inherited until a changed dependency specifically invalidates it. Context, provider quota and executable-tool versions are governed runtime resources. Frontend Studio exposes Claude `/design` through a DDE-owned DesignGateway and closes a bidirectional loop between design artifacts and real isolated live application candidates; provider artboards are never mislabeled as implementation. The same real runtime is projected as an execution graph, node inspector, run comparison, workflow library and policy-compiled Workflow Composer. Deterministic and independent verification decide completion.**

That is the single canonical human-readable architecture for DDE Rev 3.

---

# Appendix A — Canonical runtime object catalogue

The following objects are first-class or required target contracts. Names may map to existing schemas/services where already implemented; do not create duplicates solely to match this list.

| Domain | Canonical objects |
|---|---|
| Identity/bootstrap | `ProjectIdentity`, `RuntimeRoot`, `SessionBootstrapContract`, `EffectiveExecutionConfiguration`, `BootstrapReceipt` |
| Mission/planning | `Mission`, `TaskGraph`, `PlanDraft`, `StrategicOrchestratorLease`, `RoleTransition`, `PriorityOverride` |
| Execution | `TaskExecutionDescriptor`, `ExecutionStrategy`, `WorkerSession`, `WorkerRun`, `WorkspaceLease`, `ChangePacket` |
| Change governance | `DeclaredWriteSet`, `RejectionDisposition`, `StagingManifest`, `CommitManifest`, `WriteOwnershipGraph` |
| Fleet | `HarnessInstallation`, `HarnessRuntimeCapabilities`, `WorkerConfiguration`, `WorkerProfileCertification`, `ProviderCapacitySnapshot` |
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
| Learning | Any adaptive use is evidence-gated and cannot self-promote. |
| Migration | Existing implementation/evidence is retained or explicitly superseded. |
| Tests | Unit/contract/integration/e2e/chaos coverage is appropriate to risk. |
| Drift | Docs/UI cannot overclaim the actual realization state. |

States remain:

```text
SPECIFIED → CONTRACTED → WIRED → EXECUTABLE → OBSERVABLE → VERIFIED
```

A planning document alone never advances a capability beyond `SPECIFIED`.
