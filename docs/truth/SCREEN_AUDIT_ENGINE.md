# DDE Frontend Studio — Canonical Screen Audit & Experience Completeness Engine

**Status:** USER-LOCKED / REV3 CANONICAL EXTENSION — 2026-09-04  
**Mission scope:** DDE-069 — DDE Code / Frontend Studio V2 + Live Design Foundation  
**Parent authority:** `docs/truth/FRONTEND_STUDIO_REV3.md` (AD-036)  
**Global authorities:** `docs/truth/BLUEPRINT_REV3.md`, `docs/truth/DEV_PLAN_REV3.md`, accepted Project Truth rows / EDRs  
**Related implementation ledger:** `docs/truth/FRONTEND_STUDIO_BINDING_MATRIX.md`  
**Verification dependency:** DDE-068 Visual Verification & Critique Loop  

> This document is a subordinate canonical extension of `FRONTEND_STUDIO_REV3.md`. It does **not** create a second Frontend Studio architecture. It defines the Screen Audit / Experience Completeness capability that DDE-069 must integrate into the existing PXG, Frontend Contract, Coverage, candidate, mutation, verification, chat and live-design architecture. Where this document conflicts with an accepted Project Truth row or the parent Rev 3 architecture, the higher-ranked authority wins and the conflict must be resolved through normal change control.

---

# 0. Decision

DDE-069 shall include a first-class **Screen Audit & Experience Completeness Engine** inside Frontend Studio.

It must not be implemented as:

- a separate audit application;
- a static report generator;
- a screenshot inventory;
- a parallel source of truth;
- an AI-only critique feature;
- a second coverage engine;
- a second project graph;
- a separate mutation path;
- a collection of manually maintained spreadsheets.

It is a **derived intelligence and verification layer** over the canonical DDE project model:

```text
Project source / runtime
        +
Project Experience Graph (PXG)
        +
Frontend Contract
        +
Coverage Engine
        +
Routes / journeys / role-policy evidence
        +
Candidate / mutation lineage
        +
DDE-068 rendered visual verification
        +
Accessibility / functional / security evidence
        ↓
SCREEN AUDIT ENGINE
        ↓
ScreenAuditRun
ScreenAuditScreenRecord
ScreenAuditFinding
ScreenAuditEvidence
ScreenAuditResolution
        ↓
Coverage / Architecture / QA / Design / Inspector / Chat / /design
```

The engine must answer both:

> **What screens and experiences actually exist?**

and

> **What screens and experiences are required to exist?**

The comparison between those two truths is the core of the audit.

---

# 1. Product objective

The Screen Audit Engine turns Frontend Studio from a screen editor into a **continuous product-experience completeness system**.

For any project DDE builds or maintains, Frontend Studio should be able to determine, with evidence:

- which screens exist;
- which screens should exist;
- what each screen is for;
- which journeys reach it;
- which roles/personas may use it;
- which features/requirements it satisfies;
- which visible controls are actually functional;
- which UI states exist and which are missing;
- which data dependencies are real;
- which routes are unreachable or dead-ended;
- which screens are duplicated or orphaned;
- which required platform variants are missing;
- which accessibility/security requirements are satisfied;
- which DDE-068 visual checks are bound and current;
- what changed since the previous audit;
- which findings block promotion;
- what repair candidate addresses a finding;
- whether a finding is actually resolved after promotion and re-audit.

The system must be usable on small projects and on products containing hundreds or thousands of screens/components.

---

# 2. Dial depth-and-breadth quality rule, applied to DDE

This capability must meet the same implementation depth-and-breadth discipline used by Rev 3 generally, without importing Dial application architecture or business logic into DDE.

Every Screen Audit feature must map:

```text
authority
→ schema / contract
→ service owner
→ writer
→ reader
→ production call site
→ state machine
→ permissions
→ failures / recovery
→ evidence / provenance
→ observability
→ performance / scale
→ UI surface
→ verification
→ lifecycle
```

A screen-audit capability is partial if any applicable link is absent.

---

# 3. Architectural laws

## 3.1 No duplicate project truth

