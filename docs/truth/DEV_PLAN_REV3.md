# DDE Rev 3 Development & Realisation Plan — Consolidated Canonical Edition

**Canonical repository path:** `docs/truth/DEV_PLAN_REV3.md`  
**Status:** **CANONICAL FORWARD DEVELOPMENT PLAN**  
**Effective:** 2 September 2026  
**Consolidated revision:** Rev 3.2  
**Repository:** `Vanguduza/dde`  
**Architecture authority:** `docs/truth/BLUEPRINT_REV3.md`  
**Inherited product baseline:** DDE-067 at `c30d2969e3205d1a277dd128e8b182137a8892e0`  
**Inherited Rev 3 repository-memory baseline:** `fcc3e542ebc98ce769ec7ca74de72887dc5e5c02`  
**Purpose:** move the existing DDE repository to the consolidated Rev 3 architecture without restarting, duplicating closed work, re-auditing unaffected evidence, or confusing documentation with runtime completion.

> This plan absorbs the original Rev 3 Development Plan, the Rev 3 quantum audit/realisation findings, Rev 3.1 operational hardening, and the Claude `/design` + high-value Opal integration plan. Those inputs remain historical evidence after adoption; this file is the single forward implementation sequence.

---

# 0. Development doctrine

Rev 3 is a **closure, realisation and operational-hardening program**, not a rewrite.

The repository already contains a substantial governed control plane. Progress is not measured by documents, schemas, enums, UI presence or test-only seams. Every mission must move capabilities through:

```text
SPECIFIED
   ↓
CONTRACTED
   ↓
WIRED
   ↓
EXECUTABLE
   ↓
OBSERVABLE
   ↓
VERIFIED
```

A mission may introduce a new concept only when it closes a demonstrated runtime gap or implements a locked consolidated contract.

## 0.1 Dial depth-and-breadth implementation rule

For every feature/work packet, the implementation record must map:

```text
authority
→ schema/contract
→ owner/service
→ real writer
→ real reader
→ production call site
→ state machine
→ failures/recovery
→ capability/security/egress
→ telemetry/cost
→ operator/API surface
→ verification/evidence
→ migration/evidence inheritance
```

If any applicable link is missing, the feature remains partial.

## 0.2 Evidence inheritance

Do not re-audit or rebuild work already proven by chapter gates/evidence unless the current change modifies a dependency or invariant that invalidates that evidence.

## 0.3 No static model-role implementation

Mission code must express capabilities, role occupancy and worker eligibility. Static mappings such as `Fable=strategy`, `Opus=reasoning`, `Codex=coding` may exist only as decaying priors or configuration defaults, never architectural truth.

## 0.4 No design/runtime theatre

A design artboard is not a live application; an execution graph is not valid unless projected from actual runtime state; a workflow composer is not allowed to create a second orchestration engine.

---

# 1. Starting state — preserve what is already real

Treat the following as existing infrastructure to preserve and compose, not recreate:

- authoritative Project Truth model and accepted EDR path;
- requirements, missions and task state;
- immutable RouteDecision persistence;
- deterministic routing hard gates and policy activation;
- model-assisted PlanDraft validate/promote boundary;
- TaskAttempt, WorkerRun and WorkerEvent;
- certified WorkerAdapter abstraction and Worker Manager;
- capability leases;
- ExecutionEnvironment and Workspace;
- external-effect journal and recovery matrix;
- checkpoints and idempotency CommandLedger;
- attempt budgets and runtime-usage writer;
- evidence, VerificationRun/runner and AcceptanceOracle;
- API-probe and visual-diff evidence primitives;
- Donor Lab;
- Frontend generation-prompt compiler;
- Frontend Studio Gateway mutation path;
- design-token SSOT and design-lint ratchet;
- Prototype Gallery and DDE-067 Frontend Studio contributed views;
- Windows installer / VS Code / Electron product surfaces;
- Rev 3 repository-memory bootstrap under `docs/truth/**`.

Do not build parallel replacements unless a chapter gate proves the existing owner cannot be evolved safely.

---

# 2. Starting state — what remains partial

The consolidation does **not** promote implementation state. The inherited product baseline remains DDE-067.

Known partials include:

- routing prediction fields exist but are not yet empirically produced end-to-end;
- model selection is not yet a full provider-execution binding;
- WorkerSession is not yet the durable native runtime for all agent harnesses;
- worker/fleet facts are split between static/in-memory authorities and require convergence;
- current Claude path is useful but synchronous/non-resumable and lacks complete usage telemetry;
- first-class Codex/Hermes/DeepSeek runtime paths require full Rev 3 realisation/evidence;
- genuine provider usage/quota/reset producers are incomplete;
- DDE-067 proves Frontend Studio command wiring but is not the final IDE-class workbench;
- DDE-068 rendered visual verification/critique loop is not yet evidence-complete;
- the execution graph/node inspector/workflow composer are target capabilities, not current truth;
- DesignGateway/Claude Design live loop is target capability, not current truth;
- project/bootstrap identity, context-budget enforcement, ChangePacket staging guards and selective evidence invalidation require native implementation;
- managed executable-tool update certification is target capability.

No UI, prompt or document may represent these as `VERIFIED` until the production path and evidence exist.

---

# 3. Program governance

## 3.1 Rev 3 source-of-truth consolidation gate

The repository already completed an initial Rev 3 truth bootstrap. This consolidation updates that bootstrap rather than creating a second `REV_3_0.md` hierarchy elsewhere.

Canonical forward files are exactly:

```text
docs/truth/BLUEPRINT_REV3.md
docs/truth/DEV_PLAN_REV3.md
```

Supporting controlled projections/helpers are:

```text
docs/truth/ARCHITECTURE_DECISIONS.md
docs/truth/IMPLEMENTATION_STATE.md
docs/truth/RESUME_PROMPT.md
```

Gate criteria:

- Blueprint absorbs Rev 3.1 and Claude Design/Opal decisions;
- Development Plan absorbs their sequencing and acceptance changes;
- README/AGENTS/bootstrap pointers remain consistent;
- support projections do not contradict the two canonical documents;
- legacy Rev 2 and standalone addenda are historical/reference where conflicts occur;
- no product capability is falsely promoted merely because documentation changed.

## 3.2 REV-3A Operational Safety Gate — next implementation gate

