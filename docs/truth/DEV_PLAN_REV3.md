# DDE Rev 3 Development & Realisation Plan — Consolidated Canonical Edition

**Canonical repository path:** `docs/truth/DEV_PLAN_REV3.md`  
**Status:** **CANONICAL FORWARD DEVELOPMENT PLAN**  
**Effective:** 2 September 2026  
**Consolidated revision:** Rev 3.3 — Dial Depth-and-Breadth Hardened  
**Repository:** `Vanguduza/dde`  
**Architecture authority:** `docs/truth/BLUEPRINT_REV3.md`  
**Inherited product baseline:** DDE-067 at `c30d2969e3205d1a277dd128e8b182137a8892e0`  
**Inherited Rev 3 repository-memory baseline:** `fcc3e542ebc98ce769ec7ca74de72887dc5e5c02`  
**Purpose:** move the existing DDE repository to the consolidated Rev 3 architecture without restarting, duplicating closed work, re-auditing unaffected evidence, or confusing documentation with runtime completion.

> This plan absorbs the original Rev 3 Development Plan, the Rev 3 quantum audit/realisation findings, Rev 3.1 operational hardening, the Claude `/design` + high-value Opal integration plan, and the September 2026 live orchestrator-control/serving-model-attestation findings. Those inputs remain historical evidence after adoption; this file is the single forward implementation sequence. **Rev 3.3 adds normative Dial depth-and-breadth implementation packs so every mission closes traceability, contracts, state, failure, security, observability, operations, cross-platform parity and certification rather than leaving those concerns to implementation-agent inference.**

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

### 0.1 Dial depth-and-breadth implementation rule

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

### 0.2 Evidence inheritance

Do not re-audit or rebuild work already proven by chapter gates/evidence unless the current change modifies a dependency or invariant that invalidates that evidence.

### 0.3 No static model-role implementation

Mission code must express capabilities, role occupancy and worker eligibility. Static mappings such as `Fable=strategy`, `Opus=reasoning`, `Codex=coding` may exist only as decaying priors or configuration defaults, never architectural truth.

### 0.4 No design/runtime theatre

A design artboard is not a live application; an execution graph is not valid unless projected from actual runtime state; a workflow composer is not allowed to create a second orchestration engine.

### 0.5 No model-identity theatre

For orchestrator sessions:

```text
DESIRED ≠ CONFIGURED ≠ SERVING
```

unless authoritative runtime evidence proves equality.

A settings file, tier state or session-start preference may prove what the next/new session was configured to request. It does not prove which model is actually serving a running parent session. Unknown remains unknown, and model-specific completion/occupancy claims require sufficient `ModelServingEvidence` for the risk policy.

---

# 1. Starting state — what is already real

The following should be treated as existing infrastructure to preserve and compose, not recreate:

- authoritative Project Truth model;
- requirements and mission state;
- immutable RouteDecision persistence;
- deterministic routing hard gates;
- route health eviction from real outcomes;
- shadow/canary/promoted policy activation;
- model-assisted PlanDraft validation/promote boundary;
- TaskAttempt;
- WorkerRun;
- WorkerEvent;
- certified WorkerAdapter abstraction;
- Worker Manager;
- capability leases;
- ExecutionEnvironment;
- Workspace;
- external-effect journal;
- recovery matrix;
- checkpoints;
- idempotency CommandLedger;
- attempt budgets;
- runtime usage writer;
- evidence;
- verification runner;
- AcceptanceOracle;
- API probe and visual-diff evidence;
- Donor Lab;
- Frontend generation prompt compiler;
- Frontend Studio Gateway mutation path;
- design-token SSOT;
- design lint ratchet;
- Prototype Gallery;
- six Frontend Studio contributed views;
- Windows installer / VS Code / Electron product surfaces.

Do not build parallel replacements.

---

# 2. Starting state — what is only partial

## 2.1 Routing predictions

Current fields exist but are not produced:

```text
predicted_success
predicted_cost
predicted_latency
confidence
```

## 2.2 Model selection

Current model selection annotates declared models and does not bind a real provider execution.

## 2.3 Worker fleet

Actual adapters present:

```text
android
claude
cursor
donor
opensandbox
playwright
security
```

Missing first-class production adapters:

```text
codex
hermes
deepseek
```

## 2.4 Claude

Path A is executable but:

- synchronous;
- individually human-approved;
- not a normal routed worker;
- non-resumable;
- no real token telemetry.

## 2.5 Cursor

Current adapter is a fail-closed policy shell even though some README language implies a live SDK bridge.

## 2.6 WorkerSession

Specified in Blueprint 2 but absent in Worker Manager runtime.

## 2.7 Usage

Budget writer exists. No live hosted-model producer currently forwards genuine usage.

## 2.8 Worker registry

Router uses static facts.

Worker Manager uses an in-memory registry.

Those realities can diverge.

## 2.9 Frontend Studio

The current six-view DDE-067 surface proves command wiring but is not the final product UX.

The current `frontendStudio.ts` is primarily:

- mission UUID fields;
- command select;
- raw JSON parameter textarea;
- minimal canvas buttons/drop zone;
- token selects.

The richer three-pane editor described by the GUI spec is not realized at professional workbench quality.

## 2.10 Visual verification

DDE-068 is not implemented.

Pixel signoff intentionally refuses.

## 2.11 Event push

Studio does not have true real-time multi-client event transport.

## 2.12 Truth drift

README/adapter and historical planning status contradictions can still exist.

---

# 3. Program governance

## 3.1 Rev 3 source-of-truth consolidation gate

The repository already completed an initial Rev 3 truth bootstrap. This consolidation updates that bootstrap rather than creating a second `REV_3_0.md` hierarchy elsewhere.

Canonical forward files remain:

```text
docs/truth/BLUEPRINT_REV3.md
docs/truth/DEV_PLAN_REV3.md
```

Supporting controlled projections remain:

```text
docs/truth/ARCHITECTURE_DECISIONS.md
docs/truth/IMPLEMENTATION_STATE.md
docs/truth/RESUME_PROMPT.md
```

Gate criteria for this consolidation:

- Blueprint absorbs Rev 3.1 and Claude Design/Opal addenda;
- Development Plan absorbs their sequencing/acceptance changes;
- README/AGENTS/bootstrap pointers remain consistent;
- supporting truth projections do not contradict the two canonical documents;
- Rev 2 and standalone addenda are explicitly historical/reference where conflicts occur;
- no product capability is falsely promoted merely because documents changed.

## 3.2 REV-3A Operational Safety Gate — next implementation gate

**Do not renumber DDE-068 through DDE-083.**

REV-3A is a short implementation safety gate that makes DDE development itself safer before subsequent numbered missions.

Required outcomes:

1. project identity enforcement;
2. no unrelated-root configuration contamination;
3. explicit desired/configured/serving orchestrator-model state;
4. orchestrator-control level and serving-model attestation disclosure;
5. Fable/Opus next-session fallback/restoration semantics for config-only runtimes and true lease occupancy only for attested runtimes;
6. ordinary worker-pool eligibility rules;
7. context checkpoint rule;
8. `ContinuationPackage` format;
9. packet-scoped mutable work;
10. rejected-work disposition;
11. staging-scope guard;
12. evidence inheritance / no blanket re-audit.

### 3.2.1 REV-3A vertical slices

#### REV-3A.1 — ProjectIdentity preflight

Contracts:

```text
ProjectIdentity
RuntimeRoot
SessionBootstrapContract
EffectiveExecutionConfiguration
BootstrapReceipt
```

Acceptance:

- approved root resolves the expected project;
- wrong/unregistered root fails closed;
- unrelated project cannot inherit DDE/Dial config;
- effective configuration can be reconstructed from recorded sources/hashes;
- no work is accepted without PASS receipt.

#### REV-3A.2 — Orchestrator model-state / attestation safety shim

Implement the smallest truthful control needed by current development workflows. The current repo-level Claude Code mechanism is **configuration-only for the next/new session**; it cannot prove the model serving the already-running parent session.

Minimum contracts/projections:

```text
OrchestratorModelState
ModelServingEvidence
ModelControlCapabilities
StrategicOrchestratorLease (requested/unattested state only where live occupancy cannot be proved)
```

Current Claude Code acceptance:

```text
desired=fable + configured=fable
→ SERVING=unknown
→ compliance=REQUESTED_UNATTESTED
→ status output says CONFIGURED=fable, never FABLE_ACTIVE
```

Fallback acceptance:

```text
Fable quota/unavailability observed
→ configure next/new session for Opus fallback
→ do not claim current parent changed model
→ serving remains unknown unless attested
```

Restoration acceptance:

```text
Fable reset/recovery eligibility
→ configure next/new session Fable-preferred
→ do not claim Fable is serving from configuration/reset alone
```

Subagent/worker routing remains separately enforceable. If a bounded packet is explicitly dispatched to Fable and the worker execution proves that model, record **Fable packet evidence**, not “Fable orchestrated the parent session.”

Target native runtime acceptance is deferred to DDE-071/DDE-073:

```text
OCL-3 Fable attested active → Opus ordinary candidate
OCL-3 Fable unavailable → Opus attested temporary occupant; Opus removed from conflicting ordinary pool
OCL-3 Fable restored → atomic checkpoint → Fable attested occupant; Opus ordinary candidate
```

No premium-model creep, no stale fallback state and no configured→serving overclaim.

#### REV-3A.3 — ContextBudget + continuation

Add runtime/session guardrails:

```text
HEALTHY
PRESSURE
CHECKPOINT_REQUIRED
UNSAFE_FOR_HIGH_RISK_WORK
```

Acceptance: a high-risk task under unsafe remaining context checkpoints, creates a ContinuationPackage and resumes in a fresh session rather than starting.

#### REV-3A.4 — ChangePacket / rejection / staging guard

Introduce or minimally wire:

```text
ChangePacket
DeclaredWriteSet
RejectionDisposition
StagingManifest
CommitManifest
```

Acceptance:

```text
Worker A changes files
→ Packet A rejected/dispositioned
→ Worker B performs accepted work
→ broad/accidental staging attempted
→ ZERO Packet A mutations enter Worker B commit
```

Unexpected staged paths block.

#### REV-3A.5 — Evidence-validity guard

Introduce a minimal `EvidenceValidityGraph`/delta-audit mechanism or equivalent accepted mapping.

Acceptance:

- unrelated change preserves previous evidence;
- changed invariant invalidates only affected evidence;
- continuation package identifies required re-verification and forbidden rework.

### 3.2.2 REV-3A gate proof

Before DDE-068:

- focused contract/invariant tests pass;
- repository full checks pass;
- operational chapter-gate record maps each required outcome to real call sites;
- `IMPLEMENTATION_STATE.md` is updated from evidence;
- no numbered product mission is marked progressed by REV-3A unless its own acceptance is separately met.

---

# 4. Mission sequence and dependency graph

The canonical sequence is:

```text
REV-3 SOURCE-OF-TRUTH CONSOLIDATION
        │
        ▼
REV-3A OPERATIONAL SAFETY GATE
        │
        ▼
DDE-068  Visual Verification & Critique Loop
        │
        ▼
DDE-069  DDE Code / Frontend Studio V2 + Live Design Foundation
        │
        ▼
DDE-070  Harness Contract V2 + WorkerSession + Bootstrap Runtime
        │
        ▼
DDE-071  Strategic Orchestrator Runtime + Serving-Model Attestation
        │
        ▼
DDE-072  Codex Native Worker
        │
        ▼
DDE-073  Claude Agent SDK Worker + Model-Control Capability Discovery
        │
        ▼
DDE-074  DeepSeek Harness Worker
        │
        ▼
DDE-075  ACP + Hermes Experience Intelligence
        │
        ▼
DDE-076  Persistent Fleet Registry + Provider Capacity
        │
        ▼
DDE-077  TaskExecutionDescriptor + Strategy + Change/Workspace Ownership
        │
        ▼
DDE-078  Real Usage / Cost / Quota / Context / Occupancy Telemetry
        │
        ▼
DDE-079  Empirical Routing + Route Critic
        │
        ▼
DDE-080  Truth / Context / Evidence-Validity Compilers
        │
        ▼
DDE-081  Mission Workspace + Execution Graph + Node Inspector
        │
        ▼
DDE-082  Design Intelligence + Design Gateway + Playbooks/Workflow Composer
        │
        ▼
DDE-083  System Hardening / Chaos / Update Certification / Release Candidate
```