Screen Audit does not own screen definitions independently of PXG and Frontend Contract.

- PXG owns the structured product-experience graph and stable node identity.
- Frontend Contract owns declared product obligations.
- Coverage Engine owns obligation assessment semantics.
- DDE verification owns actual verification results/evidence.
- Candidate/mutation services own change lineage.
- Screen Audit derives findings from those systems and records audit-run-specific evidence.

Do not create another route registry, screen graph, requirements table or coverage percentage source unless a real missing domain exists and is approved through change control.

## 3.2 Bidirectional audit

Auditing only source code is insufficient.

The engine must compare:

```text
IMPLEMENTATION → what exists

against

PRODUCT CONTRACT → what must exist
```

The system therefore detects both:

- implemented-but-unrequired / orphaned / stale surfaces; and
- required-but-missing / incomplete surfaces.

## 3.3 Evidence, not AI confidence

Deterministic evidence should decide deterministic questions.

Models may assist where perception or semantic interpretation is genuinely required, but:

- a model does not self-certify completion;
- a model does not directly resolve an audit finding;
- a model does not bypass DDE-068 verification;
- a model does not invent a route, requirement, role or state to make coverage look complete.

## 3.4 No uncertainty laundering

Do not collapse unknown, unimplemented, unverified, blocked and failed into one percentage.

Reuse Coverage Engine semantics wherever possible.

A dimension may expose a numeric percentage only when the underlying obligations are sufficiently assessed according to the Coverage Engine's rules.

Unknown must remain unknown.

## 3.5 No silent omission

If a required screen/state/platform/interaction is deferred, waived, not-applicable or accepted as an exception, the record must name the durable authority/decision that permits it.

---

# 4. Canonical screen identity

Every audited screen must resolve to stable project identity.

The preferred anchor is the existing PXG `pxg_key` / stable node identity.

A `ScreenAuditScreenRecord` must not depend solely on:

- DOM order;
- route text;
- filename;
- visible title;
- screenshot hash.

These are evidence/properties, not sufficient identity.

Conceptual identity relation:

```text
pxg_key
↔ screen node
↔ route / navigation identity
↔ source reference(s)
↔ runtime/render target
↔ candidate/revision lineage
↔ audit findings
```

DOM reflow or a source-file move must not silently retarget findings to another logical screen.

---

# 5. Canonical domain model

Introduce schema-first objects only where no equivalent already exists.

Minimum domain concepts:

## 5.1 `ScreenAuditRun`

Represents one reproducible audit against exact inputs.

Minimum conceptual fields:

```yaml
audit_run_id:
tenant_id:
project_id:
mission_id:
source_revision:
pxg_revision:
frontend_contract_id:
frontend_contract_version:
policy_version:
role_policy_hash:
design_system_hash:
started_at:
completed_at:
status:
trigger:
parent_audit_run_id:
summary_state:
```

## 5.2 `ScreenAuditScreenRecord`

One audited logical screen.

Conceptual fields:

```yaml
record_id:
audit_run_id:
pxg_key:
screen_kind:
platform:
module_or_product_area:
route_identity:
source_refs:
journey_refs:
role_refs:
feature_requirement_refs:
data_dependency_refs:
component_inventory_ref:
verification_binding_refs:
render_evidence_refs:
implementation_state:
assessment_state:
```

## 5.3 `ScreenAuditFinding`

A durable, typed finding bound to evidence.

Conceptual fields:

```yaml
finding_id:
audit_run_id:
pxg_key:
node_key_optional:
finding_type:
dimension:
severity:
status:
message:
evidence_refs:
requirement_refs:
journey_refs:
role_refs:
first_detected_at:
last_observed_at:
resolved_at:
resolution_ref:
decision_ref_optional:
stale:
```

## 5.4 `ScreenAuditEvidence`

References existing evidence where possible instead of duplicating blobs.

Examples:

- VerificationRun / CheckResult;
- DDE-068 screenshot/render evidence;
- AcceptanceOracle bindings;
- PXG node/edge snapshots;
- Frontend Contract obligation versions;
- route-graph snapshots;
- role-policy evaluation;
- source/provenance records;
- candidate/mutation revisions;
- accessibility results;
- runtime interaction evidence.

## 5.5 `ScreenAuditResolution`

Records how a finding moved out of an unresolved state.

A resolution may point to:

- promoted candidate/revision;
- accepted Project Truth / EDR decision;
- accepted exception;
- requirement supersession;
- verified source correction.

A chat response or model assertion is not a valid resolution.

---

# 6. Screen audit dimensions

Audit every applicable screen across independent dimensions.

Do not require all dimensions to reduce to one score.

## 6.1 Contract completeness

Check:

- required screen exists;
- screen maps to intended requirement(s);
- mandatory feature is represented;
- required state/interaction exists;
- no-silent-omission decision references are valid.

Examples of findings:

- `REQUIRED_SCREEN_MISSING`
- `REQUIREMENT_UNMAPPED`
- `SCREEN_WITHOUT_PRODUCT_OBLIGATION`
- `DEFERRED_WITHOUT_DECISION`

## 6.2 Journey completeness

Check:

- intended journey reaches the screen;
- entry and exit paths exist;
- no dead end unless intentionally terminal;
- required alternate/error path exists;
- journey transition references valid screens/actions.

Findings:

- `SCREEN_UNREACHABLE`
- `JOURNEY_DEAD_END`
- `MISSING_TRANSITION`
- `BROKEN_RETURN_PATH`

## 6.3 Functional control completeness

For meaningful controls, verify the canonical equivalent of:

```text
visible control
→ read state
→ action/command
→ authority check
→ state transition
→ result
→ failure state
→ evidence
```

Findings:

- `VISIBLE_CONTROL_UNBOUND`
- `ACTION_NO_PRODUCTION_CALL_SITE`
- `COMMAND_WITHOUT_FAILURE_STATE`
- `STATIC_STATUS_PRESENTED_AS_LIVE`

## 6.4 State completeness

Check applicable states such as:

- loading;
- empty;
- error;
- success;
- disabled;
- offline/degraded;
- permission denied;
- stale/conflict;
- destructive confirmation;
- retry/reconciliation where applicable.

Findings:

- `MISSING_LOADING_STATE`
- `MISSING_EMPTY_STATE`
- `MISSING_ERROR_STATE`
- `DESTRUCTIVE_ACTION_NO_CONFIRMATION`
- `OFFLINE_STATE_REQUIRED_MISSING`
- `PERMISSION_STATE_MISSING`

## 6.5 Data completeness

Check:

- displayed data is backed by a real read model/source;
- unknown is not fabricated as zero;
- required data state exists;
- stale and loading semantics are represented;
- sensitive data exposure obeys policy.

Findings:

- `FABRICATED_DISPLAY_DATA`
- `READ_MODEL_MISSING`
- `STALE_DATA_UNDISCLOSED`
- `SENSITIVE_FIELD_EXPOSED`

## 6.6 Role / permission completeness

Check:

- intended roles can reach screen/action;
- forbidden roles cannot;
- role-specific views/states exist where required;
- UI does not imply authority that Gateway/Core denies.

Findings:

- `ROLE_CANNOT_REACH_REQUIRED_SCREEN`
- `ROLE_CAN_REACH_FORBIDDEN_SCREEN`
- `CONTROL_VISIBLE_WITHOUT_AUTHORITY`
- `PERMISSION_DENIAL_NOT_HANDLED`

## 6.7 Navigation completeness

Check route and navigation graph consistency.

Findings:

- orphan route;
- dangling navigation target;
- duplicate canonical route;
- route collision;
- stale deep link;
- modal/overlay path with no recovery.

## 6.8 Accessibility

Consume real accessibility evidence where available.

Audit:

- keyboard reachability;
- focus order;
- accessible names;
- roles/semantics;
- contrast;
- text scaling;
- reduced motion;
- non-pointer alternatives;
- live/status announcements where required.

Unknown accessibility state remains `NOT_EVALUATED`, never pass.