**Do not renumber DDE-068 through DDE-083.**

REV-3A is a short implementation safety gate that makes DDE development itself safer before subsequent numbered missions.

Required outcomes:

1. project identity enforcement;
2. no unrelated-root configuration contamination;
3. explicit strategic-orchestrator occupancy;
4. Fable/Opus fallback and restoration semantics;
5. ordinary worker-pool eligibility rules;
6. context checkpoint rule;
7. `ContinuationPackage` format;
8. packet-scoped mutable work;
9. rejected-work disposition;
10. staging-scope guard;
11. evidence inheritance / no blanket re-audit.

### 3.2.1 REV-3A.1 — ProjectIdentity preflight

Contracts:

```text
ProjectIdentity
RuntimeRoot
SessionBootstrapContract
EffectiveExecutionConfiguration
BootstrapReceipt
```

Acceptance:

- approved root resolves expected project identity;
- wrong/unregistered root fails closed;
- unrelated project cannot inherit DDE/Dial configuration;
- configuration sources/hashes are reconstructable;
- no worker session accepts work without a PASS receipt.

### 3.2.2 REV-3A.2 — StrategicOrchestratorLease safety shim

Implement the minimum durable occupancy contract needed by current development workflows.

Acceptance:

```text
Fable available   → Fable occupant; Opus ordinary eligible candidate
Fable unavailable → Opus temporary occupant; Opus removed from ordinary pool
Fable restored    → atomic checkpoint → Fable occupant; Opus returns to ordinary pool
```

No premium-model creep; no stale fallback state.

### 3.2.3 REV-3A.3 — ContextBudget + continuation

Runtime/session guard states:

```text
HEALTHY
PRESSURE
CHECKPOINT_REQUIRED
UNSAFE_FOR_HIGH_RISK_WORK
```

A high-risk task under unsafe remaining context must checkpoint, emit a `ContinuationPackage`, and resume in a fresh session rather than start/continue unsafely.

### 3.2.4 REV-3A.4 — ChangePacket / rejection / staging guard

Introduce or minimally wire:

```text
ChangePacket
DeclaredWriteSet
RejectionDisposition
StagingManifest
CommitManifest
```

Critical acceptance:

```text
Worker A modifies files
→ Packet A rejected and dispositioned
→ Worker B performs accepted work
→ broad/accidental staging attempted
→ ZERO Packet A mutations enter Worker B commit
```

Unexpected staged paths block. Broad `git add -A` is illegal for normal controlled packets unless an explicit bulk-maintenance packet/override authorizes it.

### 3.2.5 REV-3A.5 — Evidence-validity guard

Introduce minimal `EvidenceValidityGraph` / delta-audit semantics.

Acceptance:

- unrelated change preserves previous evidence;
- changed invariant invalidates only affected evidence;
- continuation identifies required re-verification and forbidden rework.

### 3.2.6 REV-3A gate proof

Before DDE-068:

- focused contract/invariant tests pass;
- repository full checks pass;
- operational chapter gate maps every required outcome to real call sites;
- `IMPLEMENTATION_STATE.md` is updated from evidence;
- no numbered product mission is marked progressed by REV-3A unless its own acceptance is independently met.

---

# 4. Canonical mission sequence

```text
REV-3 SOURCE-OF-TRUTH CONSOLIDATION
        │
        ▼
REV-3A  OPERATIONAL SAFETY GATE
        │
        ▼
DDE-068 Visual Verification & Critique Loop
        │
        ▼
DDE-069 DDE Code / Frontend Studio V2 + Live Design Foundation
        │
        ▼
DDE-070 Harness Contract V2 + WorkerSession + Bootstrap Runtime
        │
        ▼
DDE-071 Strategic Orchestrator Runtime
        │
        ▼
DDE-072 Codex Native Worker
        │
        ▼
DDE-073 Claude Agent SDK Worker + Runtime Capability Discovery
        │
        ▼
DDE-074 DeepSeek Harness Worker
        │
        ▼
DDE-075 ACP + Hermes Experience Intelligence
        │
        ▼
DDE-076 Persistent Fleet Registry + Provider Capacity
        │
        ▼
DDE-077 TaskExecutionDescriptor + Strategy + Change/Workspace Ownership
        │
        ▼
DDE-078 Real Usage / Cost / Quota / Context / Occupancy Telemetry
        │
        ▼
DDE-079 Empirical Routing + Route Critic
        │
        ▼
DDE-080 Truth / Context / Evidence-Validity Compilers
        │
        ▼
DDE-081 Mission Workspace + Execution Graph + Node Inspector
        │
        ▼
DDE-082 Design Intelligence + Design Gateway + Playbooks/Workflow Composer
        │
        ▼
DDE-083 System Hardening / Chaos / Update Certification / Release Candidate
```

Isolated work packets may overlap when dependencies and write ownership allow it, but chapter-gate dependencies control promotion. Existing DDE-068…083 numbers are retained.

---

# 5. DDE-068 — Visual Verification & Critique Loop

**Priority:** P0  
**Dependency:** REV-3A PASS  
**Objective:** turn visual quality from planning/lint concepts into real evidence-producing DDE verification.

## 5.1 Required contracts and runtime

Implement/extend the actual verification architecture so a request can:

```text
ProductEnvironment target
→ viewport/state/theme/motion matrix
→ render executor
→ screenshot + structure/accessibility evidence
→ deterministic visual checks
→ visual diff
→ VLM/independent critique where policy requires
→ bounded repair
→ persisted VerificationRun/Evidence
→ promotion/quality verdict consumed by the real gate
```

## 5.2 Deterministic quality gates

Close the remaining high-value design rules, including:

- overflow/overlap/clipping;
- required-state coverage;
- responsive breakpoint behavior;
- touch/interaction target constraints;
- contrast/accessibility primitives;
- DD207+ combination rules;
- generic silhouette/fingerprint detection;
- density/believable-data checks;
- reduced-motion semantics;
- excessive card/pill/gradient/glass generic grammar.

## 5.3 VLM/visual critic

Critic receives actual renders, not prose descriptions. Critique remains rank-9 evidence and may not directly mutate accepted product state.

Bounded automated repair default: maximum 3 cycles, then human escalation.

## 5.4 Lineage

Visual evidence binds exact:

- requirement/acceptance criterion;
- task/ChangePacket;
- code revision;
- ProductEnvironment/runtime identity;
- verifier/critic identity;
- promoted `DesignArtifact` version where applicable.

## 5.5 Evidence validity

Evidence participates in `EvidenceValidityGraph`. Unrelated changes retain proof; relevant invariant changes invalidate only dependent visual evidence.

## 5.6 Acceptance

DDE-068 is complete only when a real Gateway/API/mission path can request visual verification, persist evidence, fail/pause/recover correctly and block/permit the actual promotion gate using the recorded verdict. A CI screenshot script or UI badge alone is insufficient.

---

# 6. DDE-069 — DDE Code / Frontend Studio V2 + Live Design Foundation

**Priority:** P0  
**Objective:** replace DDE-067 command-console UX with a professional IDE-class workbench and establish the first governed Claude Design live loop without changing DDE authority.

## 6.1 Product design register

Frontend Studio is product/engineering UI, not marketing UI.

Direction: **Precision Manufacturing Workbench** — modern, technical, calm, compact, high-density, excellent typography, strong keyboard workflow, restrained accent, structural panes/inspectors/timelines/evidence, no generic SaaS card soup, glassmorphism or decorative dashboards.

## 6.2 UI runtime foundation

After dependency/EDR admission, migrate string-rendered surfaces toward componentized shared assets suitable for VS Code webview and Electron, with React + TypeScript + Vite as the preferred implementation direction already defined by the blueprint.

No UI framework becomes authority. All mutations continue through Gateway/API/MCP.

## 6.3 Host bridge

Create a stable host bridge abstraction for command, read, event subscription, external-open/file-reveal and native notification behavior, with VS Code/Electron/Test adapters.

UI components do not own protocol details.

## 6.4 Workbench modes

Implement the canonical workflow modes:

```text
Brief → Explore → References → Build → Motion → Verify → Ship
```

Build uses structure/assets + real live canvas + contextual inspector + bottom activity/verification/evidence drawer.

## 6.5 DesignGateway foundation

Establish provider-neutral contracts:

```text
DesignProvider
DesignGateway
ClaudeDesignAdapter
DesignGateDecision
DesignSession
DesignArtifact
DesignEditContext
DesignSystemRegistry
LiveEditWorkspace
PreviewRuntimeAdapter
```

Claude is the first specialist provider, not the architecture.

## 6.6 Material design gate

Mandatory by policy for new screens, substantial redesign, new navigation/information hierarchy, dashboard/onboarding/checkout, major responsive adaptation, rebrand/design-system migration or explicitly bespoke visual direction.

Tiny deterministic/copy/layout-preserving changes may bypass only through an auditable `DesignGateDecision`.

Provider outage on mandatory design creates a waiting/degraded state or approved alternate-provider route; it never silently bypasses design.

## 6.7 Claude `/design` first-class UX

Build toolbar:

```text
[Design with Claude] [Try live] [Compare] [Promote] [Verify]
```

Add:

- Design Dock scoped to selected element/screen/flow;
- candidate strip;
- `Claude Design` inspector tab;
- semantic status/provenance, not raw chat transcript.

## 6.8 Three editing lanes

**Lane A — deterministic direct edit:** token-valid spacing/type/color/alignment/component/copy/motion changes compile directly through typed Gateway commands.

**Lane B — contextual AI design edit:** selected live screen/element + minimal governed context is sent to DesignGateway for ambiguous/aesthetic refinement.

**Lane C — divergent design mode:** new/major work generates multiple artboards/candidates for comparison before Try-Live.

## 6.9 DesignEditContext

Selection uses stable anchors and compiles only the required screen/state/viewport evidence, component lineage, allowed design-system tokens/components, requirement refs, approved references and code scope. No repository dumping.

## 6.10 Try-Live implementation bridge

```text
DesignCandidate
→ machine-readable handoff
→ TaskExecutionDescriptor
→ capability router
→ certified implementation worker
→ isolated LiveEditWorkspace/ChangePacket
→ PreviewRuntimeAdapter
→ REAL LIVE CANDIDATE
```

The provider artboard is `DESIGN`. Only actual running application code may be `LIVE`. A live candidate that passed gates may be `VERIFIED`.

## 6.11 Bidirectional refinement

The real current live candidate—including deterministic inspector edits—can become the next refinement baseline:

```text
real live state → provider → candidate → Try live → real live state → provider …
```

## 6.12 Promotion boundary

Exploratory edits remain isolated. `Promote` freezes the exact design version and code revision. Only the promoted pair becomes eligible for DDE-068 verification and later merge.

## 6.13 Read-only execution graph seed

Add a read-only graph projection in the Studio shell if real event/task data is available. It must project actual runtime state only. Interactive replay/reroute/fork remains DDE-081.

## 6.14 Security/egress acceptance

- allowlisted exact context only;
- secrets, production user data and unrelated repository content excluded;
- provider/session/artifact and design-system hashes recorded;
- provider canvas embedding optional, not architectural dependency;
- no direct main/accepted workspace mutation from design output.

## 6.15 Acceptance

Prove one screen end to end:

```text
select
→ DesignEditContext
→ Claude candidate persisted as DesignArtifact
→ Try live isolated build
→ real LIVE render
→ deterministic edit
→ provider refinement
→ promote exact design/code pair
→ DDE-068 verification
```

---

# 7. DDE-070 — Harness Contract V2 + WorkerSession + Bootstrap Runtime

**Priority:** P0

DDE-070 moves REV-3A safety shims into the durable generic runtime.

## 7.1 Contracts

Add/extend without duplicating accepted owners:

```text
Harness
HarnessInstallation
HarnessVersion
HarnessRuntimeCapabilities
AgentCapabilityDescriptor
WorkerProfileV2
WorkerSession
WorkerSessionEvent
ProjectIdentity
RuntimeRoot
SessionBootstrapContract
EffectiveExecutionConfiguration
BootstrapReceipt
ContextBudget
ContinuationPackage
```

## 7.2 Bootstrap lifecycle

```text
process/session start
→ resolve RuntimeRoot
→ resolve ProjectIdentity
→ authorize root/project relationship
→ resolve configuration authorities
→ resolve skills/hooks/tools/MCPs
→ compute EffectiveExecutionConfiguration
→ emit BootstrapReceipt PASS
→ accept work
```