### 4.1 Overlap rule

Isolated branches/work packets may overlap when dependencies and write ownership allow it, but chapter-gate dependencies control promotion.

### 4.2 Do not renumber history

DDE-068 through DDE-083 retain their numbers. Changes below refine scope and acceptance; they do not create a parallel mission series.

---

# 5. DDE-068 — Visual Verification & Critique Loop

**Priority:** P0  
**Reason:** Existing sequence already names it as next; Frontend Studio V2 must be judged by a real visual pipeline rather than subjective screenshots.

## 5.1 Goals

Close:

- DD207+ combination lints;
- silhouette distinctiveness;
- believable density;
- reduced-motion semantics;
- rendered evidence;
- multimodal critic;
- bounded critique/repair;
- pixel signoff approval.

## 5.2 Existing seams to use

Do not rebuild:

- `engine.verification`;
- Playwright adapter;
- Prototype Gallery;
- `visual_diff`;
- prototype flow validator;
- design token lints;
- EDR-0016 authorization;
- Frontend Studio Verify view.

## 5.3 New contracts

Suggested:

```text
schemas/objects/visual_contract.json
schemas/objects/visual_verification_result.json
schemas/objects/visual_critique.json
schemas/objects/render_artifact.json
```

### `VisualContract`

Minimum:

```yaml
feature_id:
required_states:
breakpoints:
required_interactions:
accessibility_requirements:
density_floor:
density_ceiling:
motion_requirements:
reduced_motion_requirements:
brand_requirements:
negative_patterns:
```

## 5.4 ProductEnvironment renderer

Implement a production verification service that:

1. receives a verification plan;
2. starts/resolves ProductEnvironment;
3. seeds deterministic fixture data;
4. navigates real workflow;
5. captures screenshot/video/DOM geometry;
6. runs accessibility;
7. creates immutable render artifacts;
8. feeds deterministic and model evaluators.

Do not evaluate only the compiler's `preview_html`.

## 5.5 Deterministic visual evaluators

Implement:

- viewport overflow;
- clipping;
- tap target;
- text truncation;
- focus visibility;
- token conformance;
- spacing/grid deviations;
- contrast;
- state coverage;
- responsive integrity;
- reduced-motion preservation;
- icon-family check;
- silhouette fingerprint.

### Silhouette

Normalize rendered layout into approximate blocks:

```text
header
navigation
primary-content
secondary-content
repeated-groups
footer/action-region
```

Generate a feature vector based on:

- block occupancy;
- alignment;
- repeated structure;
- card/grid topology;
- whitespace distribution.

Compare against a generic AI-layout corpus.

Do not use silhouette score as a copyright similarity detector. It is an anti-template distinctiveness instrument.

## 5.6 Believable density

For operator/product screens evaluate:

- information regions;
- empty whitespace ratio;
- number of actionable elements;
- realistic fixture data;
- density by viewport;
- whether decorative chrome overwhelms function.

## 5.7 VLM critic

The multimodal critic receives:

- rendered images;
- VisualContract;
- ProductDesignAuthority/design intent;
- deterministic findings;
- no implementer self-rating.

Return structured dimensions:

```text
hierarchy
typography
composition
distinctiveness
interaction_clarity
motion_quality
content_believability
platform_fidelity
brand_coherence
polish
```

## 5.8 Bounded repair

Policy:

```text
max_cycles = 2 by default
hard maximum = 3
```

Each cycle:

```text
stored critique
→ repair task
→ render
→ re-evaluate
```

After max cycles:

- block automatic progression;
- require human signoff or Fable replan depending failure type.

## 5.9 Pixel signoff

Add `prototype_pixel_signoff`.

It may waive subjective visual threshold only.

It may never waive:

- functional breakage;
- accessibility hard failure;
- missing required state;
- security;
- off-token committed implementation.

## 5.10 Acceptance

DDE-068 is `VERIFIED` only when a real fixture feature performs:

```text
build
→ deploy ProductEnvironment
→ render 3 widths
→ deterministic checks
→ VLM critique
→ repair
→ rerender
→ PASS
→ immutable evidence
```

---

## 5.9 Consolidated dependencies

DDE-068 begins only after REV-3A passes.

New binding rules:

- visual verification binds to exact code revision and, where applicable, promoted `DesignArtifact` version;
- evidence participates in `EvidenceValidityGraph`;
- a rerender after an unrelated change may inherit prior unaffected proof;
- a visual repair occurs in a ChangePacket/isolated workspace;
- VLM/design critique remains evidence, not mutation authority;
- provider outage must not cause silent pass/bypass of a mandatory gate.


---

# 6. DDE-069 — DDE Code / Frontend Studio V2 Foundation

**Priority:** P0  
**Objective:** Replace DDE-067's command-console UX with a professional IDE-class workbench without changing Core authority or the proven command paths.

---

## 6.1 Product design register

Frontend Studio is **product UI**, not brand/marketing UI.

Design serves:

- software manufacturing;
- product planning;
- visual product engineering;
- quality control;
- multi-agent supervision.

Visual direction:

> **Precision Manufacturing Workbench**

Characteristics:

- dark-first;
- disciplined light mode;
- restrained one-accent palette;
- multiple structural surface levels;
- technical but approachable;
- compact;
- high information density;
- excellent typography;
- strong keyboard workflow;
- timelines/evidence rather than decorative charts;
- no gradients;
- no glassmorphism;
- no generic SaaS card grid.

---

## 6.2 UI runtime migration

The existing giant string templates become legacy renderers.

Introduce:

```text
interfaces/dde-studio/ui/
  src/
    app/
    shell/
    projects/
    missions/
    studio/
    quality/
    decisions/
    fleet/
    evidence/
    components/
    bridge/
    state/
  index.html
  vite.config.ts
```

Preferred stack after EDR/dependency admission:

```text
React
TypeScript
Vite
generated DDE CSS tokens
CSS Modules or authored CSS
```

No Tailwind or shadcn visual layer.

Reasons:

- complex split-pane UI;
- shared VS Code/Electron assets;
- lifecycle/state-heavy interactions;
- independent component tests;
- visual testability;
- AI agents generate and maintain React ergonomically;
- current string interpolation is no longer proportional to product complexity.

### Dependency gate

Before adding React/Vite:

- license;
- maintenance;
- package pin;
- CVE/security policy;
- Electron/webview CSP compatibility;
- bundle budget;
- why existing stack is insufficient.

Record via EDR/dependency admission process.

---

## 6.3 Host bridge

Create a stable bridge:

```ts
interface DdeHostBridge {
  postCommand(...)
  requestRead(...)
  subscribeEvents(...)
  openExternal(...)
  revealFile(...)
  showNativeNotification(...)
}
```

Implement:

```text
VsCodeHostBridge
ElectronHostBridge
TestHostBridge
```

UI code never calls `acquireVsCodeApi()` directly except inside bridge bootstrap.

---

## 6.4 State rules

The UI may hold ephemeral interaction state:

- selected screen;
- panel sizes;
- active tab;
- zoom;
- current filters.

It may not invent domain state.

All mission/task/worker/approval/evidence data is projection of Gateway reads/events.

Use:

```text
server state → immutable projection cache
local UI state → ephemeral store
```

Do not create client-side domain replicas.

---

## 6.5 App shell

Layout:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ DDE  Project / Mission                 Search / Command     Core Ready      │
├───────┬─────────────────────────────────────────────────────────────────────┤
│       │                                                                       │
│ Rail  │       active workspace                                   Inspector    │
│       │                                                                       │
├───────┴─────────────────────────────────────────────────────────────────────┤
│ Activity / Evidence / Verify / Console drawer                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Left rail

Icons with text on hover/expanded mode:

- Projects;
- Missions;
- Product;
- Design;
- Quality;
- Decisions;
- Fleet;
- Evidence.

### Top bar

- project breadcrumb;
- mission breadcrumb;
- command palette;
- Core status;
- current environment;
- attention count;
- user/profile.

### Context sidebar

Changes by workspace.

Example in Frontend Studio:

- screens;
- layers;
- components;
- references.

### Inspector

Contextual properties.

### Bottom drawer

Non-modal ongoing information.

---

## 6.6 DDE Code design-token V2

Do not mutate token values ad hoc inside components.

Create `schemas/design/dde-code-tokens-v2.json`.

Required semantic layers:

```text
surface.canvas
surface.base
surface.raised
surface.overlay
surface.selected
text.primary
text.secondary
text.tertiary
line.default
line.strong
accent.primary
accent.hover
accent.selected
status.success
status.warning
status.error
status.info
focus
```

Typography roles:

```text
display
section
body
label
caption
data
code
```

Recommended design direction:

- engineering-oriented open-source sans;
- matching/compatible mono;
- higher readability than current tiny 0.85rem body;
- strong numeric/data alignment;
- tabular numerals where supported.

No font files should be committed without proper license/provenance review.

---

## 6.7 Component primitives

Create DDE-specific primitives:

```text
AppShell
RailItem
ContextSidebar
WorkbenchHeader
SplitPane
InspectorSection
DataTable
StatusDot
StatusLabel
SegmentedControl
ToolbarButton
IconButton
Field
Select
SearchField
Tabs
CommandPalette
Timeline
EvidenceRow
QualityGate
AttentionItem
EmptyState
InlineError
Toast
Dialog
Drawer
ResizablePanel
```

Avoid a visual dependency on generic component-kit defaults.

Every primitive receives:

- keyboard tests;
- focus test;
- dark/light test;
- reduced-motion test;
- screenshot test.

---

## 6.8 Frontend Studio V2 workflow

Replace six disconnected forms with:

```text
Brief
Explore
References
Build
Motion
Verify
Ship
```

### Brief

- feature/mission summary;
- requirements;
- states;
- target platforms;
- DesignAuthority version;
- blockers.

### Explore

- candidate generation;
- candidate compare board;
- approve/reject/branch;
- model + skill provenance;
- design critique.

### References

- image/video;
- URLs;
- Figma;
- donor artifacts;
- reference DNA;
- licensing.

### Build

- live structured canvas.

### Motion

- selected interaction transition tooling.

### Verify

- real render evidence.

### Ship

- readiness and merge gate.

---

## 6.9 Build workspace

Four regions:

```text
┌──────────────────┬───────────────────────────────┬─────────────────────┐
│ Screens/Assets   │                               │ Properties          │
│ Layers           │          CANVAS               │ Layout              │
│ Components       │                               │ Type                │
│ Donors           │                               │ Appearance          │
│                  │                               │ Motion              │
│                  │                               │ Data/State          │
│                  │                               │ Provenance          │
├──────────────────┴───────────────────────────────┴─────────────────────┤
│ Activity | Verify | Evidence | Changes | Console                      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 6.10 Canvas capabilities

Implement incrementally:

1. screen selection;
2. state selection;
3. breakpoint presets;
4. zoom/pan;
5. click-to-select stable anchors;
6. external selection overlay;
7. legal drop-zone visualization;
8. add-by-click;
9. keyboard lift/move;
10. flow playback;
11. motion preview;
12. comparison mode;
13. screenshot/verification overlays.

All edits compile to existing structured Gateway command types.

---

## 6.11 Debug/advanced command mode

The existing raw JSON command mechanism remains accessible under:

```text
Developer → Command Inspector
```

It is not the normal UX.

The Inspector displays:

- outgoing command;
- idempotency key;
- payload;
- Gateway response;
- event correlation.

This preserves power/debuggability while removing raw JSON from ordinary authoring.

---

## 6.12 Frontend Studio V2 acceptance

The mission is not complete with a pretty mockup.

A user must be able to:

1. open a real mission;
2. see a real selected screen;
3. drag a legal component;
4. mutate the durable artifact through Gateway;
5. see the real preview refresh;
6. inspect provenance;
7. change a token-bound property;
8. run verification;
9. inspect actual evidence;
10. recover from a typed failed command;
11. navigate entirely by keyboard for core flows.

Visual battery must pass DDE-068.

---

## 6.12 Claude Design / DesignGateway foundation

DDE-069 now owns the **first usable Frontend Studio live-design loop**, not the full learned design-intelligence program.

Contracts/interfaces to establish:

```text
DesignProvider
DesignGateway
ClaudeDesignAdapter
DesignGateDecision
DesignSession
DesignArtifact
DesignEditContext
LiveEditWorkspace
PreviewRuntimeAdapter
DesignSystemRegistry
```

The implementation must remain provider-neutral even when Claude is the first certified provider.

### 6.12.1 Minimal vertical slice

Prove one real screen can:

```text
select screen/element
→ compile DesignEditContext
→ request Claude design candidate
→ persist/version DesignArtifact
→ user selects Try live
→ create isolated LiveEditWorkspace
→ route implementation worker
→ build/render real application
→ show LIVE badge
→ deterministic inspector edit
→ recompile live context
→ provider refinement
→ promote exact design/code pair
→ DDE-068 visual verification
```

If Claude Design capability is unavailable, a mandatory design task enters `WAITING_FOR_DESIGN_CAPABILITY` or routes to another certified design provider. It does not silently improvise a bypass.

### 6.12.2 Frontend Studio controls

Build toolbar:

```text
[Design with Claude] [Try live] [Compare] [Promote] [Verify]
```

Add Design Dock, candidate strip and `Claude Design` inspector tab.

Semantic badges:

```text
DESIGN
BUILDING
LIVE
PROMOTED
VERIFIED
DISCARDED
```

Only a code-backed preview runtime may use `LIVE`.

### 6.12.3 Three editing lanes

1. deterministic token/component edit;
2. contextual Claude-assisted edit;
3. divergent design/artboard generation.

Known design-system edits must not consume AI merely to change deterministic values.

### 6.12.4 Read-only execution graph seed

DDE-069 also introduces a **read-only** execution graph projection in the Studio shell if the required event/task state is available. It must project real runtime state only. Interactive replay/reroute/fork remains DDE-081.

### 6.12.5 Egress/security acceptance

- allowlisted exact context only;
- secrets/private user data excluded;
- provider context hashes/provenance recorded;
- design system version/hash recorded;
- provider artifact identity stored;
- provider UI embedding is optional, never architectural dependency.

## 6.13 DDE-069 completion evidence additions

In addition to the original workbench acceptance:

- design candidate is persisted as DDE artifact;
- Try-Live does not touch accepted/main workspace;
- real render proves candidate implementation;
- promotion freezes design version and code revision;
- independent verification is still required;
- graph projection cannot fabricate nodes.


---

# 7. DDE-070 — Harness Contract V2 + WorkerSession + Bootstrap Runtime

**Priority:** P0

DDE-070 makes worker sessions resumable and version-capability aware, and moves the REV-3A safety shim into the full native runtime.

## 7.1 Contracts

Add/extend:

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
OrchestratorModelState
ModelServingEvidence
ModelControlCapabilities
ContextBudget
ContinuationPackage
```

Do not duplicate an existing accepted contract; extend it through schema-first change control.

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

Failure is typed and fail-closed.

## 7.3 Adapter V2 contract

Conceptual methods:

```text
register
health
discover_capabilities
capabilities
open_session
resume_session
start_turn
stream_events
request_pause
resume_turn
cancel
collect_artifacts
collect_usage
close_session
cleanup
```

A compatibility wrapper may adapt safe synchronous V1 workers temporarily.

## 7.4 WorkerSession persistence

Persist:

```yaml
worker_session_id:
project_id:
mission_id:
task_id:
harness_installation_id:
worker_profile_id:
provider_session_ref:
model_endpoint_id:
workspace_id:
state:
bootstrap_receipt_id:
effective_config_hash:
orchestrator_model_state_id:
model_serving_evidence_id:
orchestrator_lease_id:
context_budget_id:
context_pressure_state:
continuation_package_id:
```

WorkerRun references the durable session.

## 7.5 Version-specific runtime capability discovery

For the exact installed version certify where applicable:

- persistent session/resume;
- lifecycle hooks;
- rate-limit events;
- model request/pinning;
- serving-model identity/attestation;
- mid-session model switching;
- provider acknowledgement/fallback visibility;
- structured output;
- usage/quota/reset metadata;
- tool interception;
- cwd/project-root/config behavior.

Distinguish documented, installed, certified and measured capability.

## 7.6 Events

Normalize native events into DDE events; vendor event schemas never become Core contracts.

## 7.7 Acceptance

Prove:

- wrong/unapproved root fails closed;
- approved root resolves correct project;
- effective configuration reconstructs exactly;
- open → run → pause → restart → resume → complete preserves lineage;
- missing expected installed capability causes certification/routing failure rather than assumption;
- context exhaustion creates continuation and resumes in fresh session;
- a configured/requested model is not reported as the serving model without certified evidence;
- the installation receives an explicit OCL-0/OCL-1/OCL-2/OCL-3 orchestrator-control certification.

---

# 8. DDE-071 — Strategic Orchestrator Runtime + Serving-Model Attestation

**Priority:** P0

DDE-071 implements a first-class **strategic role and model-control truth model**, not a model-specific architecture.

The mission must preserve this invariant:

> **Desired/configured/requested model state may never be represented as actual serving-model identity or live strategic occupancy without evidence from a certified runtime capability.**

## 8.1 Core contracts

```text
OrchestratorModelState
ModelServingEvidence
ModelControlCapabilities
StrategicOrchestratorLease
RoleTransition
RoleOccupancyEvent
OrchestrationPlan
```

Fable remains the preferred strategic model when policy, certification and capacity support it. Opus remains the initial fallback policy candidate. Neither fact alone proves the model serving a parent session.

## 8.2 Orchestrator-control levels

Certify the exact strategic harness/runtime:

```text
OCL-0  UNCONTROLLED
OCL-1  CONFIGURED
OCL-2  LAUNCH_CONTROLLED
OCL-3  RUNTIME_CONTROLLED_ATTESTED
```

### OCL-1

DDE can configure what a future/new session requests, but:

```text
DESIRED=fable
CONFIGURED=fable
SERVING=unknown
COMPLIANCE=REQUESTED_UNATTESTED
```

is the truthful state until stronger evidence exists.

### OCL-3

DDE can control/pin the strategic model and obtain authoritative serving-model identity. Only here may `ACTIVE_ATTESTED` strategic occupancy be asserted unconditionally.

## 8.3 State A — Fable attested active

For OCL-3:

```text
Fable = ACTIVE_ATTESTED strategic-orchestrator occupant
ordinary candidate pool may include:
Opus, Sonnet, Haiku, Codex, DeepSeek, local/specialist workers
```

Opus is not automatically preferred for subordinate work. It is a normal candidate selected by empirical routing.

For OCL-1/OCL-2, use `REQUESTED_UNATTESTED`; do not claim the above topology as observed parent-session fact.

## 8.4 State B — Fable unavailable

### OCL-1/config-only path

```text
Fable quota/unavailability evidence
→ configure next/new session Opus fallback
→ SERVING=unknown
→ disclosure required
```

No mechanism may claim that the running parent model changed.

### OCL-3/native path

```text
Fable attested unavailable
→ Opus = FALLBACK_ACTIVE_ATTESTED strategic occupant
→ Opus removed from conflicting ordinary worker pool
→ remaining certified workers continue routine execution
```

If Opus is unavailable/ineligible, route to another certified strategic worker or human decision according to policy.

## 8.5 State C — Fable restored

### OCL-1/config-only path

```text
provider reset/recovery eligibility
→ configure next/new session Fable-preferred
→ CONFIGURED=fable
→ SERVING=unknown until attested
```

### OCL-3/native path

```text
Fable recovery attested
→ atomic checkpoint
→ Fable reacquires ACTIVE_ATTESTED strategic lease
→ Opus releases strategic lease
→ Opus returns to ordinary eligible worker pool
```

## 8.6 High-risk model-specific requirement

If a requirement demands Fable-class review/orchestration but the parent is `REQUESTED_UNATTESTED`, policy must make the limitation explicit.

Allowed responses include:

- continue only if model identity is not a hard requirement;
- route a bounded explicitly Fable worker/subagent packet and record its own model evidence;
- start a newly controlled/attested session;
- block pending adequate control.

A Fable subagent packet proves Fable performed that bounded packet. It does not prove Fable orchestrated the parent session.

## 8.7 Structured planning path

```text
StrategicOrchestratorService.propose
→ PlanningRegistryService.submit_draft
→ validate_draft
→ approval when required
→ promote_draft
```

No direct task-graph writes.

## 8.8 Capacity integration

Provider capacity and reset metadata may change desired/configured state. Passive reset metadata is preferred over expensive probes.

A reset deadline may yield `REPROMOTION_ELIGIBLE`; it does not itself yield `SERVING_ATTESTED`.

## 8.9 Acceptance

Test all of:

- invalid strategic plan rejection;
- high-risk approval;
- valid promotion;
- desired/configured/serving state separation;
- OCL-1 configured-Fable with serving unknown;
- startup/status output cannot render configured as active;
- Fable quota exhaustion configures fallback without claiming live switch;
- Fable timed restoration configures preference without claiming live switch;
- bounded Fable subagent evidence is distinguishable from parent orchestration evidence;
- OCL-3 Fable attestation;
- OCL-3 Opus fallback exclusion from conflicting subordinate pool;
- OCL-3 atomic Fable restoration and Opus re-entry;
- serving-model mismatch state;
- no premium-model creep;
- no stale fallback lease after restart;
- model-specific completion claim blocks when required attestation is absent.

---

# 9. DDE-072 — Codex Native Worker

**Priority:** P0

## 9.1 Integration choice

Use Codex App Server/native documented programmatic interface.

Do not wrap only a one-shot CLI if richer session semantics are available.

## 9.2 Mapping

```text
Codex thread     → WorkerSession
Codex turn       → WorkerRun
item events      → WorkerEvents
diff             → artifact evidence
approval request → DDE governance
usage            → existing usage writer
```

## 9.3 Profiles

```text
profile.codex.general
profile.codex.backend
profile.codex.android
profile.codex.frontend
profile.codex.refactor
profile.codex.review
```

Profile variations need not be separate model installations; they are policy/tool/context configurations.

## 9.4 Acceptance

Run a real medium task end-to-end in an isolated worktree with:

- streaming;
- change collection;
- test execution;
- real usage;
- independent verification.

---

# 10. DDE-073 — Claude Agent SDK Worker

**Priority:** P0

## 10.1 Keep Path A

Do not delete the subscription/CLI Path A adapter.

Relabel accurately:

```text
profile.claude.personal_cli
```

## 10.2 Add managed/programmatic worker

Use Claude Agent SDK.

Capabilities:

- persistent sessions;
- structured output;
- hooks;
- explicit skills/plugins;
- programmatic permission mediation;
- real usage;
- streaming;
- subagents.