## 6.9 Responsive / platform completeness

Check required target states by contract.

Examples:

- desktop;
- tablet;
- mobile web;
- React Native / Expo target;
- Android native target where scoped;
- other declared platform adapters.

Do not infer cross-platform parity from one renderer.

Findings:

- `REQUIRED_VIEWPORT_UNVERIFIED`
- `PLATFORM_VARIANT_MISSING`
- `PARITY_OBLIGATION_MISSING`
- `PLATFORM_BEHAVIOUR_DIVERGENCE`

## 6.10 Visual quality

Consume DDE-068 evidence rather than building a second visual critic.

At minimum surface:

- silhouette/distinctiveness;
- visual critique;
- believable density;
- visual diff where a valid golden exists;
- accessibility visual defects;
- bounded-repair state;
- final promotion verdict.

## 6.11 Source / provenance

Check:

- source is known;
- generated/imported/donor origin is recorded;
- license/admission state is valid where relevant;
- design-system version is known;
- current implementation has not detached from its tracked source.

## 6.12 Security

Check screen-level product security facts that can be derived safely:

- forbidden data exposure;
- privileged action without adequate authority path;
- unsafe external content handling;
- inconsistent permission presentation;
- missing confirmation/reconciliation around consequential actions.

This does not replace DDE's broader security capability.

## 6.13 Drift

Detect disagreement between:

- source;
- PXG;
- Frontend Contract;
- routes;
- roles;
- candidate lineage;
- verification bindings;
- design-system version.

Drift is a first-class finding, not an implementation detail.

---

# 7. Finding severity and lifecycle

## 7.1 Severity

Use explicit policy, not model tone.

Minimum classes:

```text
BLOCKING
ERROR
WARNING
INFO
```

A finding is `BLOCKING` only when a canonical policy says it blocks the relevant progression/promotion.

Examples likely to be blocking:

- required screen absent;
- critical journey dead-end;
- mandatory DDE-068 check missing/failed/errored;
- security/permission violation;
- mandatory state absent;
- unsupported destructive flow;
- accepted code would be mutated outside governed candidate flow.

## 7.2 Lifecycle

Canonical conceptual lifecycle:

```text
DETECTED
→ CONFIRMED
→ CANDIDATE_CREATED / ASSIGNED
→ VERIFYING
→ RESOLVED
```

Alternative branches:

```text
DETECTED → ACCEPTED_EXCEPTION
DETECTED → BLOCKED
DETECTED → SUPERSEDED
```

Rules:

- `RESOLVED` requires re-audit evidence after the applicable change is promoted/accepted.
- `ACCEPTED_EXCEPTION` requires a durable decision reference.
- a generated repair proposal does not resolve the finding.
- deleting a finding record does not resolve it.
- changed inputs can mark prior findings/evidence `STALE`.

---

# 8. Evidence validity and staleness

Every audit must be reproducible against exact versions.

An audit/finding should bind to applicable hashes/versions such as:

```text
source revision
PXG revision
Frontend Contract version
role-policy hash
route graph revision
candidate revision
design-system hash
verification-run IDs
render-evidence IDs
```

When a relevant dependency changes, DDE must either:

- invalidate the finding/evidence;
- mark it stale;
- selectively re-audit affected nodes.

Do not silently carry a PASS from a previous revision onto changed content.

---

# 9. Incremental audit dependency graph

Full-project audit must exist, but ordinary operation should be incremental.

Triggers include:

- screen registered;
- screen removed;
- PXG node/edge changed;
- Frontend Contract changed;
- route/navigation changed;
- role/permission policy changed;
- candidate promoted;
- accepted source changed;
- verification result changed;
- design-system revision changed;
- platform target requirement changed;
- source/provenance changed.

Example:

```text
CheckoutButton mutation promoted
        ↓
identify affected PXG node
        ↓
re-audit selected control
        ↓
re-audit Checkout screen
        ↓
re-evaluate linked Checkout journey obligations
        ↓
update affected Coverage / QA projections
```

Do not re-audit an entire thousand-screen project for a local spacing mutation when dependency evidence proves the impact is local.