Wrong/unapproved root fails closed.

## 7.3 Adapter V2

Conceptual capabilities:

```text
register / health / discover_capabilities
open_session / resume_session
start_turn / stream_events
request_pause / resume_turn / cancel
collect_artifacts / collect_usage
close_session / cleanup
```

Safe V1 compatibility wrappers may exist temporarily.

## 7.4 WorkerSession persistence

Persist project/mission/task, harness/profile/model endpoint, provider session ref, workspace/environment, bootstrap receipt/effective config hash, strategic lease, context budget/pressure and continuation linkage.

WorkerRun references durable session identity.

## 7.5 Runtime capability discovery

For the exact installed version certify where applicable:

- persistent session/resume;
- start/stop/failure/rate-limit hooks;
- model switching;
- structured output;
- provider usage/quota/reset metadata;
- tool interception;
- cwd/project-root/config behavior.

Distinguish documented, installed, certified and measured capability.

## 7.6 Acceptance

Prove wrong-root refusal, approved-root identity, reconstructable configuration, open→run→pause→restart→resume→complete lineage, capability-mismatch fail-closed, and context-pressure continuation into a fresh session.

---

# 8. DDE-071 — Strategic Orchestrator Runtime

**Priority:** P0

DDE-071 implements a first-class strategic role rather than a Fable-specific architecture.

## 8.1 Contracts

```text
StrategicOrchestratorLease
RoleTransition
RoleOccupancyEvent
OrchestrationPlan
```

## 8.2 Fable available

Fable is the preferred occupant when installed/certified/eligible. Ordinary worker candidates may still include Opus, Sonnet, Haiku, Codex, DeepSeek and others.

Opus is selected for bounded subordinate work only when routing evidence justifies it.

## 8.3 Fable unavailable

Initial locked fallback behavior when eligible:

```text
Opus = temporary strategic-orchestrator occupant
Opus removed from ordinary worker pool
remaining certified workers continue routine execution
```

If Opus is also unavailable, use another certified strategic configuration or human decision according to policy.

## 8.4 Fable restoration

```text
recovery/reset confirmed
→ repromotion eligible
→ atomic checkpoint
→ Fable acquires lease
→ Opus releases lease
→ Opus returns to ordinary candidate pool
```

No stale fallback state, double occupancy or premium-model creep.

## 8.5 Planning path

Strategic output remains a draft:

```text
StrategicOrchestratorService.propose
→ PlanningRegistryService.submit_draft
→ validate
→ approval if required
→ promote
```

No direct task-graph mutation.

## 8.6 Acceptance

Test invalid plan rejection, high-risk approval, valid promotion, Fable exhaustion, Opus fallback/exclusion, Fable restoration/Opus re-entry, restart recovery and provider-capacity integration.

---

# 9. DDE-072 — Codex Native Worker

**Priority:** P0

Implement a first-class Codex worker behind the generic Harness V2 / WorkerSession contract, not a vendor-specific Core branch.

Required capabilities/evidence:

- real session/thread identity where the installed interface supports it;
- governed tools/capabilities/workspace;
- streaming normalized DDE events;
- pause/resume/cancel as supported/certified;
- genuine usage forwarding where available;
- artifact/diff collection;
- typed failures and recovery;
- routing profile for ordinary engineering as an initial prior, not permanent truth.

Acceptance: route a bounded engineering task to Codex through the normal Router/Worker Manager, produce a real ChangePacket, run verification and persist usage/evidence without bypassing DDE authority.

---

# 10. DDE-073 — Claude Agent SDK Worker + Runtime Capability Discovery

**Priority:** P0/P1

Replace the current limited Path-A-only posture with a persistent certified Claude worker where the supported SDK/runtime permits it, while preserving the safe existing path during migration.

## 10.1 Required behavior

- persistent WorkerSession when supported;
- governed tools/permissions;
- streaming normalized events;
- pause/resume/cancel where certified;
- artifacts/diff/usage collection;
- typed provider/quota/runtime failures;
- no credential leakage to worker environment.

## 10.2 Version-specific capability certification

Record the exact:

```text
installed version
available models
persistent-session support
resume support
supported hooks
runtime model switching
structured output
usage reporting
quota/reset metadata
tool interception
project-root/config-discovery behavior
```

Do not infer installed behavior from generic documentation.

## 10.3 Claude Design separation

`Claude Agent SDK Worker` and `ClaudeDesignAdapter` are separate capability providers even if vendor identity overlaps.

- coding worker executes governed implementation;
- design adapter produces/refines DesignArtifacts;
- either may be unavailable independently;
- one may not bypass the other's gates;
- telemetry/certification are independent.

## 10.4 Acceptance

Prove persistent/resumable behavior actually supported by the installed version, hard debugging/implementation route, quota failure, recovery, genuine usage where available, and no false health/capability claims.

---

# 11. DDE-074 — DeepSeek Harness Worker

**Priority:** P1

Integrate DeepSeek behind the same worker/runtime contracts for economical bounded work and fan-out where deterministic verification can arbitrate quality.

Required:

- real harness/version/capability discovery;
- explicit worker profile eligibility;
- workspace/change packet governance;
- provider health/quota/usage;
- deterministic selection/rejection of fan-out candidates;
- no hidden cross-worker writes.

Acceptance: safely execute bounded implementation/test-generation/fan-out work and prove the winning output through independent deterministic verification.

---

# 12. DDE-075 — ACP + Hermes Experience Intelligence

**Priority:** P1

## 12.1 ACP

Implement generic capability-negotiated ACP client support for session create/resume/list where available, prompting/streaming, tools/permission requests and fork/cancel where supported.

## 12.2 Hermes profiles

```text
context_scout
research
knowledge_curator
skill_distiller
operator
experience_scout
failure_memory
routing_insight
continuity_scout
provenance_scout
```

## 12.3 Execution Experience Memory

Authoritative raw WorkerRun/verification telemetry remains in DDE. Derived provenance-linked records are indexed for Hermes semantic retrieval.

`ExperienceRecord` captures task signature, exact WorkerConfiguration, verified/first-pass outcome, attempts/rework/regressions/human intervention, tokens/cost/latency, failure signatures and verification refs.

## 12.4 ExperienceScout