## 10.3 Bare/explicit configuration

Automation profiles must not silently inherit arbitrary developer MCP/hooks/plugins.

Each profile declares its allowed environment.

## 10.4 Hook mapping

```text
PreToolUse       → capability/scope gate
Permission       → ApprovalService
PostToolUse      → WorkerEvent / effect journal
SubagentStart    → child telemetry
PreCompact       → context/session evidence
SessionEnd       → WorkerSession lifecycle
```

## 10.5 Acceptance

Pause a DDE permission decision, resume the same WorkerSession and complete.

---

## 10.6 Version-specific capability certification

Certification records the exact:

```text
installed version
available models
persistent-session support
resume support
supported hooks
can_request_model
can_pin_exact_model
can_read_serving_model
can_change_model_mid_session
can_resume_session_with_new_model
provider_acknowledges_model
fallback_visible
fallback_controllable
certified orchestrator-control level
structured output
usage reporting
quota/reset metadata
tool interception
project-root/config-discovery behavior
```

DDE must not infer runtime behavior from generic provider documentation.

For the current Claude Code CLI/configuration path, certification must explicitly preserve the observed limitation: repository configuration can request the next/new session model but cannot attest the model serving a running parent session. If Agent SDK/native metadata later closes that gap, the exact installation may be promoted to OCL-2/OCL-3 only after contract tests prove it.

## 10.7 Relationship to Claude Design

The Claude Agent SDK coding worker and `ClaudeDesignAdapter` are separate capability/provider adapters even if they share a vendor identity.

- coding worker executes governed implementation tasks;
- design adapter produces/refines design artifacts;
- either may be unavailable independently;
- one may not bypass the other's gate;
- routing telemetry measures them independently.


---

# 11. DDE-074 — DeepSeek Harness Worker

**Priority:** P1

## 11.1 Purpose

High-throughput economical engineering and controlled fan-out.

## 11.2 Integration

Use pinned DeepSeek Harness SDK/JSON-RPC.

## 11.3 Tool surface

Expose only DDE-leased tools.

No unrestricted shell/environment inheritance.

## 11.4 DelegationPolicy

Default:

```yaml
max_depth: 2
max_children: 3
```

Allow:

- read-only research;
- owned-scope edit;
- independent review.

Forbid:

- Truth;
- merge;
- routing;
- approval;
- credential policy.

## 11.5 Acceptance

One parent task may spawn bounded children; all child activity is attributable and no child escapes workspace scope.

---

# 12. DDE-075 — ACP + Hermes Experience Intelligence

**Priority:** P1

## 12.1 ACP client

Implement the generic ACP client and negotiate only capabilities actually present:

- session create/resume/list where supported;
- prompts/streaming;
- tools/permissions;
- fork/cancel where supported.

## 12.2 Hermes profile families

```text
profile.hermes.context_scout
profile.hermes.research
profile.hermes.knowledge_curator
profile.hermes.skill_distiller
profile.hermes.operator
profile.hermes.experience_scout
profile.hermes.failure_memory
profile.hermes.routing_insight
profile.hermes.continuity_scout
profile.hermes.provenance_scout
```

## 12.3 Execution Experience Memory

Persist authoritative raw WorkerRun/verification telemetry in DDE. Feed derived, provenance-linked experience records to Hermes for semantic retrieval.

`ExperienceRecord` includes task signature, exact WorkerConfiguration, verified outcome, rework, failure signatures, tokens/cost/latency and verification refs.

## 12.4 ExperienceScout

Before route selection retrieve semantically similar verified work and return:

- successful configurations;
- failed configurations;
- first-pass success;
- average rework/cost/latency;
- recurring failures;
- escalation patterns;
- evidence count/freshness/confidence.

## 12.5 FailureMemory

Track repeated failure signatures and proven recoveries without treating unverified anecdotes as routing truth.

## 12.6 RoutingInsightGenerator

May emit `RoutingInsightCandidate`, never mutate routing policy.

Promotion:

```text
candidate
→ offline replay
→ holdout
→ shadow
→ canary
→ policy promotion
```

## 12.7 ContinuityScout

On resume identify relevant accepted decisions, unresolved findings, preserved verification, previous route failures and exact next work.

## 12.8 ProvenanceScout

Resolve questions through durable IDs:

```text
requirement
→ task
→ worker run
→ ChangePacket
→ verification
→ commit/artifact
```

## 12.9 Design/playbook intelligence

Hermes may correlate successful design/workflow runs and propose reusable playbook candidates. It never promotes them.

## 12.10 Acceptance

A real Hermes task must:

- retrieve evidence;
- distinguish authoritative vs advisory sources;
- produce a provenance-linked context/experience report;
- be consumed by planning/routing without hidden mutation;
- propose an insight that remains non-authoritative until evaluation.

---

# 13. DDE-076 — Persistent Fleet Registry + Provider Capacity

**Priority:** P0/P1

## 13.1 Persistent authorities

Implement/converge:

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

Router, Worker Manager, Studio and health projections consume the same persistent authority.

## 13.2 WorkerConfiguration identity

Certification binds:

```text
model + version
provider
harness + version
profile
skills/tools manifest
context strategy
environment image
policy hashes
```

Changed identity becomes stale until re-certified according to risk.

## 13.3 Multi-role certification

A configuration may be orchestration-, implementation-, review- and/or security-capable. Role occupancy remains dynamic.

## 13.4 Provider capacity states

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

Store reset source/confidence, probe cost, concurrency, failures, latency and current cost metadata.

## 13.5 Probe economics

Prefer reliable passive reset signal, then cheap probe, then expensive probe only when justified.

## 13.6 Acceptance

Restart Core and prove:

- Router/Worker Manager/UI agree on fleet state;
- exact installed capabilities survive/reconstruct;
- stale version is not treated as certified;
- provider reset metadata drives repromotion eligibility;
- model can change role without changing identity records.

---

# 14. DDE-077 — Task Execution Strategy + Change/Workspace Ownership

**Priority:** P1

## 14.1 TaskExecutionDescriptor

Implement structured classification from task/requirements/project metadata. A model may propose missing values but cannot silently invent risk.

## 14.2 ExecutionStrategyEngine

Legal strategies include direct, plan/implement/review, investigate, specialist fan-out, parallel candidates, red-team, visual iteration and migration-with-rollback proof.

Strategy selection precedes worker/harness selection.

## 14.3 WorkspaceLease + WriteOwnershipGraph

One editing session → one authorized worktree. Check file/symbol/shared-contract overlap before parallel work.

## 14.4 ChangePacket

Every mutable packet binds task/run/workspace, declared read/write scopes, base tree, touched paths, diff, staged paths, evidence and state.

## 14.5 RejectionDisposition

Rejected work is quarantined/reverted/isolated and verified absent from the accepted baseline.

## 14.6 StagingManifest / CommitManifest

Controlled commits prove:

```text
declared write scope
≈ actual changed paths
≈ staged paths
≈ commit scope
```

Unexpected staged path → `BLOCK`.

`git add -A` requires explicit bulk-maintenance packet/override.

## 14.7 Safe parallelism

Bound by dependency, write ownership, provider capacity, verification capacity, integration capacity and Attention Budget.

## 14.8 Acceptance

Critical case:

```text
Packet A changes files
→ Packet A rejected/dispositioned
→ Packet B valid work
→ Packet B stages/commits
→ ZERO Packet A mutations in commit
```

Also test concurrent packets touching same path, generated-contract contention and staged scope mismatch.

---

# 15. DDE-078 — Real Usage, Cost, Quota, Context & Occupancy Telemetry

**Priority:** P0/P1

## 15.1 Genuine usage

Every live adapter forwards genuine provider usage where available. Unknown remains unknown.

## 15.2 Normalized usage

Record:

```yaml
input_tokens:
output_tokens:
cache_read_tokens:
cache_write_tokens:
reasoning_tokens:
tool_calls:
duration_ms:
provider_cost:
effective_cost:
model:
model_version:
provider:
harness:
harness_version:
worker_profile:
```

## 15.3 Operational telemetry additions

Record:

```text
orchestrator desired model
orchestrator configured/requested model
serving-model evidence/confidence
orchestrator-control level
strategic occupancy state where attested
configured→serving mismatch/unknown duration
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

## 15.4 KPIs

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

## 15.5 Acceptance

Force quota pressure/fallback and prove:

- ordinary work reroutes;
- strategic capacity is conserved;
- desired/configured/serving facts remain separately observable;
- OCL-1 reset/config changes do not become fake live-occupancy events;
- premium-model creep becomes visible;
- context checkpoint metrics emit;
- design/provider costs are attributable to mission/task/artifact.

---

# 16. DDE-079 — Empirical Routing + Route Critic

**Priority:** P1

## 16.1 Feature vector

Join:

- TaskExecutionDescriptor;
- strategy;
- requested capabilities;
- desired strategic model;
- configured/requested strategic model;
- serving-model evidence and confidence;
- orchestrator-control level;
- attested strategic occupant where available;
- exact candidate WorkerConfiguration;
- context pressure;
- quota/reset distance;
- provider health;
- probe cost;
- historical task similarity;
- verified success;
- first-pass success;
- rework;
- human intervention;
- previous cheaper-worker failure;
- premium escalation reason.

## 16.2 Prediction targets

```text
verified_success
effective_cost
latency
rework
human_intervention
operational_risk
```

## 16.3 RouteDecision

Populate predicted success/cost/latency/confidence and preserve candidate evidence.

## 16.4 Static-prior decay

Bootstrap affinities lose weight as sufficient version-aware verified evidence accumulates.

## 16.5 Escalation policies

Learn sequences—not only winners—such as cheap-first then premium on a specific failure signature.

## 16.6 Controlled exploration

Low-risk shadow/canary only; high-risk new configurations require stricter certification.

## 16.7 Route Critic

Invoke strategic reasoning only for ambiguity/ties/high risk/prior failures. It does not override hard gates.

## 16.8 Acceptance

Holdout/replay demonstrates no safety regression and improved verified-outcome utility over deterministic baseline. New policy promotes only via shadow/canary and supports rollback.

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

Generate bounded provenance-carrying packages using the smallest sufficient source set.

## 17.4 ContextBudget integration

Estimate and reserve safe context before high-risk work. Trigger checkpoint/continuation when thresholds are crossed.

## 17.5 ContinuationPackage

Persist exact accepted decisions, branch/head, working state, active ChangePacket, completed steps, unresolved findings, next exact action, required evidence and forbidden rework.

## 17.6 EvidenceValidityGraph

Build dependency links between verification evidence and the invariants/components it proves.

## 17.7 RegressionInvalidationGraph + DeltaAuditPlan

A change computes:

```text
evidence preserved
evidence invalidated
checks required
work that must not be repeated
```

## 17.8 Acceptance

- deliberately false capability claim fails truth-check;
- unrelated implementation change retains prior evidence;
- changed invariant invalidates only dependent evidence;
- resumed session receives a bounded ContinuationPackage rather than full chat/repo dump.

---

# 18. DDE-081 — Mission Workspace + Execution Graph + Node Inspector

**Priority:** P1

Build on the Studio V2 shell and real event/fleet data.

## 18.1 Project/Mission Workspace

Show projects, missions, requirement coverage, desired/configured/serving strategic-model state and attested occupant where available, active tasks, live workers, design sessions, blockers, quality, evidence, provider degradation and attention.

## 18.2 Real Execution Graph

Project the actual runtime—not an idealized diagram.

Nodes/edges show:

- dependencies/parallelism;
- retries/fallbacks;
- role transitions;
- worker/design sessions;
- human gates;
- verification;
- integration.

## 18.3 Node Inspector

Inspect:

- normalized inputs/context manifest;
- route candidates/decision;
- exact worker/model/harness/config;
- tools/capabilities;
- ChangePacket/workspace;
- artifacts/diffs;
- usage/cost;
- failures;
- verification/evidence.

No hidden chain-of-thought persistence.

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

Every action preserves lineage and policy.

## 18.5 Run Comparison

Compare candidate runs by verified result, patch/artifacts, cost, latency, rework, human intervention and failure signatures.

## 18.6 Route explainability

`Why this route?` is derived from hard gates/scores/experience/capacity, not fabricated prose.

## 18.7 Attention Center

Classify `IMMEDIATE`, `REVIEW_QUEUE`, `DAILY_SUMMARY`, `INFORMATIONAL`.

## 18.8 Acceptance

An operator can manage a mission, inspect an exact node, understand a fallback, compare runs and invoke a legal replay/reroute without opening raw agent terminals or a second state store.

---

# 19. DDE-082 — Design Intelligence + Design Gateway + Playbooks/Workflow Composer

**Priority:** P1/P2

DDE-069 establishes the usable live-design foundation. DDE-082 completes the design intelligence and generalizes successful workflows.

## 19.1 DesignExplorationCompiler

Separate creative exploration from conformance implementation. May propose tokens/type/layout/component/motion grammar but cannot directly commit authority.

## 19.2 DesignCandidate competition

Generate genuinely distinct candidate directions through certified design configurations, potentially including Claude Design and other future providers.

## 19.3 ProductDesignAuthority

Human promotion creates a DDE-owned immutable authority version and machine-readable implementation constraints.

## 19.4 Full DesignGateway hardening

Complete:

- provider health/fallback;
- session continuity;
- design-system synchronization;
- egress ledger;
- candidate branching;
- immutable design/code promotion;
- provider-neutral adapter certification;
- cost controls.

## 19.5 Design Skill Registry

Version/certify external design skill inputs and DDE-native specialists. Skills advise; ProductDesignAuthority and policy govern.

## 19.6 Workflow Registry / Playbooks

Convert verified recurring execution/design patterns into versioned workflow candidates.

Definitions express capabilities/constraints, not unnecessary model pins.

Promotion:

```text
candidate
→ replay/holdout
→ shadow
→ canary
→ promoted
```

Hermes may discover candidates, not promote them.

## 19.7 Visual Workflow Composer

Build a visual authoring surface that compiles into DDE's validated workflow definition.

Must block:

- illegal edges;
- deletion of mandatory gates without policy;
- unsatisfied capabilities;
- Project Truth mutation through arbitrary agent/memory nodes;
- provider-specific semantics leaking into the core workflow contract.

## 19.8 Opal adoption boundary

Do not make Opal a runtime dependency. Adopt only high-value UX/inspectability patterns natively.

## 19.9 Acceptance

- 3+ truly distinct design directions can be produced when policy requests them;
- selected design becomes immutable DDE authority;
- design/live-code loop verifies;
- a successful workflow can become a candidate and pass promotion gates;
- composer-produced workflow executes through the same runtime/events as non-visual workflows;
- no duplicate orchestration truth exists.

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

- wrong root;
- unrelated-project bootstrap attempt;
- approved parent/root;
- conflicting foreign config;
- broken config link;
- partial/duplicate bootstrap.

## 20.3 Orchestration/model-control chaos

- OCL-1 `CONFIGURED=fable` while serving identity remains unknown;
- startup/status output refuses to convert configured preference into `FABLE_ACTIVE`;
- Fable exhaustion configures Opus for the next/new session without claiming a live parent switch;
- Fable timed recovery configures Fable-preferred without claiming current serving identity;
- bounded explicitly Fable subagent execution is recorded separately from parent orchestration;
- serving-model mismatch/unknown state;
- OCL-3 Opus temporary attested occupancy;
- OCL-3 Fable attested restoration;
- Opus return to ordinary pool after attested restoration;
- no premium creep;
- Core restart during fallback/requested-unattested state.

## 20.4 Runtime-capability chaos

- expected hook absent;
- installed version changes hook set;
- documented capability unavailable in installed build.

## 20.5 Context chaos

- context exhaustion before high-risk task;
- checkpoint;
- fresh-session continuation with correct lineage.

## 20.6 Change governance chaos

- rejected packet leaves mutations;
- later broad staging tries to sweep them;
- contamination blocked;
- concurrent packets conflict;
- staged scope differs from declared scope.

## 20.7 Evidence chaos

- unrelated change preserves evidence;
- changed invariant selectively invalidates evidence;
- stale verification cannot be presented as current.

## 20.8 Design chaos

- design provider unavailable;
- stale design-system sync;
- Try-Live build failure;
- direct inspector edit then provider refinement;
- artboard incorrectly attempts LIVE state;
- promoted design/code pair diverges before verify.

## 20.9 Executable-update certification

New Hermes/Claude/Codex/DeepSeek/MCP/skill/plugin candidate:

```text
detect
→ quarantine
→ certify
→ canary
→ promote or reject
→ rollback on regression
```

Active stable version stays untouched until promotion.

## 20.10 Release proof

Release candidate requires:

- full test/contract/migration suite;
- golden missions;
- recovery/chaos results;
- no critical truth drift;
- capability realization report;
- provider/worker certification snapshot;
- cost/quota report;
- security/egress checks;
- visual/operator verification;
- update rollback proof.

---

# 21. Cross-mission infrastructure changes

## 21.1 Gateway reads

Add missing list/read projections as needed.

Do not invent client data.

Preferred endpoints/projections:

```text
projects
missions
tasks
worker-sessions
worker-runs
events/timeline
approvals
verification-results
evidence
design-candidates
fleet
```

Pagination and tenant/project scoping are mandatory.

## 21.2 Event transport

Close EDR-0027 with WebSocket/SSE or equivalent sequence-preserving push.

Requirements:

- resume token/sequence;
- gap detection;
- replay;
- reconnect;
- multi-client consistency.

Studio V2 should consume event push rather than polling/by-id alone.

---

## 21.3 New cross-cutting contract families

Plan schema-first changes for:

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

Extend existing accepted objects rather than duplicate them.

## 21.4 Managed update infrastructure

Introduce `ToolUpdateManager` before release certification. Risk-class updates and keep the active certified version stable until candidate promotion.


---

# 22. Frontend Studio implementation details

## 22.1 Migration strategy

Do not remove DDE-067 webviews in one change.

Phases:

```text
A. Build ui-v2 app shell behind feature flag.
B. Mount one read-only surface.
C. Validate VS Code + Electron host bridge.
D. Migrate Frontend Studio Build.
E. Migrate Verify.
F. Migrate Mission Workspace.
G. Retire equivalent legacy renderer after parity.
```

At every phase:

- old path stays functional until replacement is verified;
- no duplicate writes;
- one Gateway command path.

## 22.2 URL/view state

Use serializable navigation state such as:

```text
/project/:projectId/mission/:missionId/studio/build?screen=checkout-empty&bp=compact
```

It need not be browser-history public routing, but should be representable for deep links and restoration.

## 22.3 Resizable panes

Persist pane sizes only locally.

Do not store UI layout in Project Truth unless user explicitly saves a workspace preference.

## 22.4 Tables

Use real tables for:

- missions;
- tasks;
- fleet;
- approvals;
- evidence.

Avoid cards for tabular engineering information.

## 22.5 Status language

Prefer concise manufacturing vocabulary:

```text
Planned
Ready
Running
Waiting
Blocked
Verifying
Passed
Failed
Needs decision
```

Avoid decorative badge overload.

## 22.6 Empty states

Empty states:

- state the fact;
- identify next meaningful action when one exists;
- do not show fake examples;
- do not write long instructional essays.

## 22.7 Loading

Use skeletons only when a real read is in flight and expected layout is known.

Use progress indicators for long-running commands.

Never imply percentage completion without real data.

## 22.8 Error states

Errors must:

- name what failed;
- show typed reason;
- offer legal next action;
- preserve diagnostic details behind disclosure.

Example:

```text
Canvas update blocked
The selected token is not allowed by DesignAuthority v4.
Choose an approved spacing token or open the design proposal.
[Open inspector] [View policy]
```

---

## 22.9 Design/live-code implementation detail

The live canvas is a ProductEnvironment/PreviewRuntime output. The provider artboard is a separate preview channel.

Support optional split view:

```text
[ DESIGN ARTBOARD ] | [ REAL LIVE CANDIDATE ]
```

with visual-difference overlay.

Stable `data-dde-el` or equivalent anchors drive selection-to-DesignEditContext mapping.

## 22.10 Design Dock / candidate UX

Do not dump provider chat. Surface intent, lineage, version, constraints, status and actions.

## 22.11 Execution Graph UX

Graph nodes must link back to durable event/task/session/evidence identifiers. A node without a runtime source is not displayed as executed.


---

# 23. Frontend Studio design quality benchmark

The tool should feel in the quality class of contemporary professional developer/design tools without copying them.

Borrow principles:

### Figma-class

- spatial workbench;
- persistent canvas;
- contextual inspector;
- layers;
- command search.

### Linear-class

- compact hierarchy;
- strong keyboard workflow;
- restrained chrome;
- precise status.

### VS Code-class

- workspace density;
- split panes;
- command palette;
- inspectable developer state.

### Raycast-class

- speed;
- keyboard-first actions;
- clear search.

Do not copy:

- brand palette;
- exact layout;
- iconography;
- proprietary component designs.

DDE's own visual identity is Precision Manufacturing Workbench.

---

# 24. AI design workflow integration

## 24.1 Stable architecture boundary

Use `DesignGateway` + provider adapters. Do not hard-code DDE state to `/design` syntax or native provider canvas embedding.

## 24.2 Material-change classifier

Only material UI work triggers mandatory design. Small deterministic changes bypass by explicit auditable policy.

## 24.3 Candidate-count policy

Candidate count is risk/design-impact/cost aware. Do not generate multiple expensive alternatives for trivial changes.

## 24.4 Live refinement

Supported loop:

```text
real live candidate
→ selected semantic context
→ provider refinement
→ design candidate
→ Try live
→ real live candidate
```

## 24.5 Promotion boundary

Exploratory candidates remain isolated. Promotion freezes exact design and code identities. Merge eligibility begins only after normal verification.

## 24.6 Provider degradation

Mandatory design unavailable → waiting/degraded state or approved alternate provider. Never silent design bypass.

## 24.7 Opal-derived UX

Implement natively:

- workflow visual clarity;
- real execution graph;
- node inspector/debugging;
- replay/reroute/fork/compare;
- workflow/playbook library;
- policy-compiled visual composer.

Do not integrate Opal as core runtime.

---

# 25. Testing strategy

## 25.1 Per-mission layers

Every mission should have:

```text
unit
contract
integration
recovery
security where relevant
visual where relevant
chapter-gate
```

## 25.2 Real-call requirement

At least one acceptance test must traverse the actual production mutation/reader path for every claimed new capability.

Mock-only success is not sufficient.

## 25.3 Studio tests

For UI V2:

- component unit;
- bridge contract;
- accessibility;
- keyboard;
- visual;
- integration with fake Gateway;
- integration with real Gateway fixture;
- Electron smoke;
- VS Code webview smoke.

## 25.4 State-machine and failure-contract tests

For every durable lifecycle or external-effect boundary introduced by a mission:

- enumerate legal transitions and reject illegal transitions;
- exercise cancel/timeout/retry classes;
- exercise ambiguous external-effect reconciliation where applicable;
- prove idempotent replay;
- prove crash/checkpoint/recovery behavior;
- assert durable event/projection correctness;
- expose typed degraded/blocking state to operators.

---

## 25.5 Operational-hardening tests

Add contract/invariant cases for:

- wrong root / config contamination;
- role occupancy fallback/restoration;
- worker-pool exclusion/re-entry;
- context threshold/continuation;
- ChangePacket rejection disposition;
- staged scope mismatch;
- evidence selective invalidation;
- tool-update quarantine/canary/rollback.

## 25.6 Design integration tests

Add:

- DesignGateway classification;
- ClaudeDesignAdapter normalization;
- egress allowlist/redaction;
- stale design-system hash;
- candidate lineage;
- Try-Live isolation;
- semantic DESIGN/LIVE/VERIFIED states;
- promote immutability;
- PreviewRuntimeAdapter behavior;
- live-state-to-provider refinement;
- provider outage fail-closed.

## 25.7 Execution graph/workflow tests

Prove:

- graph is runtime-derived;
- retries/fallbacks/human gates appear correctly;
- node inspector lineage;
- exact replay/reroute/fork lineage;
- workflow compiler blocks illegal edges and missing mandatory gates;
- visual workflow executes through the same engine as API-authored workflow.


---

# 26. CI additions

Target jobs:

```text
truth-check
fleet-contract
agent-protocol-contract
studio-unit
studio-accessibility
studio-visual
product-visual
golden-missions
routing-replay
```

Do not make every expensive model test run on every PR.

Use:

- deterministic PR gates;
- scheduled live-provider certification;
- release-gate live-provider tests.

---

Additional CI gates should include:

```text
bootstrap-contract-check
staging-scope-contract-check
evidence-validity-check
workflow-compiler-contract-check
design-contract-check
tool-update-certification-tests
```

Do not make CI depend on live premium providers unless an explicit integration test environment is configured; provider-facing tests require deterministic fixtures/mocks plus separately scheduled certified live probes.


---

# 27. Cost governance

Use expensive reasoning only where useful.

Initial cost/routing posture is capability- and evidence-based, never a static model-role map:

### Strategic orchestration

- Fable is the preferred strategic model when installed, certified, policy-eligible and available;
- a config-only runtime may request/configure Fable without proving Fable is serving; only attested runtimes may claim live strategic occupancy;
- a certified fallback such as Opus may be configured/requested for a future/new session at OCL-1 or temporarily occupy an attested strategic lease at OCL-3 when policy selects it;
- an attested strategic occupant is not thereby the default executor for ordinary work.

### Ordinary implementation/reasoning workers

- Opus, Sonnet, Haiku, Codex, DeepSeek, local models and future certified workers remain candidates according to installed capabilities, task fit, verified historical performance, provider capacity, cost and policy;
- no model is permanently designated “the coding model”, “the reasoning model” or “the cheap model”.

### Design providers

- Claude `/design` is the first high-value specialist behind `DesignGateway`; provider choice remains replaceable and policy-governed.

### Hermes

- context, research, continuity and experience intelligence; never routing/truth authority.

### Deterministic tools

- mechanical transforms, validation, verification and policy enforcement wherever model reasoning is unnecessary.

These are routing priors and architectural constraints, not fixed worker assignments. Empirical routing must be free to outperform the priors while remaining inside hard capability/security/egress/policy gates.

---

Track separately:

- strategic-orchestrator spend;
- ordinary premium-worker spend;
- verification/reviewer spend;
- design-provider spend;
- provider probe spend;
- failed/rework spend.

A routing or workflow change is not cheaper if it raises rework, human intervention or failure rate enough to increase cost per verified success.


---

# 28. Definition of success

Rev 3 is successful when DDE can repeatedly manufacture software through the consolidated control plane and prove what happened.

Required outcomes:

- project/bootstrap identity cannot silently cross-contaminate repositories;
- DDE never confuses desired/configured model intent with serving-model fact;
- config-only orchestrator failover/restoration is labelled as next/new-session intent, while attested runtimes expose real occupancy;
- strategic role occupancy, where attested, fails over/restores without premium-model creep;
- worker configurations are selected from certified real capabilities;
- Hermes improves context/experience discovery without becoming authority;
- context exhaustion produces safe continuation;
- rejected work cannot contaminate later commits;
- evidence is selectively reused/invalidated;
- provider quota/cost/health drive real routing;
- DDE-068 visual verification is real production evidence;
- Frontend Studio can move from design artifact to isolated real LIVE candidate and back;
- only promoted design/code pairs become merge-eligible;
- execution graph and node inspector show actual runtime truth;
- replay/reroute/fork preserve lineage;
- reusable playbooks promote only through evidence;
- Workflow Composer compiles into the same governed engine;
- managed executable updates can be certified/canaried/rolled back;
- operator UI is professional and honest;
- capability-realization report has no high-severity overclaims;
- golden/chaos missions pass;
- cost per verified success and human intervention are measurable.

---

# 29. Non-negotiable anti-drift rules

1. Project Truth/accepted EDRs outrank this plan.
2. Blueprint Rev 3 defines architecture; this plan cannot silently change it.
3. Do not create a second Rev 3 blueprint/plan hierarchy under another folder.
4. Do not reintroduce static model-role architecture.
5. Do not represent `CONFIGURED=fable` or reset eligibility as evidence that Fable is serving the running parent session.
6. Do not interpret Fable recovery as “Fable orchestrates, Opus becomes default premium worker”.
7. Do not let Hermes memory self-promote routing policy.
8. Do not start high-risk work in an unsafe context state.
9. Do not leave rejected mutations anonymous in a shared tree.
10. Do not use broad staging in controlled work without explicit packet authorization.
11. Do not blanket re-audit evidence unaffected by a change.
12. Do not label provider artboards LIVE.
13. Do not let design provider output mutate accepted code without Try-Live/promotion governance.
14. Do not build a decorative execution graph or parallel workflow runtime.
15. Do not pin workflow playbooks to models unless a capability requirement genuinely demands it.
16. Do not silently auto-update executable workers/tools/plugins.
17. Do not call a capability complete until production call sites and evidence meet the closure matrix.

---

# 30. Consolidation source evidence

This plan is grounded in:

- current `Vanguduza/dde` Rev 3 truth/bootstrap repository state;
- original DDE Blueprint Rev 3.0;
- original DDE Rev 3 Development & Realisation Plan;
- Rev 3 quantum audit and design-intelligence audit;
- Rev 3.1 Operational Hardening / Adaptive Routing amendment;
- Claude `/design` + high-value Opal integration addendum;
- live Dial Main orchestrator-control finding: subagent routing was enforceable, parent-session model occupancy was not; current repo-level Claude Code configuration proves requested/configured next-session state, not serving-model identity;
- existing DDE-065/066/067 implementation evidence and chapter-gate sequence.

The standalone amendment/addendum documents remain historical evidence after adoption. Their forward requirements are mapped into the relevant gates/missions above.

---

# 31. Immediate next action

After this consolidated source-of-truth update is merged:

> **Execute REV-3A Operational Safety Gate before DDE-068.**

Start with **REV-3A.1 ProjectIdentity / bootstrap preflight**, because wrong-root/config contamination can invalidate every subsequent agent/workflow decision.

Then close in order:

```text
REV-3A.1 identity/bootstrap
→ REV-3A.2 orchestrator model-state / attestation safety
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
| Orchestrator model state / serving attestation / strategic role occupancy | REV-3A.2 | DDE-071 / DDE-073 |
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
| Design intelligence/playbooks/composer | live loop seed DDE-069 | DDE-082 |
| Managed executable updates | policy foundation earlier | DDE-083 release proof |