---

# 10. Service boundaries

Prefer domain-specific services behind existing Gateway/Core rules.

Conceptual services:

```text
ScreenAuditService
ScreenDiscoveryService
ScreenAuditRuleRegistry
ScreenAuditReconciliationService
ScreenAuditProjectionService
```

Do not create these names mechanically if existing services already own the behavior.

Responsibilities:

## `ScreenAuditService`

- create/run audit;
- resolve exact inputs;
- execute deterministic checks;
- request existing verification evidence;
- persist findings/evidence references;
- publish projections/events.

## `ScreenDiscoveryService`

- derive implemented screen inventory from accepted PXG/source/runtime evidence;
- never mint authoritative screens based on guesses.

## `ScreenAuditRuleRegistry`

- version deterministic audit rules;
- declare which dimensions/findings are blocking;
- declare applicability by screen/platform/contract type.

## `ScreenAuditReconciliationService`

- compare implementation inventory with Frontend Contract obligations;
- identify missing/orphaned/duplicated/drifted states;
- handle stale findings.

## `ScreenAuditProjectionService`

- provide Screen Matrix;
- QA findings;
- Architecture overlays;
- Inspector/Canvas audit context;
- Chat context.

---

# 11. Gateway / command surface

User-facing or automated state changes must remain behind existing Gateway/Core authority.

Candidate command/read types may include equivalents of:

```text
frontend.audit.run
frontend.audit.recompute_affected
frontend.audit.accept_exception
frontend.audit.create_repair_candidate
frontend.audit.read_summary
frontend.audit.read_screen
frontend.audit.read_findings
frontend.audit.read_matrix
```

Before adding commands:

- inspect existing command patterns;
- reuse `mission.control` or another existing scope only if semantically valid;
- do not widen autonomy/security scope merely for convenience;
- preserve CommandLedger/idempotency rules.

Pure reads should remain reads rather than side-effect commands.

---

# 12. Frontend Studio UI integration

Screen Audit is integrated into the existing locked Frontend Studio modes. Do not add a separate top-level "Audit app" unless a future approved product decision requires it.

## 12.1 Coverage mode — Screen Matrix

Coverage mode becomes the primary cross-screen completeness matrix.

Example conceptual presentation:

```text
Screen          Contract  Journey  Functional  States  A11y  Visual  Platform
Login              ✓        ✓          ✓          ✓      ✓      ✓       ✓
Dashboard          ✓        ✓          ✓          !      ✓      ✓       ?
Orders             ✓        ✓          ✓          ✓      ?      !       ✓
Checkout           ✓        !          !          !      ✓      ✓       ✓
```

Rules:

- `?` means unknown/not evaluated, not pass;
- row/column filters operate on real projections;
- clicking a screen opens that screen in Design mode/live canvas when available;
- clicking a finding opens evidence/details;
- do not invent percentages when dimensions are not assessed.

## 12.2 Architecture mode — Experience Graph

Architecture mode renders real PXG / journey / route relations with audit overlays.

Required overlays include applicable:

- orphan screens;
- unreachable screens;
- dead ends;
- missing contract nodes;
- duplicate routes;
- role-specific reachability;
- platform gaps;
- unresolved blocking findings.

No hardcoded demo graph.

## 12.3 QA mode — Audit Findings Workbench

QA aggregates real findings by:

- severity;
- screen;
- journey;
- dimension;
- role;
- platform;
- finding lifecycle;
- age/staleness;
- candidate/repair state.

Every finding links to evidence and source/project context.

## 12.4 Design mode — audit overlays

Once the real preview runtime exists, the canvas can overlay:

- blocking finding markers;
- missing-state badges;
- accessibility markers;
- verification state;
- role/platform context;
- stale evidence indicators.

Overlays must be optional and must not modify the target candidate.

## 12.5 Inspector — Audit section

For a selected `pxg_key` / stable node, show applicable audit facts such as:

```text
Contract       PASS
Action         PASS
Loading        PASS
Failure        MISSING
Disabled       PASS
Accessibility NOT_EVALUATED
Visual         PASS
Responsive     PARTIAL
Source         checkout/SubmitOrderButton.tsx
```

Inspector audit state must resolve from real ScreenAudit/PXG/verification projections.

## 12.6 Source mode — provenance and drift

Source mode exposes:

- implementation source;
- component origin;
- donor/provider lineage;
- version/license/admission where relevant;
- design-system mapping;
- source drift;
- local mutation lineage.

---

# 13. Frontend Chat integration

Frontend Chat must receive audit context as part of the same conversation/design session architecture.

Supported conceptual requests include:

```text
/audit current screen
show missing states in checkout
which screens implement ORDER-F023?
show unreachable screens
find customer journeys that dead-end
show role-specific screen gaps
create candidates for the three blocking checkout findings
```

Rules:

- deterministic audit queries use deterministic services/read projections;
- deterministic repair instructions use the existing MutationPlanner where possible;
- generative repair requests may route through DesignGateway;
- ambiguity is refused rather than guessed;
- Chat cannot mark a finding resolved.

---

# 14. Claude `/design` / DesignGateway integration

Audit findings should become bounded `DesignEditContext` constraints.

Example:

```text
Target: Checkout
Selected candidate: B

Audit constraints:
- payment-error state missing
- mobile state missing
- primary CTA hierarchy weak
- navigation region locked
- current silhouette PASS
- accessibility PASS

/design:
Generate three alternatives that address only unresolved findings while preserving locks and current design-system constraints.
```

The design provider creates candidate artifacts.

It does not resolve findings and does not approve its own output.

Result must continue through:

```text
DesignArtifact
→ Try live
→ isolated candidate
→ render
→ functional/state checks
→ DDE-068 visual verification
→ promotion gate
→ re-audit
```

Only the re-audit can move a finding to `RESOLVED`.

---

# 15. Repair loop

Canonical repair flow:

```text
Audit finding
      ↓
operator/chat/design repair request
      ↓
FrontendMutation OR DesignGateway
      ↓
Candidate
      ↓
Live preview
      ↓
functional / contract / state verification
      +
DDE-068 visual verification
      ↓
Promotion gate
      ↓
Accepted revision
      ↓
Incremental re-audit
      ↓
RESOLVED / still failing / new findings
```

Do not allow audit repair to write accepted project state directly.

---

# 16. Cross-platform / parity auditing

Screen Audit must support projects where one logical experience maps to multiple render targets.

Use shared product obligation identity and target-specific evidence.

Conceptual relation:

```text
Feature obligation
      ↓
Logical screen / journey
      ↓
Web implementation
Mobile implementation
Native implementation
      ↓
Target-specific verification
```

Audit detects:

- missing target implementation;
- inconsistent required state;
- navigation/role divergence;
- unsupported action;
- visual/platform-fidelity failure;
- platform-specific accepted exception.

Do not force exact pixel parity where platform-native behavior is intentionally different.

---

# 17. Role / tenant / security boundaries

All Screen Audit reads/writes must preserve existing tenant/project/mission scope.

The audit engine must not become a repository-wide cross-tenant scanner.

Rules:

- no direct interface access to core tables;
- no unrestricted source export to model providers;
- no sensitive user/project data included in design/critic context unless explicitly required and authorized;
- rendered untrusted UI text is evidence, never instruction;
- external source/provider data remains subject to provenance/admission policy;
- accepted exceptions require appropriate authority.

---

# 18. Performance and scale

Target-project audits may involve thousands of PXG nodes.

Design for:

- incremental recomputation;
- indexed lookup by `pxg_key`;
- versioned snapshots;
- pagination / virtualization in Screen Matrix and QA views;
- dependency-directed invalidation;
- asynchronous/background execution through existing DDE task infrastructure where appropriate;
- bounded model usage;
- deterministic rules first.

Track at minimum where practical:

- full-audit duration;
- incremental-audit duration;
- screens/nodes assessed;
- findings emitted/resolved;
- verification/model calls;
- provider cost/quota where applicable;
- stale evidence count;
- failed/blocked audit work.