Before route selection, retrieve semantically similar verified work and return successful/failed configurations, success/rework/cost/latency aggregates, recurring failure/escalation patterns, freshness, evidence count and confidence.

## 12.5 FailureMemory / ContinuityScout / ProvenanceScout

Hermes remembers recurring failures/recoveries, prepares bounded resume context and answers lineage questions from durable DDE IDs.

## 12.6 RoutingInsightCandidate

Hermes may propose a routing improvement but cannot promote policy.

```text
candidate
→ offline replay
→ holdout
→ shadow
→ canary
→ governed promotion
```

## 12.7 Playbook discovery

Hermes may identify recurring successful design/execution patterns as workflow candidates. DDE evaluation/policy owns promotion.

## 12.8 Acceptance

Perform a real research/experience task, preserve authority/provenance, consume it in planning/routing without hidden mutation, and prove an insight remains non-authoritative until evaluation.

---

# 13. DDE-076 — Persistent Fleet Registry + Provider Capacity

**Priority:** P0/P1

## 13.1 Persistent authorities

Converge:

```text
harnesses
harness_installations
harness_versions
worker_profiles
worker_profile_capabilities
worker_profile_certifications
model_endpoints
model_capabilities
runtime_capability_certifications
provider_capacity_snapshots
role_certifications
```

Router, Worker Manager and UI consume the same authority.

## 13.2 WorkerConfiguration identity

Certification binds exact model/version, provider, harness/version, profile, skills/tools manifest, context strategy, environment identity and policy hashes. Changed identity becomes stale until recertified.

## 13.3 Multi-role certification

A configuration may be orchestration-, implementation-, review- and/or security-capable. Current role occupancy is separate.

## 13.4 Capacity states

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

Store reset source/confidence, probe cost, concurrency, failures, latency and cost metadata.

## 13.5 Probe economics

Use reliable passive reset signals before cheap active probes, and expensive probes only when expected value justifies cost.

## 13.6 Acceptance

Restart Core and prove Router/Worker Manager/UI agreement, stale-version handling, exact runtime-capability reconstruction, capacity/reset lifecycle and dynamic role eligibility.

---

# 14. DDE-077 — Task Execution Strategy + Change/Workspace Ownership

**Priority:** P1

## 14.1 TaskExecutionDescriptor

Implement structured task classification from authoritative task/requirements/project metadata. Model assistance may propose missing values but cannot silently invent risk.

## 14.2 ExecutionStrategyEngine

Map descriptors to legal strategies such as direct, plan/implement/review, investigate, specialist fan-out, parallel implementations, red-team, visual iteration and migration-with-rollback proof.

Strategy precedes worker selection.

## 14.3 WorkspaceLease + WriteOwnershipGraph

One editing session → one authorized worktree. Check file, symbol, schema/generated-contract and integration-hotspot overlap before parallel work.

## 14.4 ChangePacket

Every mutable packet binds project/mission/task/run/workspace, declared read/write scopes, base tree, touched paths, diff, staging, provenance and gate refs.

## 14.5 RejectionDisposition

Rejected work is quarantined/reverted/isolated and verified absent from accepted baseline. `REJECTED` is not merely a UI status.

## 14.6 StagingManifest / CommitManifest

Controlled commits prove declared scope ≈ actual changed paths ≈ staged paths ≈ commit scope. Unexpected staged path → BLOCK.

## 14.7 Safe parallelism

Bound by dependency, write ownership, provider capacity, verification capacity, integration capacity and Attention Budget—not agent count.

## 14.8 Acceptance

Critical invariant: Packet A rejected + Packet B accepted → **zero Packet A changes** can enter Packet B commit. Also test concurrent path conflict, generated-contract contention and staged-scope mismatch.

---

# 15. DDE-078 — Real Usage, Cost, Quota, Context & Occupancy Telemetry

**Priority:** P0/P1

Every live adapter forwards genuine provider usage where available. Unknown remains unknown.

Normalized dimensions include model/version, provider, harness/version, profile, tokens/cache/reasoning, tool calls, duration, provider/effective cost.

Additional telemetry:

```text
strategic-orchestrator occupancy
fallback duration
repromotion latency
premium-worker utilization
provider probe cost
context pressure
checkpoint/continuation rate
rework count
human intervention
design-provider usage
design candidate count
Try-Live rebuild count
visual-verification cost
```

KPIs:

```text
cost_per_verified_success
premium_tokens_per_verified_success
orchestrator_tokens / total_model_tokens
rework_per_worker_configuration
fallback_recovery_time
first_pass_verified_rate
human_intervention_per_verified_success
design_cost_per_verified_candidate
```

Acceptance: force quota/fallback/context pressure and prove correct attribution, conservation of strategic capacity and visibility of premium-model creep.

---

# 16. DDE-079 — Empirical Routing + Route Critic

**Priority:** P1

## 16.1 Routing feature vector

Join requested capabilities, descriptor/strategy, current strategic occupant, exact candidate WorkerConfiguration, context pressure, quota/reset distance, provider health, probe cost, semantic task similarity, verified historical success/rework, previous cheaper-worker failure and premium escalation reason.

## 16.2 Prediction targets

```text
verified_success
effective_cost
latency
rework
human_intervention
operational_risk
```

Populate RouteDecision predictions/confidence from measured evidence.

## 16.3 Static-prior decay

Bootstrap affinities lose influence as sufficient version-aware evidence accumulates.

## 16.4 Escalation learning

Learn sequences, not just winners—for example cheaper first, premium only on a specific failure signature.

## 16.5 Controlled exploration

Low-risk shadow/canary only; high-risk new configurations require stronger certification.

## 16.6 Route Critic

Invoke strategic reasoning only for ambiguity/ties/high risk/prior failures. It never overrides hard gates.

## 16.7 Acceptance

Historical holdout/replay shows no safety regression and improves verified-outcome utility over deterministic baseline. Promotion remains shadow→canary→promoted with rollback.

---

# 17. DDE-080 — Truth, Context and Evidence-Validity Compilers

**Priority:** P1

## 17.1 Capability-realisation report

Generate truthful status from code/registries/evidence:

```text
capability
specified
contracted
writer
reader
gateway
adapter
telemetry
ui
verified
status
```

## 17.2 Truth/drift checks

Detect stale docs, overclaimed adapters, impossible routes, conflicting mission state, dead enums and model catalog drift.