---

# Appendix B — Per-mission chapter-gate checklist

Every numbered mission and REV-3A slice closes only when the gate records:

- authoritative blueprint clauses;
- accepted EDRs;
- changed schemas/contracts;
- production writers/readers;
- Gateway/API/UI paths;
- actual state transitions;
- failure/cancel/retry/recovery semantics;
- capabilities/credentials/egress;
- migration and evidence-inheritance effects;
- tests and real evidence;
- observed capability-realization state;
- residuals/deferred items;
- exact next dependency.

Allowed result:

```text
PASS
PASS-WITH-EDR
FAIL
```

A green test suite alone is never a mission PASS.

# Appendix C — Normative per-mission implementation-resolution pack

This appendix is **mandatory for REV-3A and every numbered mission**. It is not additional documentation ceremony; it is the minimum implementation-resolution record required to prove that a capability moved beyond planning.

For each mission/slice, create one chapter-gate implementation pack containing the following sections. Existing repository evidence may be referenced instead of duplicated.

## C.1 Authority and traceability

Record:

```text
Blueprint clauses
Accepted EDRs
RequirementAtom IDs
Capability IDs
AcceptanceCriterion IDs
Inherited evidence
Invalidated evidence
Residual/deferred requirements
```

No mission may invent a capability without an authority reference. No requirement touched by the mission may be left without an owner or explicit disposition.

## C.2 Contract delta

List every added/changed/retired:

```text
CommandContract
QueryContract
ApiContract
EventContract
DataContract
StateMachine
FailureContract
SecurityControl
ObservabilityContract
ServiceBudget
SurfaceContract
MigrationContract
```

For each, identify schema version and compatibility impact.

## C.3 Production wiring

For every capability changed, identify:

- owner service/module;
- production writer(s);
- production reader(s);
- Gateway/API/MCP/UI call sites;
- adapter bindings;
- registry/DI binding;
- event producers/consumers;
- non-test execution proof.

A fixture, mocked service or test helper alone is not production wiring.

## C.4 State/failure implementation

Record:

- legal state transitions;
- guard conditions;
- transition authority;
- cancellation;
- timeout;
- retry classification;
- ambiguous-effect reconciliation;
- degraded mode;
- operator-visible failure state.

## C.5 Security implementation

Record:

- principals/capabilities;
- credential/secret path;
- filesystem/write scope;
- network/egress scope;
- sensitivity classification;
- prompt/retrieval trust boundary where AI is involved;
- supply-chain impact;
- security/adversarial tests.

## C.6 Observability and economics

Record:

- emitted events;
- logs/traces/correlation IDs;
- metrics;
- provider usage/token/cost fields;
- queue/backlog visibility;
- provisional service budget;
- measured values;
- alert/Attention Center semantics.

## C.7 Product/operator surfaces

Record every affected:

```text
VS Code / DDE Code
Electron/Desktop
Frontend Studio
CLI
MCP
API
Web/Mobile if supported
```

For each capability assign parity class: `REQUIRED_ALL`, `REQUIRED_OPERATOR`, `REQUIRED_AUTOMATION`, `HOST_SPECIFIC`, `READ_ONLY_PARITY` or `NOT_APPLICABLE`.

## C.8 Migration/rollout/recovery

Record:

- schema/data migration;
- config migration;
- evidence-validity effect;
- feature flag/policy rollout if used;
- rollback/restore strategy;
- compatibility window;
- update to deployment manifest.

## C.9 Verification and certification

Map each acceptance criterion to one or more verification scenarios and evidence refs. At closure, produce/update `CapabilityCertification` records or explicitly leave the capability below `VERIFIED`.

---

# Appendix D — Program-wide traceability workstream

Traceability is implemented incrementally, not postponed until DDE-083.

## D.1 Target projections

By Rev 3 release candidate, DDE must generate/read projections equivalent to:

```text
Requirement → Capability
Capability → Contracts
Capability → Owner/Call Sites
Capability → State/Failure/Security
Capability → Surfaces
Capability → Verification/Evidence
Capability → Certification
Evidence → Dependency/Validity
Code/API/Event/Surface → owning Capability/Requirement
```

Suggested generated artifacts may live under a clearly generated/subordinate location such as `docs/generated/**` or a Core projection endpoint. They do **not** become third canonical human architecture documents.

## D.2 Traceability implementation order