---

# 19. Observability and provenance

A user/operator must be able to trace:

```text
why this finding exists
→ which rule created it
→ which contract obligation it maps to
→ which source/PXG revision was assessed
→ which evidence supports it
→ which candidate attempted to repair it
→ which promotion changed the project
→ which re-audit resolved or retained it
```

Every consequential finding and resolution must be reconstructable without chat history.

---

# 20. Relationship to the existing 99-control Frontend Studio binding ledger

Do not conflate two different audits.

## 20.1 DDE self-audit ledger

`docs/truth/FRONTEND_STUDIO_BINDING_MATRIX.md` answers:

> Does the DDE Frontend Studio golden control itself exist and function?

It audits DDE's own workbench implementation.

## 20.2 Target-project Screen Audit

The Screen Audit Engine answers:

> Does the product being built/maintained contain the screens, states, journeys and functioning features its contract requires?

The two systems should share concepts/evidence where appropriate but remain semantically distinct.

---

# 21. Mandatory binding-ledger hardening discovered during DDE-069 review

The current binding matrix has a semantic weakness: some rows can be classified `VERIFIED` because backend production files/tests exist even when the named **visible golden control** is not present or wired in the React workbench.

Example class of defect:

```text
"Chat composer" domain/backend implemented
but no composer rendered in DdeStudioApp
→ row must not be called fully VERIFIED
```

DDE-069 must harden the ledger before closure.

Preferred model: multidimensional binding evidence, for example:

```text
DOMAIN
READ
COMMAND
UI
WIRED
E2E
VISUAL
```

or another equivalent schema that guarantees a visible control cannot reach final `VERIFIED` while its UI or end-to-end wiring is absent.

Minimum invariant:

> A golden visible-control row may reach final `VERIFIED` only when every applicable layer required by its own contract is evidenced, including the real UI surface and real production wiring.

Do not simply rename statuses without enforcing the rule in `engine/studio/binding_matrix.py` and tests.

---

# 22. Dogfood requirement

The first comprehensive production proof of Screen Audit must audit **DDE Frontend Studio itself**.

Use the canonical 99-control binding ledger as an independent comparison source.

The dogfood run should identify known current gaps such as:

- live canvas absent;
- stable selection absent;
- Inspector not yet wired to selection;
- Frontend Chat UI absent despite backend capability;
- `/design` provider transport unavailable;
- source intelligence gaps;
- pixel-reference conformance blocked by missing golden artifact.

The dogfood run must not be scripted to produce those expected answers. They are expected test evidence; the engine must derive them from real project state.

Compare:

```text
Screen Audit findings
vs
FRONTEND_STUDIO_BINDING_MATRIX
vs
actual React/Gateway/runtime behavior
```

Disagreement becomes a reconciliation finding, not something silently ignored.

---

# 23. Implementation sequence from current DDE-069 state

This extension is adopted while DDE-069 is already in progress. Do not restart the mission.

Preserve the work already landed on the DDE-069 branch:

- M1/M2 characterization, golden-manifest machinery and 99-control ledger;
- PXG;
- Frontend Contract;
- Coverage Engine;
- read projections;
- automatic DDE-068 screen verification bindings;
- unified mutation/lock/candidate architecture;
- host-neutral React/TS/Vite shell;
- Frontend Chat backend/control-plane semantics;
- DesignSession / DesignArtifact / DesignGateway architecture;
- honest typed refusal for missing certified design transport.

Proceed dependency-first.

## Packet A — binding-ledger correctness

1. harden final `VERIFIED` semantics so visible controls require actual UI + wiring + tests;
2. reclassify current rows from evidence;
3. add regression tests preventing backend-only false verification.

## Packet B — live preview vertical slice

Prove:

```text
candidate
→ code-backed isolated preview
→ canvas render
→ stable pxg_key selection
→ Inspector descriptor resolution
→ governed Inspector mutation
→ candidate rerender
→ DDE-068 verification invalidation/re-run
→ candidate state update
```

This is higher priority than adding more disconnected UI panels.