## 17.3 Context Compiler

Generate smallest-sufficient provenance-carrying context packages.

## 17.4 ContextBudget integration

Estimate/reserve safe context before high-risk work and checkpoint when thresholds are crossed.

## 17.5 ContinuationPackage

Persist accepted requirements/decisions, branch/base/head/working state, active ChangePacket, completed steps, unresolved findings, next exact action, required evidence and forbidden rework.

## 17.6 EvidenceValidityGraph / RegressionInvalidationGraph / DeltaAuditPlan

A change computes evidence preserved, evidence invalidated, checks required and work that must not be repeated.

## 17.7 Acceptance

False capability claim fails truth-check; unrelated change retains evidence; changed invariant invalidates only dependent evidence; fresh session resumes from bounded ContinuationPackage instead of full historical chat/repo dump.

---

# 18. DDE-081 — Mission Workspace + Execution Graph + Node Inspector

**Priority:** P1

## 18.1 Mission Workspace

Show projects/missions, requirement coverage, current strategic occupant, active tasks/workers/design sessions, blockers, quality, evidence, provider degradation and attention.

## 18.2 Real Execution Graph

Project actual TaskGraph/WorkerSession/DesignSession/event/evidence state. Show dependencies, parallelism, retries, fallbacks, role transitions, human gates, verification, design branches and integration.

No manually maintained duplicate graph truth.

## 18.3 Node Inspector

Inspect normalized inputs/context manifest, routing candidates/decision, exact worker/model/harness/config, tools/capabilities, ChangePacket/workspace, artifacts/diff, cost/usage, failures and verification/evidence.

Hidden chain-of-thought is neither required nor persisted.

## 18.4 Runtime controls

Where policy permits:

```text
replay exact
reroute
fork
compare
cancel
resume
open evidence
```

All preserve lineage and policy.

## 18.5 Run Comparison

Compare verified outcome, patch/artifacts/evidence, cost, latency, rework, human intervention and failure signatures.

## 18.6 Route explainability + Attention Center

`Why this route?` is derived from stored hard gates/scores/experience/capacity. Attention classes remain `IMMEDIATE`, `REVIEW_QUEUE`, `DAILY_SUMMARY`, `INFORMATIONAL`.

## 18.7 Acceptance

Operator manages a mission, inspects exact nodes, understands fallback, compares runs and invokes legal replay/reroute without raw agent terminals or a second state store.

---

# 19. DDE-082 — Design Intelligence + Design Gateway + Playbooks/Workflow Composer

**Priority:** P1/P2

DDE-069 establishes the usable live-design foundation. DDE-082 completes design intelligence and generalizes successful workflows.

## 19.1 DesignExplorationCompiler

Separate creative exploration from conformance. It may propose token/type/layout/component/motion grammar but cannot commit authority.

## 19.2 DesignCandidate competition

Generate genuinely distinct directions through certified design configurations, including Claude Design and future providers where eligible.

## 19.3 ProductDesignAuthority

Human promotion creates immutable DDE-owned authority plus machine-readable implementation constraints.

## 19.4 Full DesignGateway hardening

Complete provider health/fallback, session continuity, design-system synchronization, egress ledger, candidate branching, immutable design/code promotion, provider-neutral certification and cost controls.

## 19.5 Design Skill Registry

Version/certify external design skills/guidelines and DDE-native specialists. Skills advise; ProductDesignAuthority/policy govern.

## 19.6 Workflow Registry / Playbooks

Convert verified recurring patterns into versioned workflow candidates. Definitions express capabilities/constraints, not unnecessary model pins.

```text
candidate
→ replay/holdout
→ shadow
→ canary
→ promoted
```

Hermes may discover; DDE promotes.

## 19.7 Visual Workflow Composer

Build a visual authoring surface that **compiles into DDE's validated workflow model**. It is not an alternate runtime.

Block illegal edges, missing mandatory gates, unsatisfied capabilities, unauthorized Project Truth mutations and provider-specific semantics leaking into core contracts.

## 19.8 Opal boundary

Do not make Opal a runtime dependency. Adopt only the high-value UX/inspectability patterns natively.

## 19.9 Acceptance

Prove genuinely distinct design candidates, immutable selected authority, design/live-code/verification loop, evidence-gated playbook promotion, and a composer-authored workflow executing through the same runtime/events as API-authored workflow.

---

# 20. DDE-083 — Rev 3 System Hardening, Chaos & Release Candidate

**Priority:** P1

DDE-083 proves the consolidated architecture under failure.

## 20.1 Golden missions

At minimum:

1. small backend feature;
2. Android feature;
3. cross-platform product feature;
4. risky database migration;
5. frontend redesign through design/live loop;
6. recovery after worker kill;
7. quota exhaustion and strategic fallback;
8. provider auth failure;
9. conflicting parallel edits;
10. visual repair loop;
11. context-pressure continuation;
12. rejected-packet contamination attempt;
13. harness/tool update candidate.

## 20.2 Bootstrap chaos

Wrong root, unrelated bootstrap, approved parent/root, foreign config, broken config link, partial/duplicate bootstrap.

## 20.3 Orchestration chaos

Fable exhaustion, Opus temporary occupancy, Fable timed recovery, Opus subordinate re-entry, no premium creep, Core restart during fallback.

## 20.4 Runtime-capability chaos

Expected hook absent; installed version changes hook set; documented capability unavailable in installed build.

## 20.5 Context chaos

Context exhaustion before high-risk task → checkpoint → fresh-session continuation with correct lineage.

## 20.6 Change governance chaos

Rejected mutations + later broad staging; contamination blocked; concurrent packet conflict; staged scope mismatch.

## 20.7 Evidence chaos

Unrelated change preserves evidence; relevant invariant selectively invalidates evidence; stale verification cannot be shown as current.

## 20.8 Design chaos

Provider unavailable, stale design-system sync, Try-Live build failure, inspector edit then provider refinement, artboard attempts false LIVE state, promoted design/code divergence before verification.

## 20.9 Managed executable updates

Hermes/Claude/Codex/DeepSeek/MCP/skill/plugin updates follow:

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

Regression → rollback. Stable active version remains untouched until candidate promotion.

## 20.10 Release proof