| Gate/mission | Traceability responsibility |
|---|---|
| REV-3A | stable project/session/change/evidence IDs and correlation discipline |
| DDE-068 | acceptance criterion → visual VerificationRun/Evidence lineage |
| DDE-069 | surface action → command → design/live/verification lineage |
| DDE-070 | session/harness/capability contract → production WorkerSession lineage |
| DDE-071 | desired/configured/serving model evidence + role lease/plan proposal → route/task lineage |
| DDE-072–075 | worker/provider adapter → WorkerRun/usage/outcome lineage |
| DDE-076 | certified installation/profile/capacity → route eligibility lineage |
| DDE-077 | task → ChangePacket → declared write set → commit lineage |
| DDE-078 | run → usage/cost/quota/context/occupancy telemetry lineage |
| DDE-079 | ExperienceRecord → route prediction/decision → verified outcome lineage |
| DDE-080 | Requirement/Truth/Context/EvidenceValidity graph compilation |
| DDE-081 | operator graph/node inspector exposes the real lineage |
| DDE-082 | design/workflow/playbook → real governed execution lineage |
| DDE-083 | orphan scan, certification ledger and release traceability closure |

## D.3 Orphan gates

CI/release checks shall eventually fail on release-critical:

- accepted requirement with no capability/disposition;
- capability with no owner;
- mutating surface with no command contract;
- command with no production handler;
- event with no schema/owner;
- authoritative data with no owner/migration rule;
- `VERIFIED` capability with no current certification;
- certification whose evidence is invalid;
- UI state claiming a realization level higher than Core projection.

---

# Appendix E — Mission hardening responsibility matrix

The existing mission numbering and order remain locked. This matrix prevents cross-cutting Dial requirements from falling between missions.

| Mission | Primary hardening responsibilities added by Rev 3.3 |
|---|---|
| REV-3A | project identity, bootstrap state machine, orchestrator desired/configured/serving honesty shim, correlation IDs, context safety, ChangePacket lifecycle, staging isolation, evidence-validity seed, security of root/write scope |
| DDE-068 | verification state machine, verifier failure semantics, visual evidence lineage, ProductEnvironment observability, deterministic/independent evidence policy |
| DDE-069 | host-bridge command/query contracts, surface parity foundation, DesignCandidate state machine, truthful DESIGN/LIVE/VERIFIED semantics, preview error/latency telemetry |
| DDE-070 | WorkerSession state machine, bootstrap enforcement, harness version/capability contract, cancellation/checkpoint/recovery, session service budgets |
| DDE-071 | OrchestratorModelState/ModelServingEvidence, OCL-0…3 semantics, StrategicOrchestratorLease state machine, truthful failover/repromotion, planning command contracts, strategic cost/latency/availability telemetry |
| DDE-072 | Codex adapter security/capabilities, real-call usage/failure normalization, side-effect boundaries, certification |
| DDE-073 | Claude adapter/runtime and model-control capability discovery, serving-model attestation support, tool/skill capability manifests, prompt/egress boundary, resumability |
| DDE-074 | DeepSeek adapter equivalent production/security/usage/failure closure |
| DDE-075 | Hermes memory provenance, derived-vs-authoritative data ownership, retrieval trust labels, ExperienceRecord/Context query contracts |
| DDE-076 | persistent fleet data ownership, installation/profile certification lifecycle, provider capacity provenance/freshness, update/version binding |
| DDE-077 | TaskExecutionDescriptor ownership, ChangePacket full lifecycle, write ownership graph, commit manifest, merge/conflict/rejection recovery |
| DDE-078 | canonical telemetry contracts, service budgets, provider quota/reset facts, context/occupancy metrics, cost reconciliation |
| DDE-079 | routing feature schema, confidence/calibration, holdout/shadow/canary policy promotion, learning safety, route explainability |
| DDE-080 | traceability compiler, context compiler, EvidenceValidityGraph, RegressionInvalidationGraph, DeltaAuditPlan, orphan/drift checks |
| DDE-081 | runtime execution graph projection, node inspector commands, replay/reroute/fork lineage, Attention Center and backlog/degraded state |
| DDE-082 | ProductDesignAuthority, DesignGateway hardening, playbook/workflow contracts, Workflow Composer compiler safety, design/workflow certification |
| DDE-083 | threat closure, migration/restore rehearsal, tool-update certification, load/capacity envelope, chaos matrix, cross-platform parity closure, release certification |

No mission may defer its primary row wholesale to DDE-083. DDE-083 integrates and proves; it does not become a dumping ground for missing production wiring.

---

# Appendix F — Command/query/API/event/data implementation plan

## F.1 Shared contract infrastructure

Where not already present, extend the current contract approach rather than create a parallel framework. Required shared capabilities:

- command envelope with idempotency/correlation/expected revision;
- query envelope/projection version/freshness;
- normalized API error contract;
- durable event envelope with schema version/correlation/causation;
- event idempotency/replay utilities;
- explicit `DataOwnership` metadata/projection;
- schema compatibility tests;
- generated client/types where useful.

## F.2 Command ownership map

At minimum the following mutation families must resolve to one Core owner by the owning mission:

```text
bootstrap/session lifecycle
mission/plan/task lifecycle
strategic lease acquisition/release/repromotion
route decision/policy activation
worker session/run/cancel/checkpoint/resume
workspace/change packet/rejection/staging/commit
provider installation/certification/update
context/continuation creation
verification request/verdict/certification
DesignGateway request/try-live/promote
workflow validate/run/pause/resume/reroute/fork
release certification/promotion
```

## F.3 Query/projection map

Primary projections include:

```text
Project/Mission Workspace
Task/Attempt/Run detail
Fleet/Capability/Provider Capacity
Usage/Cost/Quota/Context
ChangePacket/Write Ownership
Verification/Evidence/Validity
Design Session/Candidates/Live Candidate
Execution Graph/Node Inspector
Workflow/Playbook registry
Capability Realization/Traceability
Release Readiness/Certification
```

## F.4 Event implementation rules

- transactional owner changes publish through the existing sanctioned event/outbox mechanism;
- consumers are idempotent;
- projection lag is measured;
- replay-safe events are distinguished from side-effect commands;
- event schema drift is CI-tested;
- provider-native streaming/tool events are normalized before persistence/projection.

## F.5 Data-migration discipline

Every mission changing persistent contracts supplies:

```text
migration preflight
forward migration
compatibility/backfill
postflight invariant check
rollback/restore path
EvidenceValidityGraph impact
```

---

# Appendix G — State, failure and recovery implementation plan

The Blueprint state machines are normative target semantics. Missions may extend states only through accepted architecture/EDR change; they may not simplify away safety states for convenience.

## G.1 Minimum state-machine test pattern

For each aggregate:

1. table/property test of all legal transitions;
2. rejection test for illegal transitions;
3. authorization/guard test;
4. idempotent replay test where applicable;
5. timeout/cancellation test;
6. crash/recovery or continuation test;
7. event emission/version test;
8. projection correctness test.

## G.2 Failure-contract test pattern

For each external/provider/side-effect boundary:

```text
success
retryable failure
non-retryable failure
timeout before request
timeout after possible effect
quota/capability denial
cancellation
malformed response
stale/duplicate response
provider/harness crash
```

Where an external effect may have occurred, include reconciliation before retry.

## G.3 Required chaos mapping

DDE-083 must execute the Blueprint failure/eventuality matrix against the integrated release candidate, but the individual failure paths must already be implemented and tested by their owning missions.

---

# Appendix H — Security implementation and threat-closure plan

## H.1 Threat model deliverable

Each mission affecting a trust boundary updates a compact threat record using at least:

```text
asset
principal
entry point
trust boundary
abuse/failure scenario
preventive control
detective control
recovery
verification evidence
residual risk
```

## H.2 Mandatory adversarial scenarios

By DDE-083 the release candidate must prove resistance to:

- wrong-repository config inheritance;
- path traversal/symlink escape from declared workspace;
- broad staging/foreign mutation contamination;
- provider prompt attempting to grant itself tools/capabilities;
- retrieved document/web content attempting authority override;
- secret appearing in prompt/log/evidence capture;
- network egress outside allowlist;
- stale/revoked capability lease;
- event replay causing duplicate external effect;
- forged UI state attempting promote/ship without Core verdict;
- malicious/compromised tool update requesting new capability/egress;
- workflow definition attempting to bypass mandatory verification/human gate.

## H.3 Security ownership by mission

Security is not deferred to one final audit:

- REV-3A closes project/write-root safety;
- DDE-070–076 close worker/provider/harness isolation and credentials;
- DDE-077 closes mutation/staging security;
- DDE-080 closes truth/context/evidence integrity;
- DDE-082 closes design/workflow compiler policy safety;
- DDE-083 performs integrated adversarial and supply-chain certification.

---

# Appendix I — Observability, SLO, performance and capacity realisation plan

## I.1 Provisional service budgets

Each owning mission must create provisional measured budgets for interactive/core/provider operations it introduces. Budgets are configuration/contract data, not comments buried in code.

At minimum specify:

```text
latency target
operation timeout
queue/concurrency limit
payload/context/artifact limit
availability/degraded behavior
measurement window
provider time accounting rule
```

Do not invent “infinite” capacity or hide provider latency inside Core latency.

## I.2 Required dashboards/projections

By DDE-081/DDE-083 operators must be able to inspect:

- mission/task/run health;
- provider/harness health and certified capability;
- quota/reset/fallback state;
- context pressure/continuations;
- event backlog/consumer lag;
- failure/retry/reconciliation counts;
- change packet/staging blocks;
- verification outcomes and evidence invalidations;
- design/preview health;
- cost per verified success;
- service-budget breaches;
- release/capacity health.

## I.3 Benchmarking cadence

Performance benchmarks run:

- per mission for new hot paths;
- after material storage/event architecture changes;
- on DDE-083 release candidate across declared deployment profiles;
- after certified executable updates that may affect performance.

## I.4 Capacity release proof

DDE-083 publishes a tested `CapacityEnvelope` for each supported release deployment profile. The release notes/operator UI must not imply scale beyond the certified envelope.

---

# Appendix J — Deployment, migration, backup and disaster-recovery plan

## J.1 Deployment manifest

Maintain a reconstructable release/deployment manifest containing:

```text
DDE revision
schema versions
policy versions
configuration hashes
provider/harness/tool certified versions
artifact/storage compatibility
migration set
feature flags/canaries
```

## J.2 Migration rehearsal

Any mission introducing persistent-schema changes must add migration tests immediately. DDE-083 performs full upgrade/rollback/restore rehearsal from the supported pre-Rev-3 baseline and at least one representative partially-upgraded failure point.

## J.3 Backup/restore verification

Before release certification, prove:

1. accepted truth/EDRs restore;
2. mission/task/route history restore;
3. evidence metadata and required artifact proof restore;
4. projections rebuild where designed to be rebuildable;
5. stale leases are invalidated after restore;
6. ambiguous external effects are not replayed blindly;
7. EvidenceValidityGraph is consistent after restore.

## J.4 Update lifecycle integration

Executable update certification is treated as a deployment migration:

```text
detect → quarantine → certify → canary → promote
                              ↘ reject
promoted regression → rollback
```

Provider model-version changes that materially alter capability/behavior may require re-certification even when no local binary changes.

---

# Appendix K — Cross-platform parity implementation plan

## K.1 Surface matrix required at every UI/API-affecting mission

The chapter gate includes:

| Capability | VS Code/DDE Code | Electron | Frontend Studio | CLI | MCP | API | Other supported | Parity class |
|---|---|---|---|---|---|---|---|---|
| `CAP-*` | state/action | state/action | state/action | state/action | state/action | state/action | state/action | classification |

Use `N/A` only with rationale.

## K.2 Host-bridge discipline

DDE-069 establishes host adapters. Later missions add capabilities through shared typed commands/projections first, then thin host-specific presentation. Do not separately implement business logic in VS Code and Electron.

## K.3 Semantic parity tests