## Packet C — Screen Audit core

Schema-first implementation of:

- audit run;
- screen record;
- finding;
- evidence references;
- reconciliation;
- deterministic contract/journey/state/function rules;
- read projections;
- incremental dependency invalidation.

## Packet D — audit UI

Integrate:

- Coverage Screen Matrix;
- QA findings workbench;
- Architecture graph overlays;
- Design/Canvas markers;
- Inspector Audit section.

## Packet E — Chat / `/design` audit loop

Wire audit queries and repair candidates into the already-existing conversation/DesignSession architecture.

## Packet F — dogfood proof

Run Screen Audit against DDE Frontend Studio and reconcile with the 99-control ledger.

## Packet G — M8 source intelligence and remaining golden closure

Continue the existing DDE-069 source adapter/template/provenance work and remaining unbound golden controls. Screen Audit should then consume source/provenance evidence rather than reimplement it.

---

# 24. Acceptance / Definition of Done

Screen Audit is not complete because a report renders.

It is complete only when evidence proves at least one real project can perform:

```text
load accepted project
→ discover implemented screens
→ load Frontend Contract obligations
→ reconcile required vs actual
→ produce typed findings
→ render Screen Matrix
→ open finding on real screen
→ map finding to stable pxg_key/source/evidence
→ create governed repair candidate
→ render candidate live
→ verify function/state
→ run DDE-068 visual verification
→ deny promotion when mandatory finding remains
→ promote corrected candidate
→ incremental re-audit
→ finding becomes RESOLVED from evidence
```

And also prove negative paths:

- contract requires missing screen;
- orphan screen exists;
- unreachable journey;
- visible control lacks action;
- mandatory error/empty/loading state missing;
- wrong role access;
- critic/verification unavailable;
- stale audit evidence;
- accepted exception without decision reference is refused;
- candidate repair does not alter accepted state before promotion;
- unknown assessment does not become a fake percentage/pass.

---

# 25. DDE-069 closure impact

DDE-069 may not be marked `COMPLETE_EVIDENCED` while the adopted Screen Audit capability is represented only as inert schemas/docs.

For DDE-069 closure:

- core Screen Audit domain must be real;
- Coverage/QA/Architecture integration must be usable;
- live canvas/Inspector audit integration must work where the canonical Studio exposes it;
- Chat must query audit state;
- repair candidates must follow governed mutation/design paths;
- DDE-068 remains the visual verification authority;
- the dogfood audit against DDE Frontend Studio must run;
- Project Truth / implementation state must be reconciled from evidence.

A provider-dependent `/design` action may remain a typed external capability blocker if no certified transport exists, but the audit engine and deterministic repair/query paths must not be blocked on that provider.

---

# 26. Non-goals

This decision does not authorize:

- a new DDE mission number;
- a separate Screen Audit frontend product;
- a second PXG;
- a second Coverage Engine;
- automatic mutation of accepted code;
- model-driven waiver of hard requirements;
- replacement of DDE-068 visual verification;
- export of whole private repositories to a model;
- fabricated screen counts or scores;
- silent platform parity assumptions;
- importing Dial business-unit architecture into DDE.

---

# 27. Final product law

DDE Frontend Studio must eventually be able to answer, for every important screen:

```text
WHY DOES THIS SCREEN EXIST?
WHO CAN USE IT?
WHICH JOURNEY REACHES IT?
WHICH REQUIREMENT DOES IT SATISFY?
DO ITS CONTROLS ACTUALLY WORK?
ARE ALL REQUIRED STATES PRESENT?
IS THE DATA REAL?
IS IT ACCESSIBLE?
IS IT SECURE?
IS IT VERIFIED VISUALLY?
DO REQUIRED PLATFORM VARIANTS EXIST?
WHERE DID IT COME FROM?
WHAT IS STILL UNKNOWN?
WHAT BLOCKS PROMOTION?
WHAT CHANGE WILL FIX IT?
DID THE FIX ACTUALLY RESOLVE THE FINDING?
```

The answers must come from DDE evidence and project state, not from a model improvising a plausible story.