Full tests/contracts/migrations, golden missions, chaos/recovery, truth-drift report, fleet certification snapshot, cost/quota report, security/egress evidence, visual/operator verification and update rollback proof are mandatory.

---

# 21. Cross-mission infrastructure

## 21.1 Schema-first contract families

Plan schema/change-control changes for:

```text
identity/bootstrap
strategic role occupancy
runtime capability discovery
context budget/continuation
ChangePacket/staging/commit governance
evidence validity/delta audits
design sessions/artifacts/live-edit workspaces
execution-graph projection
workflow/playbook registry
tool-update candidates/certification
```

Extend existing accepted owners instead of duplicating them.

## 21.2 Event model

Normalize durable events for bootstrap, role acquisition/release, planning/routing, session lifecycle, context pressure, ChangePacket lifecycle, staging/commit gates, design candidate/Try-Live/promotion, verification/evidence invalidation, provider capacity, experience/policy candidates and tool updates.

Provider-native event shapes remain adapter-local.

## 21.3 Gateway/API/MCP

Any user-facing or external control action must map to existing or newly accepted governed command/read surfaces. No UI-only mutation path.

## 21.4 Database/migrations

New persistent authorities require tenant/project ownership, RLS where applicable, forward/reverse migration proof, indexes/uniqueness for idempotency and explicit retention/audit rules.

## 21.5 Managed update infrastructure

Introduce `ToolUpdateManager` before release certification. Risk classes:

- A non-executable metadata/content;
- B bounded executable components;
- C core runtime/control-plane components.

Class B/C require certification/canary/rollback appropriate to risk.

---

# 22. Frontend Studio implementation details

## 22.1 Shared product shell

Use the same built UI assets across supported VS Code/Cursor and Electron surfaces where feasible. Keep host differences behind the bridge.

## 22.2 Honest state

Implement loading, empty, unavailable, degraded, blocked, failed, waiting-for-capability, running, verifying, complete and stale states from real backing data. Never fabricate mission/fleet/design/evidence rows.

## 22.3 Live canvas

The live canvas is a ProductEnvironment/PreviewRuntime output. It supports viewport/state selection, stable element anchors, responsive preview, interaction playback and out-of-sandbox selection overlays.

## 22.4 Artboard vs live split

Optional split view:

```text
[ DESIGN ARTBOARD ] | [ REAL LIVE CANDIDATE ]
```

Visual diff overlay may compare them. Artboard never serves as implementation proof.

## 22.5 Inspector/direct manipulation

Known token/component edits compile deterministically. Drag/resize maps to legal semantic operations or a design request, not arbitrary inline-style mutation.

## 22.6 Design Dock/candidate strip

Surface intent, selected scope, requirements, provider/session, design-system version, candidate lineage/status, warnings and governed actions—not provider chat dumps.

## 22.7 Execution Graph UX

Every shown executed node links to durable task/session/event/evidence identity. No runtime source → do not display it as executed.

---

# 23. Frontend Studio design quality benchmark

DDE Code and generated products must be evaluated for:

- clear visual hierarchy;
- coherent typography and spacing;
- appropriate density;
- intentional composition;
- product-specific memorable features;
- accessible states/keyboard/reduced motion;
- responsive quality;
- believable data/content;
- generic-layout fingerprint avoidance;
- controlled motion;
- professional loading/error/degraded/blocked states.

A functionally correct generic AI dashboard can fail Definition of Polished.

DDE should dogfood its own DDE-068 + DesignGateway pipeline for later DDE Code UI changes once the necessary foundations are evidence-complete.

---

# 24. AI design workflow integration

## 24.1 Stable boundary

`DesignGateway` + provider adapters are the durable interface. Do not hard-code DDE state to `/design` syntax or native provider-canvas embedding.

## 24.2 Candidate-count/cost policy

Candidate count is materiality/risk/cost aware. Do not generate multiple expensive alternatives for trivial deterministic changes.

## 24.3 Live refinement

```text
real live candidate
→ selected semantic context
→ provider refinement
→ design candidate
→ Try live
→ real live candidate
```

## 24.4 Promotion

Exploratory candidates remain isolated. Promotion freezes exact design and code identity. Merge eligibility begins only after normal verification.

## 24.5 Provider degradation

Mandatory design unavailable → waiting/degraded state or approved alternate. Never silent bypass.

## 24.6 Opal-derived native features

Implement workflow visual clarity, real execution graph, node inspector/debugging, replay/reroute/fork/compare, workflow/playbook library and policy-compiled visual composer inside DDE. Do not integrate Opal as core runtime.

---

# 25. Testing strategy

Every mission requires applicable:

```text
unit
contract
integration
recovery
security
visual
chapter-gate
```

At least one acceptance test must traverse the **real production writer/reader/gate path** for every claimed capability. Mock-only success is not sufficient.

## 25.1 Operational-hardening tests

- wrong root / config contamination;
- role occupancy fallback/restoration;
- worker-pool exclusion/re-entry;
- context threshold/continuation;
- ChangePacket rejection disposition;
- staged-scope mismatch;
- evidence selective invalidation;
- update quarantine/canary/rollback.

## 25.2 Design integration tests

- DesignGate classifier;
- DesignGateway/provider normalization;
- egress allowlist/redaction;
- stale design-system hash;
- candidate lineage;
- Try-Live isolation;
- semantic DESIGN/LIVE/VERIFIED states;
- promotion immutability;
- PreviewRuntimeAdapter;
- live-state refinement;
- provider outage fail-closed.

## 25.3 Execution graph/workflow tests

- graph runtime derivation;
- retry/fallback/human-gate projection;
- node lineage;
- replay/reroute/fork lineage;
- illegal-edge/mandatory-gate compilation;
- composer-authored workflow runs through same engine as API-authored workflow.

## 25.4 Studio product tests

Component, bridge, accessibility, keyboard, visual, fake-Gateway, real-Gateway fixture, Electron smoke and VS Code webview smoke.

---

# 26. CI additions

Target deterministic PR gates include:

```text
truth-check
bootstrap-contract-check
fleet-contract
agent-protocol-contract
staging-scope-contract-check
evidence-validity-check
design-contract-check
workflow-compiler-contract-check
studio-unit
studio-accessibility
studio-visual
product-visual
golden-missions
routing-replay
tool-update-certification-tests
```

Do not require live premium providers on every PR. Use deterministic fixtures for PR gates and scheduled/release-gate live-provider certification/probes.