Automated tests should prove that equivalent host requests:

- call the same Core command/query family;
- receive equivalent state semantics;
- enforce equivalent authorization;
- cannot promote/ship from a host that lacks authoritative verification.

## K.4 Offline/degraded parity

Where a host supports cached/offline reads, test freshness indicators, reconnect conflict handling and prohibition of stale high-risk approvals.

---

# Appendix L — Capability certification and evidence-ledger implementation plan

## L.1 Certification service/projection

Do not wait until DDE-083 to invent certification. Build a thin capability-realization/certification projection as early as practical, then deepen it through DDE-080.

The service/projection must support:

```text
current realization state
required evidence classes
latest valid evidence
inherited evidence
invalidated evidence
residuals
last certified revision/config
certification status
```

## L.2 Mission gate promotion rule

A chapter gate may mark:

- a mission `PASS` while some non-release-critical capability remains below `VERIFIED` only if the mission acceptance explicitly permits that residual and records the owning later mission;
- a capability `VERIFIED` only when its certification exists and evidence is current;
- `PASS-WITH-EDR` only when the EDR explicitly accepts the residual/risk and names the expiry/revisit trigger where appropriate.

## L.3 Release certification pack

DDE-083 produces a release pack containing:

```text
release manifest
capability certification ledger
traceability orphan report
security/adversarial report
migration/restore report
capacity envelope + service-budget report
golden mission report
chaos/recovery report
tool/provider certification report
cross-platform parity report
known residuals/EDRs
```

No single model summary substitutes for this evidence pack.

---

# Appendix M — Detailed hardening acceptance matrix by mission

The following acceptance deltas are added to existing mission criteria; they do not replace the mission-specific requirements already defined above.

## REV-3A hardening acceptance

Must additionally prove:

- `SM-BOOTSTRAP` transitions and expiry/invalidation;
- correlation/project identity present on controlled commands/events;
- wrong-root, stale receipt and config-contamination adversarial tests;
- `SM-CHANGE-PACKET` rejection/disposition/staging states;
- path/symlink/write-set escape blocked;
- evidence invalidation/inheritance scenario produces deterministic delta;
- operator receives typed blocking reason, not generic failure.

## DDE-068 hardening acceptance

Must additionally prove:

- `SM-VERIFICATION` including `INCONCLUSIVE/BLOCKED`;
- visual evidence bound to exact ProductEnvironment/revision/state/viewport;
- verifier outage cannot auto-pass;
- preview/critic latency/failure telemetry exists;
- stale visual evidence invalidates only when dependent rendering/design/runtime inputs change.

## DDE-069 hardening acceptance

Must additionally prove:

- every mutating workbench action maps to typed Core command;
- host adapters share semantic state;
- DesignCandidate state machine prevents DESIGN→LIVE semantic collapse;
- Try-Live crash/stale preview handled truthfully;
- parity matrix exists for VS Code/Electron/Studio/CLI-MCP-API relevant capabilities;
- design provider cannot receive forbidden context/secrets.

## DDE-070 hardening acceptance

Must additionally prove:

- WorkerSession full lifecycle, cancel, checkpoint, resume and crash recovery;
- BootstrapReceipt required at real worker launch;
- harness capabilities/version recorded and bound to session;
- stale capability lease rejected;
- context/session service budgets measured.

## DDE-071 hardening acceptance

Must additionally prove:

- desired/configured/serving model states are distinct and persisted;
- OCL-1 configured changes never emit fake attested occupancy;
- ModelServingEvidence source/confidence is validated;
- strategic lease transitions and atomic repromotion occur only at the control level that supports them;
- fallback occupant excluded from conflicting subordinate pool as policy requires when occupancy is attested;
- bounded Fable subagent evidence cannot be mislabeled as parent-session orchestration;
- plan proposal/promote commands remain DDE-owned;
- Fable/Opus outage/reset scenarios are observable and cost-attributed;
- no stale strategic occupant after lease expiry/failure;
- high-risk model-specific claims block or disclose when serving attestation is absent.

## DDE-072 / DDE-073 / DDE-074 hardening acceptance

Each worker adapter must additionally prove:

- exact installation/model/harness/profile version lineage;
- exact model-control capability certification, including serving-model visibility and OCL level where orchestration-capable;
- normalized failure/retry semantics;
- real-call usage and cost capture where provider exposes it;
- cancellation/timeout behavior;
- secret/egress/tool scope;
- no provider-native state bypasses Core authority;
- independent verification outcome feeds ExperienceRecord only after evidence.

## DDE-075 hardening acceptance

Must additionally prove:

- Hermes authoritative-vs-derived storage boundary;
- memory item provenance/trust/freshness;
- retrieval prompt injection cannot grant capability or alter Project Truth;
- ExperienceContext/RoutingInsight are advisory inputs with policy-controlled promotion;
- stale/incorrect memory can be superseded without rewriting Core history.

## DDE-076 hardening acceptance

Must additionally prove:

- installation/profile/provider capacity are persisted with owners and freshness;
- capability certification lifecycle is explicit;
- provider capacity unknown/stale has safe route semantics;
- version changes invalidate only dependent capability certifications;
- fleet query/projection supports operator inspection.

## DDE-077 hardening acceptance

Must additionally prove:

- task→workspace→ChangePacket→write set→staging→commit trace is reconstructable;
- rejected mutations cannot contaminate accepted commits;
- conflict/rebase/merge ambiguity has explicit packet lineage;
- broad staging guard covers actual index content, not only intended paths;
- commit manifest binds exact accepted packet set.

## DDE-078 hardening acceptance

Must additionally prove:

- canonical telemetry schema across providers;
- quota/reset fact provenance and freshness;
- context/orchestrator-desired/configured/serving/occupancy/token/cost fields distinguish unknown from zero;
- configured→serving mismatch/unknown duration is observable;
- service-budget breaches and event backlog are observable;
- cost per verified success can be computed from persisted data.

## DDE-079 hardening acceptance

Must additionally prove:

- route features/labels have versioned schema;
- only verified outcomes materially train/update route evidence;
- confidence/calibration and sparse-data fallback are explicit;
- exploration cannot violate hard capability/security/data-egress/authority policy gates;
- routing policy candidate goes replay→holdout→shadow→canary→promotion;
- operator can explain why selected route beat alternatives.

## DDE-080 hardening acceptance

Must additionally prove:

- bidirectional requirement/capability/contract/evidence trace queries;
- release-critical orphan detector;
- generated realization report cannot overclaim runtime state;
- EvidenceValidityGraph handles schema/policy/tool/design/runtime dependencies;
- DeltaAuditPlan is the smallest safe re-verification set for tested deltas;
- context provenance/trust/freshness is inspectable.

## DDE-081 hardening acceptance

Must additionally prove:

- graph derives from durable runtime IDs/events, not UI-local graph data;
- node commands use same Core command paths as other surfaces;
- replay/reroute/fork preserve original immutable lineage;
- backlog/degraded/failure state appears in graph and Attention Center;
- large mission graph uses pagination/virtualization/streaming within measured budget.

## DDE-082 hardening acceptance

Must additionally prove:

- Workflow Composer compiles to policy-validated canonical workflow definition;
- workflow cannot encode a bypass around mandatory gates;
- playbooks carry capability requirements rather than hard-coded model identity unless justified;
- design/workflow artifacts have version/lineage/certification;
- provider outage and design/live divergence have explicit recovery;
- promoted design/code pair is exact and immutable for verification reference.

## DDE-083 hardening acceptance

Must additionally prove all integrated Rev 3.3 closure artifacts:

- threat/adversarial matrix PASS or accepted EDR residual;
- full migration + restore rehearsal;
- tested service budgets and capacity envelopes for supported release profiles;
- cross-platform parity report;
- release-critical traceability orphan count = 0;
- all release-critical capability certifications current;
- tool/harness/plugin update certification and rollback exercised;
- golden + chaos missions run against exact release candidate manifest;
- final EvidenceValidityGraph recomputed after integration;
- release certification binds code/config/policy/schema/tool/provider facts.

---

# Appendix N — Rev 3 program risk register

The development program maintains these risks explicitly. A mission that materially changes a risk updates its status/evidence.

| Risk | Failure mode | Primary mitigation | Owning gate/mission |
|---|---|---|---|
| R-01 config contamination | agent operates on wrong project/root | ProjectIdentity + fail-closed bootstrap | REV-3A / DDE-070 |
| R-02 premium-model creep | fallback becomes universal expensive worker | role occupancy separated from worker eligibility | REV-3A / DDE-071 / DDE-079 |
| R-03 context collapse | long session loses constraints/invents state | ContextBudget + ContinuationPackage | REV-3A / DDE-080 |
| R-04 mutation contamination | rejected/unrelated work reaches commit | ChangePacket + staging manifest | REV-3A / DDE-077 |
| R-05 evidence theatre | tests/docs imply capability not on production path | realization ladder + certification | all / DDE-080/083 |
| R-06 stale proof | changed invariant leaves old PASS trusted | EvidenceValidityGraph + DeltaAuditPlan | REV-3A / DDE-080 |
| R-07 provider lock-in | provider-native contracts become architecture | adapters + provider-neutral contracts | DDE-070–076 / 082 |
| R-08 Hermes authority creep | memory becomes routing/truth owner | advisory contracts + governed promotion | DDE-075/079 |
| R-09 design theatre | artboards called LIVE / no real app proof | DesignGateway + Try-Live + semantic states | DDE-069/082 |
| R-10 decorative workflow graph | visual graph diverges from runtime | event/state-derived projection | DDE-081 |
| R-11 tool supply-chain regression | auto-update changes behavior/capabilities | certify/canary/promote/rollback | DDE-083 |
| R-12 hidden security expansion | worker/plugin gains new egress/tool scope | capability manifests + threat tests | DDE-070–076/083 |
| R-13 cost blindness | cheap route causes expensive rework | cost per verified success | DDE-078/079 |
| R-14 capacity collapse | UI/control plane degrades under fanout/artifacts | service budgets + CapacityEnvelope | DDE-078/081/083 |
| R-15 migration/data loss | Rev 3 schema evolution corrupts authority/evidence | migration/backup/restore rehearsal | each schema mission / DDE-083 |
| R-16 cross-platform drift | hosts show different semantics/authority | shared commands/projections + parity tests | DDE-069 onward |
| R-17 traceability orphaning | requirements/features/code/evidence disconnect | stable IDs + compiler/orphan gates | DDE-080/083 |
| R-18 false release confidence | final gate misses integrated failure modes | release certification + golden/chaos suite | DDE-083 |
| R-19 orchestrator identity overclaim | configured/requested model is presented as the model serving a running parent session | OrchestratorModelState + ModelServingEvidence + OCL certification + disclosure/block policy | REV-3A / DDE-071 / DDE-073 / DDE-078 |

---

# Appendix O — Hardened immediate-execution rule

The Rev 3.3 hardening is **normative immediately after adoption**, but it does not move the product baseline and it does not justify reopening completed work indiscriminately.

The next engineering action remains:

```text
REV-3A.1 ProjectIdentity / bootstrap preflight
```

When implementing that slice, the agent must use the Appendix C implementation-resolution pack and the relevant Blueprint Rev 3.3 appendices from the first commit onward. Existing DDE-065/066/067 evidence is inherited unless a changed dependency or invariant specifically invalidates it.

The locked execution order remains:

```text
REV-3A → DDE-068 → DDE-069 → DDE-070 → DDE-071 → DDE-072 → DDE-073
→ DDE-074 → DDE-075 → DDE-076 → DDE-077 → DDE-078 → DDE-079
→ DDE-080 → DDE-081 → DDE-082 → DDE-083
```

**No implementation agent may respond to Rev 3.3 by creating more planning documents instead of implementing the next evidence-producing slice.**