---

# 27. Cost governance

Initial model/harness affinities are priors, not permanent assignments.

Cost accounting must separate:

- strategic-orchestrator spend;
- ordinary premium-worker spend;
- verification/reviewer spend;
- design-provider spend;
- provider-probe spend;
- failed/rework spend.

Prefer deterministic mechanisms for mechanical work. Use lower-cost workers where verification can arbitrate quality. Use premium reasoning where expected verified outcome justifies it.

A route is not cheaper if rework, human intervention or failures increase `cost_per_verified_success`.

---

# 28. Definition of success

Rev 3 is successful when DDE can repeatedly manufacture software through the consolidated control plane and prove what happened.

Required outcomes:

- project/bootstrap identity cannot silently cross-contaminate repositories;
- strategic role occupancy fails over/restores without premium-model creep;
- worker configurations are selected from certified installed capabilities;
- Hermes improves context/experience discovery without becoming authority;
- context exhaustion produces safe continuation;
- rejected work cannot contaminate later commits;
- evidence is selectively reused/invalidated;
- provider quota/cost/health drive real routing;
- DDE-068 visual verification is real production evidence;
- Frontend Studio moves from design artifact to isolated real LIVE candidate and back;
- only promoted design/code pairs become merge-eligible;
- execution graph and node inspector show actual runtime truth;
- replay/reroute/fork preserve lineage;
- reusable playbooks promote only through evidence;
- Workflow Composer compiles into the same governed engine;
- managed executable updates can be certified/canaried/rolled back;
- operator UI is professional and honest;
- capability-realisation report has no high-severity overclaims;
- golden/chaos missions pass;
- cost per verified success and human intervention are measurable.

---

# 29. Non-negotiable anti-drift rules

1. Project Truth/accepted EDRs outrank this plan.
2. Blueprint Rev 3 defines architecture; this plan cannot silently change it.
3. Do not create a second Rev 3 blueprint/plan hierarchy under another folder.
4. Do not reintroduce static model-role architecture.
5. Do not interpret Fable recovery as “Fable orchestrates, Opus becomes default premium worker”.
6. Do not let Hermes memory self-promote routing policy.
7. Do not start high-risk work in an unsafe context state.
8. Do not leave rejected mutations anonymous in a shared tree.
9. Do not use broad staging in controlled work without explicit packet authorization.
10. Do not blanket re-audit evidence unaffected by a change.
11. Do not label provider artboards LIVE.
12. Do not let design output mutate accepted code without Try-Live/promotion governance.
13. Do not build a decorative execution graph or parallel workflow runtime.
14. Do not pin workflow playbooks to models unless a capability requirement demands it.
15. Do not silently auto-update executable workers/tools/plugins.
16. Do not call a capability complete until production call sites and evidence meet the Blueprint closure matrix.

---

# 30. Consolidation source evidence

This plan is grounded in:

- current `Vanguduza/dde` Rev 3 truth/bootstrap repository state;
- original DDE Blueprint Rev 3.0;
- original DDE Rev 3 Development & Realisation Plan;
- Rev 3 quantum audit and design-intelligence audit;
- Rev 3.1 Operational Hardening / Adaptive Routing amendment;
- Claude `/design` + high-value Opal integration addendum;
- existing DDE-065/066/067 implementation evidence and chapter-gate sequence.

The standalone amendment/addendum documents remain historical evidence after adoption. Their forward requirements are mapped into the relevant gates/missions above.

---

# 31. Immediate next action

After this consolidated source-of-truth update is merged:

> **Execute REV-3A Operational Safety Gate before DDE-068.**

Start with **REV-3A.1 ProjectIdentity / bootstrap preflight**, because wrong-root/config contamination can invalidate every subsequent agent/workflow decision.

Then:

```text
REV-3A.1 identity/bootstrap
→ REV-3A.2 strategic occupancy safety
→ REV-3A.3 context/continuation
→ REV-3A.4 ChangePacket/rejection/staging
→ REV-3A.5 evidence validity/delta audit
→ REV-3A gate review
→ DDE-068
```

Do not reopen DDE-065/066/067 unless the delta touches an invariant they depend on or current code evidence shows regression.

The next implementation session must first verify current repository HEAD/state, then execute the smallest evidence-producing REV-3A slice. It must not spend the session rewriting this plan.

---

# Appendix A — Mission-to-capability ownership matrix

| Capability | First safety/foundation gate | Full owning mission |
|---|---|---|
| Project identity/bootstrap | REV-3A.1 | DDE-070 |
| Strategic role occupancy | REV-3A.2 | DDE-071 |
| Context budget/continuation | REV-3A.3 | DDE-070 / DDE-080 |
| ChangePacket/rejection/staging | REV-3A.4 | DDE-077 |
| Evidence validity/delta audit | REV-3A.5 | DDE-080 |
| Visual verification | — | DDE-068 |
| Frontend Studio live-design foundation | — | DDE-069 |
| WorkerSession/Harness V2 | — | DDE-070 |
| Codex worker | — | DDE-072 |
| Claude coding worker capability discovery | — | DDE-073 |
| DeepSeek worker | — | DDE-074 |
| Hermes experience intelligence | — | DDE-075 |
| Persistent fleet/provider capacity | — | DDE-076 |
| Real cost/quota/occupancy telemetry | — | DDE-078 |
| Empirical routing | — | DDE-079 |
| Execution graph/node inspector actions | read-only seed DDE-069 | DDE-081 |
| Design intelligence/playbooks/composer | live-loop seed DDE-069 | DDE-082 |
| Managed executable updates | policy foundation earlier | DDE-083 release proof |

---

# Appendix B — Per-mission chapter-gate checklist

Every numbered mission and REV-3A slice closes only when the gate records:

- authoritative Blueprint clauses;
- accepted EDRs;
- changed schemas/contracts;
- production writers/readers;
- Gateway/API/UI paths;
- actual state transitions;
- failure/cancel/retry/recovery semantics;
- capabilities/credentials/egress;
- migration and evidence-inheritance effects;
- tests and real evidence;
- observed capability-realisation state;
- residuals/deferred items;
- exact next dependency.

Allowed result:

```text
PASS
PASS-WITH-EDR
FAIL
```

A green test suite alone is never a mission PASS.
