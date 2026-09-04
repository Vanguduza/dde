# DDE FRONTEND STUDIO — CANONICAL TECHNICAL ARCHITECTURE, LIVE DESIGN CONTROL PLANE & QUANTUM IMPLEMENTATION MAP — REV 3

**Status:** CANONICAL FRONTEND-STUDIO DOMAIN ARCHITECTURE / USER-LOCKED CHANGE PACKAGE
**Quality bar:** Dial depth-and-breadth / quantum implementation standard
**Repository:** `Vanguduza/dde`
**Observed main HEAD when this document was prepared:** `b5753db672422aa4321188cf39302866f1c3cb88` (`docs: adopt Rev 3.3 orchestrator attestation truth`)
**Observed last product implementation baseline:** `c30d2969e3205d1a277dd128e8b182137a8892e0` (`DDE-067 Frontend Studio surface`)
**Golden UI authority:** user-approved DDE Frontend Studio mockup, 1672 × 941 px, approved 2026-09-03
**Consolidates:** `DDE FRONTEND STUDIO — CANONICAL ARCHITECTURE, PRODUCT EXPERIENCE SYSTEM & IMPLEMENTATION BLUEPRINT REV 2` in full, included later in this file
**Global DDE authorities to reconcile, not fork:** `docs/truth/BLUEPRINT_REV3.md`, `docs/truth/DEV_PLAN_REV3.md`, `docs/truth/ARCHITECTURE_DECISIONS.md`, `docs/truth/IMPLEMENTATION_STATE.md`, `docs/truth/RESUME_PROMPT.md`
**Change rule:** the golden visual law, no-silent-omission law, manager-authority law and existing proven DDE-067 safety invariants may change only through explicit user-approved revision.

**Adoption note (2026-09-04):** this document was integrated into the repository's Rev 3 truth set via `docs/truth/ARCHITECTURE_DECISIONS.md` AD-036 (adoption) and AD-035 (golden visual authority), and `docs/truth/ARCHITECTURE_DECISIONS.md` AD-030 (DDE-069 identity, resolving the naming drift this document itself flags in §2.2 below). `docs/truth/DEV_PLAN_REV3.md` §6 and `docs/truth/IMPLEMENTATION_STATE.md`'s DDE-069 section point back here. Read those four files alongside this one; they record the reconciliation decisions, this file remains the detailed technical architecture.

> **Canonical intent:** The approved screen is not a concept image. Every visible control in it must resolve to a real read model, command, state transition, provider capability, preview action, validation result, or explicitly honest unavailable state. Decorative product theatre is forbidden.

---

# 0. EXECUTION PROMPT — INTEGRATE THIS ARCHITECTURE FROM THE CURRENT DDE STATE

Copy the following block verbatim into the active DDE Project Manager/Orchestrator session when adopting this document into the repository.

```text
You are the DDE Project Manager/Orchestrator responsible for integrating the new canonical Frontend Studio architecture into the EXISTING Vanguduza/dde repository. This is an incremental migration, not a restart and not permission to replace already proven infrastructure.

PRIMARY OBJECTIVE
Transform the current DDE-067 Frontend Studio surface into the user-locked professional Frontend Studio shown by the approved 1672×941 golden mockup, while preserving DDE Core authority, the proven Gateway/CommandLedger mutation path, donor approval controls, token conformance, workspace isolation, tenant/project boundaries and operational honesty. Implement every visible feature in the locked UI as a software-usable capability. No decorative controls, fake counts, fabricated scores, invented provider status, fake LIVE state or fake sync state are allowed.

NEW DOMAIN AUTHORITY
Read this entire document first. It consolidates the previous Frontend Studio Rev 2 blueprint and adds the repository-grounded technical integration required for the current codebase. Treat it as the canonical Frontend Studio domain specification to be reconciled into the global Rev 3 truth set. Do not create a competing architecture tree.

MANDATORY GLOBAL AUTHORITIES
Before editing, read:
- docs/truth/BLUEPRINT_REV3.md
- docs/truth/DEV_PLAN_REV3.md
- docs/truth/ARCHITECTURE_DECISIONS.md
- docs/truth/IMPLEMENTATION_STATE.md
- docs/truth/RESUME_PROMPT.md
- AGENTS.md
- docs/planning/dde-067-chapter-gate.md
- docs/planning/frontend-studio-gui-spec.md
- docs/planning/product-studio-charter.md
- docs/planning/design-tooling-integration.md
- docs/planning/gap-closure-record.md

CURRENT REPOSITORY REALITY TO VERIFY, NOT BLINDLY ASSUME
At preparation time main HEAD was b5753db672422aa4321188cf39302866f1c3cb88 and product implementation remained DDE-067. Verify current HEAD and recent commits before acting. Inspect at minimum:
- interfaces/dde-studio/shared/ui/frontendStudio.ts
- interfaces/dde-studio/src/webviews/providers.ts
- interfaces/dde-studio/src/extension.ts
- interfaces/dde-studio/shared/studioGateway.ts
- interfaces/dde-studio/shared/gatewayClient.ts
- interfaces/dde-studio/shared/clientHonesty.test.ts
- interfaces/dde-studio/visual/**
- engine/studio/frontend.py
- engine/studio/canvas.py
- engine/studio/compiler.py
- engine/studio/tokens_catalog.py
- engine/gateway/commands.py
- engine/donor/**
- engine/verification/**
- schemas/design/** and relevant command/object schemas

DO NOT REBUILD PROVEN DDE-067 PATHS
Preserve and reuse:
- StudioGatewayService.sendFrontendCommand -> POST /v1/commands
- CommandLedger/idempotency admission
- GatewayCommandService frontend dispatch
- FrontendStudioService production command boundary, evolving it into a compatibility façade rather than an ever-growing monolith
- WorkspaceService-backed artifact writes
- donor reuse approval and mission/donor scope-hash enforcement
- semantic design-token fail-closed validation
- tenant/project scope checks
- no-fabricated-data/client-honesty rules
- existing verification, Playwright, visual_diff and Prototype Gallery seams

SOURCE-OF-TRUTH DRIFT TO RESOLVE FIRST
Current DEV_PLAN_REV3 Rev 3.3 defines DDE-069 as "DDE Code / Frontend Studio V2 + Live Design Foundation", while the current IMPLEMENTATION_STATE snapshot still labels DDE-069 as deferred Mobile/Multi-target work. Reconcile this projection drift explicitly from evidence. Do not silently reinterpret history. Update IMPLEMENTATION_STATE and ARCHITECTURE_DECISIONS as appropriate after the domain plan is adopted.

VISUAL AUTHORITY UPDATE
The user-approved golden mockup supersedes the older DDE-069 visual-direction phrases that required dark-first and broadly prohibited gradients. The canonical shell is now light-first, neutral, dense and precision-oriented exactly as the golden reference. Dark mode remains a derived supported theme. Gradients remain prohibited in DDE application chrome but are allowed inside the project content being designed/previewed when the target project permits them. Preserve the semantic-token and non-generic-workbench principles.

CLAUDE /DESIGN REQUIREMENT
Add a first-class visible `Claude /design` button to the Frontend Studio canvas toolbar. It must not be a terminal-opening gimmick. It must participate in the same DesignSession, DesignEditContext, Frontend Chat, Project Experience Graph, Frontend Contract, locks, candidate runtime, provenance and acceptance architecture as all other design operations.

Implement provider-neutral DesignGateway contracts with Claude as the first certified provider. Prefer a certified direct Claude Design MCP/OAuth transport when available; a certified Claude Code `/design` WorkerSession transport is an allowed alternative. Do not automate terminal keystrokes as the architectural interface when a structured transport is available. Capability/version/auth state must be discovered and recorded. If Claude Design is unavailable, show a typed honest state and route only to another certified design provider if policy allows. Never silently substitute a generic code-generation prompt and call it `/design`.

The `Claude /design` button must:
1. use current selection or current screen as its default scope;
2. open/focus the shared Design Dock and Frontend Chat context rather than creating a disconnected conversation;
3. compile a minimal allowlisted DesignEditContext;
4. use the exact design-system snapshot/hash and Frontend Contract/PXG slice;
5. create one or more versioned DesignArtifact candidates;
6. place those artifacts into neutral Direction A/B/C cards;
7. leave the accepted design untouched;
8. require Try live to create an isolated code-backed candidate workspace;
9. allow chat, comments and direct manipulation to refine the same DesignSession;
10. preserve provider/artifact/context provenance;
11. require DDE verification before promotion;
12. never label a pure artboard or screenshot as LIVE.

CLAUDE DESIGN SYNC
Implement project design-system synchronization as a governed capability. DDE remains the authority for project design tokens/components/locks. Sync only the allowlisted design-system snapshot to Claude Design, record provider sync identity and content hash, and invalidate/resync when the project design-system hash changes. Expose Sync design system as a secondary action in the Claude /design control and Source mode; do not make provider state the project source of truth.

21ST / TEMPLATE INTELLIGENCE
Integrate 21st through a DesignSourceAdapter/MCP boundary for search, inspection and retrieval. Do not let 21st paste directly into production. Search internal approved components first, then approved external registries/donors according to source policy. Every external artifact passes provenance, license, dependency, security, framework, accessibility and Design System Compiler gates.

Change donor semantics: donor repositories are atomic evidence/directive sources, not automatic whole-project design law unless explicitly locked as such. At project/frontend intake, Frontend Studio must be able to recommend suitable full templates/foundations from DDE libraries, 21st and other enabled providers, then let the user lock a selected or blended direction.

MOBILE PATH
For mobile projects, use platform-specific source adapters such as BNA UI/gluestack/React Native Reusables as qualified sources and Expo MCP/device tooling as runtime/validation capabilities. Do not treat mobile as resized web. Keep provider interfaces replaceable and version-gated.

ONE MUTATION ARCHITECTURE
Chat, drag/drop, property edits, template blending, 21st imports, Claude /design refinements, agent edits and keyboard operations must all compile to the same FrontendMutation/MutationPlan architecture. No client path may directly patch accepted code or bypass locks, coverage, provenance or candidate isolation.

ONE CONVERSATION/DESIGN SESSION
Frontend chat is the conversational control surface for the entire studio. `/design` is a mode/capability within that same control plane, not a second chat system. Persist FrontendConversation/DesignSession lineage, selected-node references, candidate references and mutation history so the user can say things like "take Candidate B's sidebar, keep the locked nav, and ask /design for three hero alternatives" without context loss.

GOLDEN UI FUNCTIONALITY LAW
Map every visible feature in the approved mockup to a real capability before declaring reconstruction complete: project selector; save/sync state; Design/Coverage/Architecture/QA/Source modes; coverage gauge; notification/attention center; project explorer; screens/journeys/components counts; DDE Library/21st/donor/internal source states; templates; locks; QA counts; Manager Chair/Design Director status; viewport controls; selection/pan/comment/grid/zoom/fullscreen; real preview; selection handles; lock badges; inspector layout/style/behaviour/lock/provenance/accessibility/responsive controls; frontend chat; Claude /design; candidate cards; Source Blend; actual scores; error/warning status; Auto Layout; AI Suggest; breadcrumbs; build/version state. If backend support is not yet present, the UI must show a typed unavailable/pending state rather than fabricated information.

SAVE/SYNC HONESTY
A 202 command acceptance is not "Saved" or "Synced". Introduce durable mutation/projection revision semantics. "Synced" is shown only when no local planned mutation is pending and the authoritative read projection confirms the accepted durable revision. Event push may use an admitted stream when available; explicit polling/read-after-write fallback is permitted but must be labeled honestly.

MANAGER AUTHORITY
The Project Manager/Orchestrator owns the frontend programme. Design Director is a subordinate role/projection, not a second orchestrator. Obey configured Manager-Chair eligibility. Lower-tier workers may search, compile, implement and validate bounded packets but may not silently change product scope, locks, accepted design, or final acceptance. Desired/configured/serving model identity must remain distinct; do not display a serving model as known without valid ModelServingEvidence.

DDE-068 DEPENDENCY
Do not skip DDE-068. The final DDE-069/Frontend Studio V2 promotion must consume real rendered visual verification. Preparatory schema/UI/runtime work may be developed in isolated non-promoted packets only if global mission sequencing and write ownership allow it; it cannot be marked complete or promoted around the DDE-068 gate.

IMPLEMENTATION ORDER
0. Preflight current branch/HEAD, repository identity and focused baseline tests.
1. Reconcile truth drift and adopt this document into the Rev 3 truth hierarchy without creating duplicate authority.
2. Preserve DDE-067 contract tests and add characterization tests around current Gateway/frontend mutations.
3. Close/consume DDE-068 prerequisites needed by V2.
4. Introduce the host-neutral React/TypeScript/Vite UI runtime behind dependency admission; keep legacy string renderers as compatibility shims until replacement proof is green.
5. Implement DdeHostBridge for VS Code, Electron/DDE Code and tests; remove direct acquireVsCodeApi calls from feature code.
6. Implement the canonical DDE shell/tokens/primitives to match the golden mockup and add golden screenshot tests.
7. Implement real Frontend Studio read projections/list surfaces/events so the new UI can populate without fabrication.
8. Implement PXG, Frontend Contract, Product Experience Template and multi-dimensional Coverage Engine.
9. Implement unified mutation/lock/conflict engine and candidate/worktree/live-preview runtime.
10. Implement source adapters, template recommendation, Design System Compiler and provenance/security gates; 21st first among external web registries.
11. Implement Frontend Chat as the shared conversation/control plane.
12. Implement DesignGateway + ClaudeDesignAdapter + `Claude /design` button + design-system sync + Design Dock; prove chat and button share one DesignSession.
13. Implement mobile source/runtime adapters behind the same contracts when project scope requires them.
14. Bind every golden-screen control to real state/commands and finish the functional binding matrix.
15. Run functional, keyboard, accessibility, responsive, security, visual, failure-injection and cross-host tests.
16. Promote only after DDE-068 evidence, coverage reconciliation, provenance, source/security gates and manager acceptance pass.
17. Migrate all remaining DDE windows to the same shared shell/primitives, preserving module-specific functionality.
18. Update IMPLEMENTATION_STATE, ARCHITECTURE_DECISIONS, DEV_PLAN/BLUEPRINT references and resume state continuously from evidence.

QUALITY RULE
Quality is more important than being "done". Do not reduce scope to make a gate green. If a capability cannot be made real in the current packet, leave it explicit, typed and blocked rather than decorating the UI as if it exists.

AUTONOMY
Continue autonomously through all unblocked phases and bounded packets. Do not wait for a "resume" message between green phases. Stop only for: explicit user-authority decisions; credentials/OAuth the user must supply; a hard external dependency; a source-of-truth conflict that cannot be resolved by the authority hierarchy; or a destructive/irreversible action requiring approval.

REQUIRED END-OF-PHASE REPORT
For every phase report:
- exact files changed;
- contracts/schemas added or extended;
- existing call paths preserved;
- tests/evidence run and result;
- screenshot/visual evidence where applicable;
- coverage delta;
- unresolved gaps/blockers;
- next autonomous phase.
```

---

# 1. WHY REV 3 EXISTS

Rev 2 established the correct product-experience model: golden visual law, Project Experience Graph (PXG), Frontend Contract, comprehensive Product Experience Template, source adapters, unified mutation protocol, functional locks, candidate isolation, provenance, Manager ownership, QA and cross-DDE migration. The live repository, however, is still at the DDE-067 implementation boundary and the global Rev 3 plan contains a mixture of already-proven seams, planned DDE-068/DDE-069 work, and older visual assumptions.

Rev 3 therefore does four things simultaneously:

1. **grounds the Frontend Studio architecture in the actual current repository;**
2. **closes technical gaps between the approved golden UI and software reality;**
3. **makes Claude `/design`, 21st/template intelligence and mobile design sources first-class but governed capabilities;**
4. **turns every visible element of the locked mockup into a contract-backed usable feature.**

Rev 3 does not remove Rev 2. The full Rev 2 canonical body is consolidated into Part XXVII of this document and remains binding except where Rev 3 explicitly hardens or clarifies its integration into the current repository.

---

# 2. REPOSITORY-GROUNDED CURRENT STATE

## 2.1 What is real now

At the observed repository state:

- DDE-067 is complete/evidenced for its signed scope.
- `interfaces/dde-studio/shared/ui/frontendStudio.ts` renders six string-template views: Home, Intake, Donors, Canvas, Verify and Approvals.
- ordinary authoring is currently mission UUID + command selector + raw JSON parameters, with a small canvas palette/drop zone and token selects.
- `StudioGatewayService.sendFrontendCommand` sends structured `frontend.*` commands through the existing Gateway command ledger with a generated command UUID and idempotency key.
- `GatewayCommandService` dispatches frontend commands to `FrontendStudioService`.
- `FrontendStudioService` performs compile, donor discovery/intake/adoption, canvas insert/move/update/remove, motion and flow mutations.
- donor-derived insertion is fail-closed behind approved `donor_reuse` scope.
- semantic token values are validated at the server mutation boundary.
- client honesty tests explicitly reject fabricated rows/verdicts.
- current frontend webview feature code calls `acquireVsCodeApi()` directly inside generated HTML.
- current Frontend Studio is presented through `WebviewViewProvider` surfaces rather than a host-neutral full workbench application runtime.
- richer list/read surfaces remain incomplete; the DDE-067 chapter gate records missing list reads honestly.
- true event push is not yet available in the Studio path.
- DDE-068 visual verification/critique is still planned and pixel signoff intentionally fails closed.
- Rev 3.3 plans DDE-069 Frontend Studio V2 + live design, including `DesignGateway`, `ClaudeDesignAdapter`, `DesignSession`, `DesignArtifact`, `DesignEditContext`, `LiveEditWorkspace` and a first usable live-design loop.

## 2.2 Current truth-projection drift

A material documentation inconsistency exists and must be corrected during adoption:

- `docs/truth/DEV_PLAN_REV3.md` Rev 3.3 now defines **DDE-069 — DDE Code / Frontend Studio V2 + Live Design Foundation**.
- `docs/truth/IMPLEMENTATION_STATE.md` still describes **DDE-069 — Mobile / multi-target** as deferred.

This is not permission to renumber or erase history. The implementation-state projection must be refreshed from the current canonical plan and repository evidence.

**Resolution (2026-09-04):** see `docs/truth/ARCHITECTURE_DECISIONS.md` AD-030. `IMPLEMENTATION_STATE.md`, `ARCHITECTURE_DECISIONS.md` and `RESUME_PROMPT.md` have been updated to match `DEV_PLAN_REV3.md`.

## 2.3 Visual-direction drift

The older DDE-069 plan says "dark-first", "no gradients" and "no generic SaaS card grid." The user has subsequently approved and locked a specific light-first Frontend Studio mockup as the DDE-wide visual baseline.

Rev 3 resolves this without discarding the useful design discipline:

- canonical reference theme: **light-first**;
- dark theme: required derived parity theme, not golden baseline;
- shell: neutral white/light grey with restrained blue/indigo/violet accents;
- DDE shell gradients: forbidden;
- target-project content gradients: allowed when project design law permits;
- dense panel/workbench architecture remains mandatory;
- generic kit appearance remains forbidden;
- component cards may exist where functionally appropriate, but the DDE application shell must not collapse into a marketing/SaaS dashboard grid.

## 2.4 Stack boundary clarification

The global plan says no Tailwind/shadcn visual layer for **DDE Code itself**. That remains a sound rule for the DDE shell. It must not be misapplied to projects DDE is designing.

Therefore:

- DDE Frontend Studio application chrome uses DDE primitives/tokens and authored CSS/CSS Modules (or an equivalent admitted implementation).
- A target project may use Tailwind/shadcn if its own Frontend Contract permits it.
- 21st artifacts commonly use React/Tailwind/shadcn conventions; they enter only through the Design System Compiler.
- if the target project does not use those technologies, DDE adapts the artifact into project-native primitives/styles before promotion.
- external styling dependencies may exist transiently inside a candidate sandbox but may not leak into the DDE shell or accepted target project against policy.

---

# 3. GAP REGISTER — LOCKED WORKING SETUP TO REV 3 TARGET

The following gaps are normative closure items.

| ID | Current gap | Risk if ignored | Rev 3 closure |
|---|---|---|---|
| FS-GAP-001 | giant generated HTML/string-template UI | brittle state and panel complexity | host-neutral React/TS/Vite workbench behind admitted dependency |
| FS-GAP-002 | feature code directly calls `acquireVsCodeApi()` | VS Code coupling; Electron/test divergence | `DdeHostBridge` with VS Code/Electron/Test implementations |
| FS-GAP-003 | six disconnected command-console views | cannot realize golden workbench | one Frontend Studio application surface with mode projections |
| FS-GAP-004 | missing list/read projections | fake rows/count temptation | typed Frontend read model and list/query capabilities |
| FS-GAP-005 | no true Studio event stream | stale "Synced"/status risk | capability-aware event subscription + honest polling fallback |
| FS-GAP-006 | client frontend commands are stringly typed | drift and invalid operations | generated typed command contracts/capability map |
| FS-GAP-007 | current canvas mutations write active Workspace directly | exploratory work can collide | `LiveEditWorkspace`/Candidate isolation before accepted promotion |
| FS-GAP-008 | no unified mutation planner | chat/MCP/direct editing could diverge | one `FrontendMutation` + `MutationPlan` path |
| FS-GAP-009 | no production PXG/Frontend Contract/Coverage Engine | thin implementation remains undetectable | implement Rev 2 experience/coverage domain |
| FS-GAP-010 | DDE-068 not implemented | UI quality can be overclaimed | real ProductEnvironment render/verification gate |
| FS-GAP-011 | Claude design architecture planned only | design button could become theatre | certified `DesignGateway` + `ClaudeDesignAdapter` vertical slice |
| FS-GAP-012 | no Claude Design capability/auth projection | button cannot be truthful | capability snapshot, OAuth/broker state, version/certification |
| FS-GAP-013 | `/design` could form a second conversation | context loss/conflicting edits | shared FrontendConversation + DesignSession + mutation planner |
| FS-GAP-014 | no governed design-system sync | provider may design off-brand | hashed `DesignSystemSnapshot` + sync record + invalidation |
| FS-GAP-015 | donors can be overinterpreted as project law | unwanted cloning/design lock-in | atomic donor directives with explicit strength/scope |
| FS-GAP-016 | no template recommendation intake | user forced to preselect donors | template/foundation recommendation across internal + external sources |
| FS-GAP-017 | 21st not a first-class source adapter | manual copy/paste bypass | 21st MCP adapter → inspect → compiler → candidate only |
| FS-GAP-018 | external component compatibility not normalized | dependency/design conflicts | Design System Compiler and target-stack adapters |
| FS-GAP-019 | mobile design source path not first class | resized-web mobile quality | BNA/gluestack/RN source adapters + Expo runtime validation |
| FS-GAP-020 | candidate scores can be misunderstood | synthetic confidence/theatre | explainable scorecards; `UNSCORED` until evidence exists |
| FS-GAP-021 | Source Blend percentages could be cosmetic | provenance theatre | component/node attribution; separate actual attribution from target blend weights |
| FS-GAP-022 | "Saved/Synced" has no durable revision semantics | false persistence claims | durable mutation revision + read-after-write/projection confirmation |
| FS-GAP-023 | left-tree counts may not have source reads | fabricated UI | counts derive from read model or display unknown/unavailable |
| FS-GAP-024 | Manager Chair card could overclaim model identity | violates serving-model truth | desired/configured/serving displayed separately from evidence |
| FS-GAP-025 | mockup shows px while current server enforces tokens | off-token write risk | display computed px + token identity; writes remain token-bound |
| FS-GAP-026 | inspector controls are not backed by generalized semantics | visual-only editor | property descriptor registry → deterministic mutations |
| FS-GAP-027 | no stable selection/instrumentation contract for real app | fragile DOM edits | preview instrumentation + stable PXG/source anchors + external overlay |
| FS-GAP-028 | no end-to-end undo/revert across sources | unsafe iteration | mutation event history + candidate rollback/revert |
| FS-GAP-029 | no unified attention/notification projection | top-right badges become decoration | Attention Center read model from real blockers/events |
| FS-GAP-030 | no full cross-DDE shell implementation | modules drift visually | shared DDE shell and module manifest migration |
| FS-GAP-031 | FrontendStudioService risks becoming monolith | unmaintainable backend | compatibility façade delegating bounded domain services |
| FS-GAP-032 | source provider outage semantics incomplete | false comprehensive search | health snapshots + degraded coverage labels + retry/fallback |
| FS-GAP-033 | large project loading not implemented | workbench stalls | incremental graph/read loading, virtualization, background validation |
| FS-GAP-034 | design provider usage/quota not surfaced | opaque failure/cost | provider capacity/limit state where observable; unknown remains unknown |
| FS-GAP-035 | current UI host themes can alter appearance | golden reference drift | DDE-owned theme tokens inside Studio; host-neutral rendering |
| FS-GAP-036 | current verification view cannot produce pixel signoff | Ship gate incomplete | DDE-068 evidence + admitted `prototype_pixel_signoff` type |
| FS-GAP-037 | no clear current-vs-working design semantic | accepted state can be edited inadvertently | `AcceptedDesignRevision` + `WorkingCandidate` separation |
| FS-GAP-038 | no source-of-truth reconciliation for code-added screens | graph/code drift | bidirectional reconciliation/orphan findings, never silent auto-trust |
| FS-GAP-039 | no real comment/annotation domain | toolbar comment could be decoration | anchored `DesignComment`/review thread model with status/resolution |
| FS-GAP-040 | no functional Auto Layout/AI Suggest semantics | status-bar theatre | explicit layout engine mode and suggestion policy state |

---

# 4. CANONICAL REV 3 SYSTEM ARCHITECTURE

## 4.1 One governed control plane

```text
                               PROJECT SOURCE OF TRUTH
                                         │
                         ┌───────────────┴────────────────┐
                         │                                │
                  Project Manager                 Frontend Contract
                  /Orchestrator                           │
                         │                                ▼
                         │                    Project Experience Graph
                         │                                │
                         └──────────────┬─────────────────┘
                                        ▼
                              FRONTEND PROGRAMME
                                        │
           ┌────────────────────────────┼────────────────────────────┐
           │                            │                            │
           ▼                            ▼                            ▼
   Design Source Plane           Interaction Plane             Evidence Plane
   internal/21st/donors/         chat/direct edit/             coverage/QA/
   templates/mobile              Claude /design                provenance
           │                            │                            │
           └────────────────────────────┼────────────────────────────┘
                                        ▼
                                Mutation Planner
                                        │
                                Lock/Conflict Gate
                                        │
                             Candidate/LiveEdit Workspace
                                        │
                   ┌────────────────────┼───────────────────────┐
                   ▼                    ▼                       ▼
             real preview            code diff               QA/evidence
                   │                    │                       │
                   └────────────────────┼───────────────────────┘
                                        ▼
                                  Acceptance Gate
                                        │
                                  promoted pair
                             DesignArtifact + code revision
```

## 4.2 Read/write/event separation

Frontend Studio must stop treating a webview as both state store and UI.

```text
READS
Gateway projections/read models
→ React query/projection cache
→ components

WRITES
UI intent
→ FrontendMutation/Design command
→ DdeHostBridge
→ StudioGatewayService
→ POST /v1/commands
→ CommandLedger
→ domain service
→ durable revision

EVENTS
Domain event / command outcome
→ admitted event transport when available
→ host bridge subscription
→ projection invalidation/update
→ UI

FALLBACK
No event transport
→ explicit polling/read-after-write
→ UI marks POLLING/STALE honestly
```

The client may own selection, panel width, hover state, open tabs and unsent text. It may not own mission truth, coverage truth, accepted design truth, manager identity, source licensing, QA verdicts or provider availability.

## 4.3 Revision semantics

Every authoritative frontend projection should include a monotonic or causally ordered `revision`/`version` field appropriate to the existing persistence model.

Minimum UI synchronization state:

```ts
type StudioSyncState =
  | { kind: 'LOCAL_DRAFT'; pendingMutationCount: number }
  | { kind: 'SUBMITTING'; commandId: string }
  | { kind: 'ACCEPTED_PENDING_PROJECTION'; commandId: string }
  | { kind: 'SYNCED'; authoritativeRevision: string; lastDurableAt: string }
  | { kind: 'STALE'; authoritativeRevision?: string; reason: string }
  | { kind: 'OFFLINE'; reason: string }
  | { kind: 'CONFLICT'; localBaseRevision: string; authoritativeRevision: string }
```

**Golden UI binding:** "Saved 2m ago · Synced" may render only from `SYNCED`. A 202 command acceptance maps to `ACCEPTED_PENDING_PROJECTION`, not saved completion.

---

# 5. HOST-NEUTRAL UI RUNTIME

## 5.1 Migration target

Use the Rev 3 global target path rather than creating a disconnected package universe:

```text
interfaces/dde-studio/ui/
  src/
    app/
      DdeStudioApp.tsx
      routes.ts
      providers.tsx
    shell/
      DdeShell.tsx
      GlobalTopBar.tsx
      AppRail.tsx
      ContextSidebar.tsx
      WorkspaceFrame.tsx
      InspectorPanel.tsx
      StatusBar.tsx
    frontend-studio/
      FrontendStudioWorkspace.tsx
      modes/
        DesignMode.tsx
        CoverageMode.tsx
        ArchitectureMode.tsx
        QaMode.tsx
        SourceMode.tsx
      explorer/
      canvas/
      inspector/
      chat/
      design/
      candidates/
      sources/
      coverage/
      qa/
      comments/
    components/
      primitives/
      data-display/
      feedback/
    bridge/
      DdeHostBridge.ts
      VsCodeHostBridge.ts
      ElectronHostBridge.ts
      TestHostBridge.ts
    state/
      projectionCache.ts
      ephemeralStore.ts
      commands.ts
      events.ts
    styles/
      tokens.css
      theme-light.css
      theme-dark.css
      global.css
  index.html
  vite.config.ts
```

This is a target decomposition. Before creating a file/package, search the repository for existing equivalents and reuse/migrate them.

## 5.2 Host bridge contract

```ts
interface DdeHostBridge {
  readonly hostKind: 'vscode' | 'electron' | 'test'
  getCapabilities(): Promise<HostCapabilities>

  sendCommand<T extends DdeCommand>(command: T): Promise<CommandAcceptance>
  requestRead<Q extends DdeReadQuery>(query: Q): Promise<ReadResult<Q>>
  subscribeEvents(filter: EventFilter, onEvent: (event: DdeEvent) => void): Unsubscribe

  revealFile(ref: SourceFileRef): Promise<void>
  openExternal(target: ApprovedExternalTarget): Promise<void>
  showNativeNotification(notification: DdeNotification): Promise<void>
  pickLocalFile?(options: PickFileOptions): Promise<PickedFile | null>
}
```

Feature components never call VS Code APIs directly. `acquireVsCodeApi()` is contained to the VS Code bridge bootstrap.

## 5.3 VS Code host strategy

The current six `WebviewViewProvider` surfaces remain compatibility shims during migration. The canonical Frontend Studio should open as a central full workbench `WebviewPanel`/equivalent editor surface capable of reproducing the golden composition. Legacy contributed views may:

- open/focus the new Frontend Studio workspace;
- show minimal status/shortcut information;
- remain until usage and regression evidence permit removal.

Do not attempt to reproduce the 1672×941 golden shell inside a narrow VS Code sidebar view.

## 5.4 Electron/DDE Code host strategy

DDE Code/Electron hosts the same React bundle and bridge contract. It should provide the closest pixel-equivalent realization of the full golden DDE shell because it controls the application surface.

## 5.5 Theme authority

The DDE workbench owns its tokens. VS Code host theme variables may inform native integration surfaces but may not silently recolor the golden Frontend Studio.

```text
canonical theme: dde-light
secondary parity theme: dde-dark
host theme: advisory/default-selection input only
```

---

# 6. BACKEND DOMAIN DECOMPOSITION

`engine/studio/frontend.py` remains the compatibility command façade. Rev 3 prevents it from becoming a second monolith by delegating to bounded services.

```text
engine/studio/
  frontend.py                 # compatibility façade / command dispatch
  reads.py                    # Frontend read-model composition
  contract/
    service.py
    validators.py
  pxg/
    service.py
    reconciliation.py
  coverage/
    service.py
    scoring.py
  mutations/
    planner.py
    executor.py
    rollback.py
  locks/
    service.py
    conflict.py
  design/
    gateway.py
    sessions.py
    context.py
    providers/
      claude_design.py
  sources/
    registry.py
    compiler.py
    adapters/
      internal.py
      donor.py
      twentyfirst.py
      mobile.py
  candidates/
    service.py
    worktrees.py
    reconciliation.py
  preview/
    service.py
    instrumentation.py
  provenance/
    service.py
  comments/
    service.py
  acceptance/
    service.py
```

Exact paths may be adapted to existing conventions; the domain boundaries are normative.

## 6.1 Domain ownership

| Domain | Owns | Must not own |
|---|---|---|
| `FrontendContractService` | project frontend obligations/version | source code mutation |
| `PxgService` | semantic experience graph | final executable truth by itself |
| `CoverageService` | multidimensional coverage calculation | self-reported completion |
| `MutationPlanner` | structured change plan/impact | direct provider calls |
| `LockService` | lock evaluation/change history | user/project scope definition |
| `DesignGateway` | provider-neutral design-session lifecycle | project truth or accepted design |
| `DesignSourceRegistry` | source discovery/health/candidates | direct production insertion |
| `DesignSystemCompiler` | normalization/adaptation report | approval/promotion |
| `CandidateService` | isolated candidate lifecycle | main/accepted branch writes |
| `PreviewService` | code-backed preview sessions | accepted design authority |
| `ProvenanceService` | source/artifact lineage | design scoring |
| `FrontendAcceptanceService` | gate aggregation/record | bypassing manager/user authority |

---

# 7. TYPED FRONTEND COMMAND, READ AND EVENT CONTRACTS

## 7.1 Command families

All writes still enter through the ordinary Gateway/CommandLedger. Extend command contracts schema-first rather than accepting arbitrary strings forever.

```text
frontend.contract.generate
frontend.contract.update
frontend.contract.reconcile

frontend.lock.create
frontend.lock.update
frontend.lock.remove

frontend.mutation.plan
frontend.mutation.apply
frontend.mutation.revert

frontend.candidate.create
frontend.candidate.reject
frontend.candidate.promote
frontend.candidate.rebase

frontend.design.sync_system
frontend.design.start_session
frontend.design.request
frontend.design.refine
frontend.design.try_live
frontend.design.discard
frontend.design.promote

frontend.source.search
frontend.source.import_candidate
frontend.source.request_adoption

frontend.preview.start
frontend.preview.stop
frontend.preview.set_state

frontend.comment.create
frontend.comment.resolve

frontend.verification.run
frontend.prototype.request_pixel_signoff
```

Existing DDE-067 command names remain supported behind compatibility adapters until migrated.

## 7.2 Read-model capability groups

The locked UI requires real list/read surfaces. Implement using existing Gateway conventions; exact URLs are secondary to these typed capabilities.

```text
FrontendStudioSnapshot
ProjectExplorerSnapshot
ScreenTreeSnapshot
JourneyInventory
ComponentInventory
DesignSourceInventory
TemplateInventory
LockInventory
QaFindingInventory
CoverageSummary + CoverageMatrix
FrontendCanvasSnapshot
InspectorDescriptor
DesignProviderStatus
DesignSessionReadModel
CandidateBoardSnapshot
SourceBlendSnapshot
OrchestratorFrontendStatus
AttentionCenterSnapshot
StudioSyncSnapshot
```

Each result includes:

- project/mission scope;
- authoritative revision/version;
- generated/observed time;
- partial/degraded flags;
- source capability status where relevant.

## 7.3 Event families

```text
frontend.contract.updated
frontend.pxg.updated
frontend.coverage.updated
frontend.coverage.regressed
frontend.mutation.planned
frontend.mutation.accepted
frontend.mutation.durable
frontend.lock.changed
frontend.lock.conflict
frontend.source.search_started
frontend.source.search_completed
frontend.source.health_changed
frontend.design.session_started
frontend.design.provider_state_changed
frontend.design.artifact_created
frontend.candidate.created
frontend.candidate.preview_ready
frontend.candidate.validation_updated
frontend.candidate.promoted
frontend.preview.selection_changed
frontend.comment.changed
frontend.verification.updated
frontend.attention.changed
```

Unknown/missing event transport does not authorize synthetic local events pretending the server changed.

---

# 8. GOLDEN UI — QUANTUM FUNCTIONAL BINDING MAP

Every row below is part of the Definition of Done. "Backing capability" means a real service/read/state transition, not a hardcoded local value.

## 8.1 Global top bar

| Golden feature | Software meaning | Backing capability | Required failure/empty behavior |
|---|---|---|---|
| DDE Frontend Studio title/logo | current DDE module | shell module registry | static product identity is allowed |
| project selector (`LogiFlow Marketplace`) | active ProjectIdentity/workspace | project read + authorized switch command/navigation | show unavailable/no project; never invent project |
| saved timestamp | last durable accepted frontend revision | StudioSyncSnapshot | hide timestamp if unknown |
| Synced status | client and authoritative projection converged | revision reconciliation | show Saving/Pending/Stale/Offline/Conflict |
| Design tab | design workspace | mode state + design snapshots | always usable if project open |
| Coverage tab | scope completeness workspace | CoverageService | explicit unassessed/blocked states |
| Architecture tab | PXG/component/dependency view | PXG + implementation map | show graph gaps, never guessed edges |
| QA tab | verification findings/evidence | verification/read models | unavailable when executor absent |
| Source tab | source/provider/provenance workspace | DesignSourceRegistry | provider health shown explicitly |
| Coverage 92% ring | weighted summary only | CoverageSummary | `—`/Unassessed if dimensions missing; click opens breakdown |
| activity/metrics icon | project frontend activity/telemetry | frontend activity projection | hide or disabled if not admitted |
| notification badge | real attention items | AttentionCenterSnapshot | zero/no badge if none; unknown not shown as count |
| help | context-sensitive docs/shortcuts | local docs registry | opens correct versioned help |
| user avatar | authenticated principal/session | auth/session projection | generic identity only if known |

## 8.2 App rail and project explorer

| Golden feature | Software meaning | Backing capability | Functional behavior |
|---|---|---|---|
| app rail module icons | DDE module navigation | module registry | switch modules without changing shell grammar |
| Project heading | active project explorer | ProjectExplorerSnapshot | project-scoped search/menu |
| search icon | semantic/local tree search | indexed read model | keyboard shortcut + no hidden mutation |
| Screens count/tree | real PXG/routes/screens | ScreenTreeSnapshot | count from authoritative inventory |
| Journeys count/tree | PXG journeys | JourneyInventory | opens journey map/coverage |
| Components count/tree | project component inventory | ComponentInventory | filter by native/external/deprecated |
| Sources group | source provider registry | DesignSourceInventory | health and scope aware |
| DDE Library | approved internal components/templates | internal adapter | search/preview/add candidate |
| 21st MCP | 21st source adapter | `TwentyFirstDesignSourceAdapter` | authenticate/search/inspect; no direct prod insertion |
| Donor Sources | approved/observed donor evidence | donor adapter | atomic directive view + adoption status |
| Internal Components | project-native inventory | project adapter | reuse before inventing |
| source numeric badges | actual indexed/returned eligible items | source inventory | `—`, error icon or stale marker when unknown |
| Templates group | project foundation/candidate templates | TemplateRecommendationService | inspect/compare/lock/blend |
| Template A/B/C | neutral recommended/favorited candidates | Template records | preview details; labels are not hardcoded permanently |
| Locks count | real lock inventory | LockService | filter by type/scope/owner |
| Style Locks | style/token locks | LockService | inspect/change with authority gate |
| Section Locks | region locks | LockService | same |
| Component Locks | component locks | LockService | same |
| QA Issues count | unresolved findings | QA inventory | drill down; severity and evidence |
| Accessibility count | a11y findings | verification results | no fabricated "AA" if not run |

## 8.3 Orchestrator card

| Golden feature | Software meaning | Backing capability | Honesty rule |
|---|---|---|---|
| Orchestrator ACTIVE | frontend programme manager runtime status | OrchestratorFrontendStatus | active only from actual session/lease state |
| Manager Chair | current eligible strategic authority | manager-role projection | desired/configured/serving distinguished |
| Design Director | subordinate design programme role | role assignment | never a second sovereign orchestrator |
| avatar/name | model/human identity if known | role identity + evidence | "Serving unknown" when unattested |
| waveform/activity | recent real design/orchestration events | activity window | no decorative random animation |
| status dot | health/activity | role health | typed active/paused/waiting/degraded/unknown |

## 8.4 Canvas toolbar

| Golden feature | Software meaning | Command/state |
|---|---|---|
| Desktop 1440 selector | target preview breakpoint | PreviewViewport state; persisted user preference optional |
| Select arrow | selection mode | local editor mode + preview selection instrumentation |
| Hand | pan mode | local canvas transform only |
| Comment bubble | anchored design review/comment | `DesignComment` create/resolve |
| grid/layout icon | grid/spacing/data overlays | PreviewOverlayState |
| **Claude `/design` button** | invoke shared design session for current scope | `frontend.design.request` via DesignGateway; detailed in Part 10 |
| zoom 100% | canvas transform | local ephemeral state |
| fullscreen/fit | editor presentation state | host capability/local state |

## 8.5 Real canvas and selection

| Golden feature | Software meaning | Required implementation |
|---|---|---|
| visible application screen | code-backed project preview | Candidate/LiveEdit PreviewRuntime, not screenshot background |
| route navigation | real route/state model | PreviewRuntime route control |
| selection outline | selected PXG/source node | instrumentation geometry → external overlay |
| resize handles | proposed layout mutations | drag translates to token/grid mutation; no direct persisted DOM style |
| Section Lock chip | effective lock on selected node | LockService result |
| Style Lock chip | style mutation restriction | LockService result |
| realistic data | deterministic safe fixture data | ProductEnvironment/fixture service |
| state simulation | loading/empty/error/offline/role states | PreviewScenario controls |

## 8.6 Frontend Chat composer

| Golden feature | Software meaning | Required implementation |
|---|---|---|
| prompt text field | shared FrontendConversation | persisted/threaded conversation linked to project/design session |
| current selection awareness | resolved node context | `DesignEditContext`/PXG refs |
| slider/settings icon | context scope/provider/action policy | chat context inspector; no hidden provider change |
| send button | parse/plan or inspect request | intent router → deterministic action or design request |
| natural "this/that/Candidate B" | reference resolution | stable IDs + ambiguity handling |
| design instruction | same design session as `/design` | DesignGateway when design-class intent requires it |
| ordinary deterministic edit | mutation planner | no unnecessary AI call |
| undo/revert requests | mutation history | candidate-safe revert |

## 8.7 Candidate/Directions dock

| Golden feature | Software meaning | Backing capability |
|---|---|---|
| Candidate A/B cards | isolated candidate revisions | CandidateService/worktree |
| thumbnail | current rendered candidate screenshot | Preview/verification artifact |
| 84%/76% score | explainable score summary | CandidateScore breakdown; `UNSCORED` until evidence |
| Good/Medium match | derived score classification | policy thresholds; clickable explanation |
| "2 changes" | actual structural mutation diff count | MutationPlan/code/PXG delta |
| Current (Locked) | accepted design revision | AcceptedDesignRevision + effective locks |
| Explore | request more design/source candidates | DesignGateway + source intelligence |
| compare | side-by-side real candidate renders | Candidate compare mode |
| accept/promote | reconciliation gate | candidate promotion command + manager acceptance |

## 8.8 Source Blend

The mockup combines provenance and desired mix. Rev 3 separates two concepts so the UI never lies.

```text
ACTUAL ATTRIBUTION
Template C > Hero Variant 2      60% attributable selected-region nodes
DDE Library > Navigation         40%

TARGET BLEND (for next generation only)
[slider 60/40]
```

- actual attribution is computed from component/PXG provenance records;
- target blend is an explicit design preference passed into a new candidate request;
- changing the target slider never rewrites provenance of the current design;
- if attribution cannot be computed, show named sources without fabricated percentages.

## 8.9 Inspector

| Golden control | Software action |
|---|---|
| Selected: Hero Section | stable PXG/source selection |
| layout tab | property descriptor group |
| style tab | token/style descriptor group |
| behavior tab | interaction/motion descriptor group |
| lock tab | lock inventory/action group |
| code/source tab | source mapping/read-only diff/reveal file |
| Type: Stack | deterministic layout mutation |
| Direction | deterministic layout mutation |
| Gap 24 px | display `space-token · computed px`; write token identity |
| Padding 64 px | same token-bound semantics |
| Style Lock | real lock state/action |
| Behaviour: Fade In | tokenized/validated animation reference |
| Section Lock | real lock state/action |
| Provenance | provenance record, source artifact, license/security status |
| View Source | reveal approved source/ref, subject to access policy |
| Accessibility AA / No issues | only after valid evidence; otherwise Not evaluated/Findings |
| responsive breakpoint buttons | switch viewport and selected responsive rule set |

### 8.9.1 Token-display rule

The golden screen may show numeric computed values for usability. Writes remain semantic:

```text
UI: Gap   24 px   [space-6]
WRITE: property=spacing.gap, token=space-6
```

If a project genuinely permits arbitrary values, that permission must be explicit in its Frontend Contract and the mutation creates a project token/custom value record rather than bypassing DDE-067 token safety accidentally.

## 8.10 Status bar

| Golden feature | Software meaning |
|---|---|
| breadcrumb | selected screen/region path from PXG |
| No errors | current known blocking error count, not build assumption |
| 23 warnings | actual unresolved warning count |
| Auto Layout: ON | project/editor layout-assist state; deterministic engine only |
| AI Suggest: ON | passive suggestion policy enabled; suggestions cannot auto-mutate accepted design |
| version | DDE Studio build/version + optional project revision |

---

# 9. REAL PREVIEW AND SELECTION ARCHITECTURE

## 9.1 Preview is executable

The canvas renders either:

1. the accepted project revision in a safe ProductEnvironment; or
2. the selected Candidate/LiveEditWorkspace revision.

A static design artifact is shown only in a clearly labeled `DESIGN` mode and can never receive the `LIVE` badge.

## 9.2 Preview instrumentation

Use a sandbox-only instrumentation layer rather than ad-hoc DOM mutation from the editor.

```text
project build
  ↓
preview instrumentation adapter
  ├─ stable DDE node/source anchors
  ├─ element geometry stream
  ├─ route/state metadata
  ├─ interaction capture hooks
  └─ selection events
  ↓
sandboxed preview frame/runtime
  ↓ postMessage/bridge
editor external overlay
```

Properties:

- no instrumentation in production build unless the target project explicitly ships it;
- stable node IDs map to PXG/source references;
- cross-origin/CSP rules are explicit;
- selection overlay lives in editor chrome where practical;
- direct manipulation emits a mutation plan, not persisted CSS against the live DOM;
- when stable mapping is impossible, inspector displays "source mapping unavailable" rather than guessing.

## 9.3 Code-backed LIVE badge

`LIVE` requires all of:

```text
candidate/workspace revision exists
+ build succeeds
+ preview runtime serves that revision
+ runtime health is ready
+ rendered route corresponds to the candidate
```

`DESIGN`, `BUILDING`, `LIVE`, `PROMOTED`, `VERIFIED`, `DISCARDED` remain semantically distinct.

---

# 10. CLAUDE `/design` — FIRST-CLASS FRONTEND STUDIO CONTROL

## 10.1 External capability reality

As of September 2026, Claude Design supports moving between Claude Design and Claude Code, including `/design`, `/design-sync`, and an official Claude Design MCP/OAuth integration. These capabilities are external and evolving; DDE must discover/certify them rather than freeze a version assumption into Core.

The architecture therefore exposes **Claude `/design` as a user-facing affordance** while keeping the backend provider-neutral.

## 10.2 Exact golden-UI placement

Add a compact primary design action to the canvas toolbar:

```text
[ viewport ] [ select ] [ hand ] [ comment ] [ grid ] [ ✦ Claude /design ▾ ]      [ 100% ] [ fit ]
```

The control uses the same restrained violet/indigo AI-action language as the golden chat Send button. It is prominent enough to discover but does not dominate the workbench.

## 10.3 One-click behavior

Primary click:

```text
resolve selected node(s)
  else current screen
  ↓
open/focus Design Dock
  ↓
attach `Claude /design` scope chip to shared Frontend Chat
  ↓
compile DesignEditContext
  ↓
show preflight summary when scope/egress/lock requires it
  ↓
submit frontend.design.request
  ↓
show in-place progress
  ↓
materialize Direction candidates
```

It does **not** spawn a detached terminal and type `/design` blindly.

## 10.4 Dropdown actions

Keep the default simple. Secondary menu:

- Design selected section;
- Design current screen;
- Explore 3 directions;
- Refine current candidate;
- Use selected template/source blend;
- Sync design system;
- Open in Claude Design (when provider artifact supports it);
- Provider status/authentication.

## 10.5 Button states

```text
UNAVAILABLE
AUTH_REQUIRED
SYNC_REQUIRED
READY
CONTEXT_COMPILING
SUBMITTING
GENERATING
CANDIDATES_READY
RATE_LIMITED / QUOTA_LIMITED (only if observable)
FAILED
```

The button may show a spinner/progress dot during active work, but provider activity remains visible in the shared activity/event model.

## 10.6 Provider capability contract

```ts
interface DesignProviderCapabilities {
  providerId: string
  providerVersion?: string
  transport: 'mcp' | 'worker_session' | 'other_certified'
  authState: 'ready' | 'required' | 'expired' | 'unknown'
  supportsDesign: boolean
  supportsDesignSync: boolean
  supportsMultipleDirections: boolean | 'unknown'
  supportsArtifactRefinement: boolean | 'unknown'
  supportsExternalCanvas: boolean | 'unknown'
  supportsProjectImport: boolean | 'unknown'
  quotaState?: 'available' | 'limited' | 'exhausted' | 'unknown'
  certification: 'uncertified' | 'certified' | 'degraded'
  observedAt: string
}
```

Unknown capabilities remain unknown.

## 10.7 Claude transport preference

Preferred order when certified:

```text
1. Claude Design MCP structured transport with brokered OAuth
2. certified Claude Code WorkerSession exposing `/design` capability
3. no Claude design capability → WAITING_FOR_DESIGN_CAPABILITY
```

Do not implement "type slash command into terminal" as a permanent transport. A temporary compatibility shim requires its own certification and must never be represented as equivalent to a structured provider API.

## 10.8 DesignEditContext

Send the minimum context necessary:

```ts
interface DesignEditContext {
  projectId: string
  missionId?: string
  designSessionId: string
  intent: string
  targetNodeIds: string[]
  screenId: string
  viewport: ViewportSpec
  frontendContractRefs: string[]
  pxgSliceHash: string
  designConstitutionVersion: string
  designSystemSnapshotId: string
  designSystemHash: string
  effectiveLocks: EffectiveLock[]
  preserveRefs: string[]
  allowedSourceRefs: string[]
  candidateRef?: string
  screenshotRefs?: string[]
  contentPolicy: ProviderContextPolicy
}
```

Never send the entire repository merely because it is convenient.

## 10.9 Shared chat semantics

Frontend Chat and Claude `/design` share:

```text
FrontendConversation
  └── DesignSession
       ├── turns
       ├── selected references
       ├── DesignArtifacts
       ├── candidate refs
       ├── source refs
       ├── mutation plans
       └── decisions
```

Examples:

> "Take the hero from Template C and ask /design for three variants, but keep the locked nav and our search."

The intent router resolves this to:

```text
source reference: Template C hero
preserve: nav, search
locks: effective current screen locks
provider capability: Claude /design
outputs: 3 DesignArtifacts
accepted design: untouched
```

> "Make the selected gap one step tighter."

This remains a deterministic token mutation and does **not** call Claude Design.

## 10.10 Design system sync

DDE owns the design system. Sync is an outbound derived snapshot.

```text
DDE Project Design System
  ↓ compile allowlisted bundle
DesignSystemSnapshot(id, hash, version)
  ↓ provider sync
ProviderDesignSystemLink(provider_id, external_id, source_hash, synced_at)
```

Rules:

- project tokens/components/locks remain authoritative in DDE;
- provider edits do not back-write design-system truth automatically;
- hash change marks provider link `STALE_SYNC`;
- button can prompt "Sync required" before design generation when policy demands consistency;
- provider link/identity is recorded in DesignArtifact provenance;
- design-system sync can be performed from Source mode or the `/design` dropdown;
- synced bundle is minimized to relevant package/directory for large repos.

## 10.11 DesignArtifact lifecycle

```text
REQUESTED
→ GENERATING
→ GENERATED
→ REVIEWED
→ TRY_LIVE_REQUESTED
→ IMPLEMENTING
→ LIVE
→ VERIFIED
→ PROMOTED
or DISCARDED / SUPERSEDED / FAILED
```

A generated artboard is `GENERATED`, not implemented.

## 10.12 Try live

```text
DesignArtifact
  ↓ implementation packet
Manager/Orchestrator selects eligible implementation worker
  ↓
isolated LiveEditWorkspace/worktree
  ↓
project-native code implementation
  ↓
build + real preview
  ↓
LIVE
```

Implementation worker identity may differ from design provider. Claude Design is not automatically allowed to mutate source merely because it created the design.

## 10.13 Direct manipulation after `/design`

If the provider artifact is editable externally, DDE may expose "Open in Claude Design". DDE still treats the returned updated artifact as a new `DesignArtifactVersion`. Within DDE's live candidate canvas, direct manipulation produces normal FrontendMutation operations against the candidate code/PXG.

No two-way provider sync path may overwrite accepted DDE state without a new version and acceptance gate.

## 10.14 Provider failure

Typed outcomes:

```text
AUTH_REQUIRED
CAPABILITY_UNAVAILABLE
PROVIDER_UNREACHABLE
RATE_LIMITED
QUOTA_EXHAUSTED
CONTEXT_REJECTED
DESIGN_SYSTEM_SYNC_REQUIRED
ARTIFACT_FETCH_FAILED
PROVIDER_VERSION_UNCERTIFIED
```

If another design provider is certified and project policy permits, the Manager can route to it. The UI must disclose the provider change in provenance. Otherwise the design request remains blocked/waiting.

---

# 11. TEMPLATE & DESIGN SOURCE INTELLIGENCE

## 11.1 Project foundation selection is now a first-class phase

Projects should no longer be forced into "donor repo = design law." At frontend intake:

```text
Project scope + personas + archetypes + platform + brand + constraints
  ↓
Frontend Contract/PXG seed
  ↓
Template Recommendation Query
  ↓ parallel governed sources
project library / org library / DDE library / 21st / donors / mobile registries
  ↓
normalized FoundationCandidate[]
  ↓
compatibility + coverage + design-fit + license/security scoring
  ↓
Direction board
  ↓
user/manager selects, blends, or rejects
  ↓
DesignConstitution + FoundationLock
```

## 11.2 FoundationCandidate

```ts
interface FoundationCandidate {
  id: string
  sourceRefs: string[]
  templateRef?: string
  supportedArchetypes: string[]
  expectedScreenCoverage: CoverageEstimate
  designFit: ScoreWithEvidence
  architectureFit: ScoreWithEvidence
  responsiveFit: ScoreWithEvidence
  accessibilityFit: ScoreWithEvidence
  adaptationCost: Estimate
  dependencyRisk: RiskAssessment
  licenseAssessment: LicenseAssessment
  sourceHealth: SourceHealth
  previewArtifactRefs: string[]
  hardFailures: string[]
}
```

A hard failure cannot be averaged away by an overall score.

## 11.3 21st adapter

21st is treated as a high-value web registry/provider, not as a dependency that owns DDE UI.

```text
DesignSourceAdapter
└── TwentyFirstAdapter
     ├── capabilities/health
     ├── semantic search
     ├── inspect code/dependencies
     ├── retrieve candidate
     ├── capture author/source/license metadata
     ├── capture theme/template/component structure
     └── hand artifact to Design System Compiler
```

Rules:

- internal/project component search precedes external search by default;
- no `21st install`/MCP code lands directly on accepted project branch;
- source results may be shown as previews before code retrieval;
- exact external usage limits/credits are provider state, not architectural constants;
- provider outage marks source coverage degraded;
- source content is versioned/hashed at retrieval.

## 11.4 Donor sources

A donor can contribute:

```text
navigation = HARD
information architecture = STRONG
motion = INSPIRATION_ONLY
color system = FORBIDDEN
component X = COMPONENT_DONOR
```

The user can explicitly elevate a donor to global design law, but this is never inferred from the mere act of adding the repo.

## 11.5 1Code treatment

The 21st.dev 1Code open-source project is an **architecture donor**, not a runtime dependency. Reuse concepts such as:

- per-chat/per-candidate worktrees;
- live previews;
- diffs;
- rollback;
- task/session visualization;
- agent status;

Do not bind DDE's durability, orchestration or frontend runtime to the archived 1Code repository.

## 11.6 Mobile sources

For React Native/Expo targets:

```text
BNA UI adapter
Gluestack adapter
React Native Reusables adapter
DDE mobile library
approved mobile donors
```

Every source artifact still passes the same provenance/compiler gate.

## 11.7 Expo runtime verification

Expo MCP/device tooling belongs to execution/validation rather than source design authority.

```text
mobile candidate
→ SDK/version check
→ build/run simulator/device
→ screenshot
→ component hierarchy inspection
→ tap/type/gesture flow
→ logs/network/performance
→ accessibility/touch checks
→ evidence
```

No mobile candidate reaches `VERIFIED` based only on a web preview.

---

# 12. DESIGN SYSTEM COMPILER — TARGET-AWARE NORMALIZATION

Rev 2's compiler is hardened with target-stack awareness.

```text
SourceArtifact
  ↓
license/provenance/security admission
  ↓
parse source/AST/registry metadata
  ↓
semantic component decomposition
  ↓
resolve target project's FrontendContract.stack
  ↓
map primitives/tokens/behavior
  ↓
normalize dependencies
  ↓
normalize accessibility
  ↓
normalize responsive semantics
  ↓
isolate data/events
  ↓
generate adapted component in candidate workspace
  ↓
build/test/visual comparison
  ↓
CompilerReport
```

Possible dispositions:

```text
REUSE_NATIVE
ADAPT_SAFE
ADAPT_WITH_DEBT
REQUIRES_PROJECT_DEPENDENCY
REQUIRES_DESIGN_TOKEN_EXTENSION
REJECT_LICENSE
REJECT_SECURITY
REJECT_ARCHITECTURE
REJECT_ACCESSIBILITY_COST
REJECT_UNSUPPORTED
```

---

# 13. PROJECT EXPERIENCE TEMPLATE — QUANTUM COMPLETENESS COMPILER

Rev 2 defines the DDE Comprehensive Product Experience Template. Rev 3 adds how it is operationalized so "Dial depth and breadth" becomes executable rather than a checklist.

## 13.1 Archetype composition

A project is compiled as a set of applicable archetypes:

```text
ProjectExperienceTemplateInstance
  = Authentication
  + Organisation
  + Marketplace
  + Commerce
  + Payments
  + Logistics
  + AssetManagement
  + Services
  + Messaging
  + Notifications
  + Analytics
  + Administration
  + ... project-specific branches
```

Each branch is explicitly:

```text
REQUIRED
OPTIONAL_SELECTED
DEFERRED_APPROVED
NOT_APPLICABLE_APPROVED
BLOCKED_RECORDED
```

There is no silent omission state.

## 13.2 Atomic feature expansion algorithm

For each scoped requirement:

```text
Requirement
→ feature semantic class
→ affected personas/roles
→ affected surfaces/platforms
→ entry points
→ journeys/transitions
→ route/screen obligations
→ region/component obligations
→ interaction commands
→ data read/write contracts
→ permission states
→ loading/empty/error/offline/degraded states
→ responsive/platform variants
→ accessibility obligations
→ analytics/telemetry
→ notification/deep-link implications
→ security/privacy constraints
→ acceptance tests
→ visual/interaction evidence obligations
→ coverage nodes
```

The compiler may propose obligations but only explicit applicability/authority can remove them.

## 13.3 Feature Coverage Pack

Every non-trivial feature gets a machine-readable pack:

```yaml
feature_id:
requirement_refs: []
personas: []
surfaces: []
entry_points: []
journeys: []
routes: []
screens: []
regions: []
components: []
states: []
interactions: []
data_reads: []
data_writes: []
permissions: []
responsive_variants: []
a11y: []
analytics: []
notifications: []
security_privacy: []
acceptance_criteria: []
verification_obligations: []
implementation_refs: []
coverage_state:
```

## 13.4 Completeness gates

A feature cannot become `VERIFIED` if any required pack field has unresolved applicable obligations. "Implemented screen exists" is never sufficient.

## 13.5 Screen thinness detector

Flag a suspicious screen when any applies:

- feature has multiple required states but screen only implements happy path;
- interactions exist in requirement but no command/action contract;
- role permissions exist but no denied/conditional UI state;
- live/realtime feature has no reconnect/stale behavior;
- list/table feature has no empty/loading/error/pagination/large-data treatment where applicable;
- mobile target exists but no mobile variant/gesture/keyboard/safe-area evidence;
- critical destructive workflow lacks confirmation/recovery;
- backend data contract exists but UI uses placeholder/static values;
- route exists with no journey entry/exit;
- analytics/notification obligations are absent without explicit N/A.

These become Coverage findings, not model prose.

---

# 14. UNIFIED FRONTEND CONVERSATION & INTENT ROUTER

## 14.1 FrontendConversation entity

```ts
interface FrontendConversation {
  id: string
  projectId: string
  missionId?: string
  designSessionId?: string
  activeCandidateId?: string
  selectedNodeIds: string[]
  viewport: ViewportSpec
  turns: FrontendConversationTurn[]
  referencedSourceIds: string[]
  mutationIds: string[]
  decisionIds: string[]
  createdAt: string
  updatedAt: string
}
```

## 14.2 Intent classes

```text
EXPLAIN
INSPECT
SEARCH_SOURCE
COMPARE_SOURCE
DESIGN_DIVERGENT
DESIGN_REFINE
MUTATE_DETERMINISTIC
MUTATE_STRUCTURAL
LOCK_CHANGE
COVERAGE_QUERY
QA_QUERY
VERIFY
UNDO_REVERT
PROMOTE
```

## 14.3 Intent routing

```text
chat turn
  ↓ reference resolution
  ↓ authority/lock/coverage context
  ↓ intent classification
  ├─ read-only → read/query service
  ├─ deterministic → MutationPlanner
  ├─ design-class → DesignGateway
  ├─ source search → DesignSourceRegistry
  └─ verification → Verification service
```

Provider choice is a routing decision, not encoded in ordinary chat components.

## 14.4 Context chips

The UI may show compact removable scope chips above/in the composer:

```text
[Hero Section 🔒] [Current: Desktop 1440] [Candidate B] [Claude /design]
```

These are concrete references. Removing a chip changes the planned scope before submission, not historical evidence.

---

# 15. UNIFIED MUTATION AND LOCK ENGINE — LIVE EDITING

## 15.1 One operation protocol

Rev 2 operations remain authoritative (`ADD`, `MOVE`, `REPLACE`, `RESTYLE`, etc.). Rev 3 adds source/candidate revision preconditions:

```ts
interface MutationPrecondition {
  authoritativeDesignRevision: string
  candidateRevision?: string
  pxgRevision: string
  frontendContractVersion: string
  designSystemHash: string
  effectiveLockHash: string
}
```

A stale precondition produces `CONFLICT_REPLAN_REQUIRED`, never blind application.

## 15.2 Deterministic inspector property descriptors

Inspector fields are generated from project/component descriptors:

```ts
interface EditablePropertyDescriptor {
  propertyId: string
  label: string
  group: 'layout' | 'style' | 'behavior' | 'data' | 'responsive'
  valueKind: 'token' | 'enum' | 'boolean' | 'number' | 'reference' | 'object'
  allowedValues?: unknown[]
  tokenNamespace?: string
  lockScope: string
  mutationOperation: string
  validationRuleIds: string[]
}
```

This lets the exact golden inspector remain usable across different target stacks without hardcoding CSS writes.

## 15.3 Undo/revert

Every applied candidate mutation records inverse/rollback information. User-visible undo can revert within the candidate. Reverting an accepted/promoted historical change creates a new compensating revision; it does not rewrite audit history.

---

# 16. CANDIDATE, WORKTREE AND LIVE-EDIT ARCHITECTURE

## 16.1 Accepted vs working state

```text
AcceptedDesignRevision (immutable reference)
  │
  ├─ Direction A candidate/worktree
  ├─ Direction B candidate/worktree
  └─ Working candidate/worktree
```

Even when the user is "editing the current design," the mutable working state is an isolated candidate based on the accepted revision. Promotion creates the next accepted revision.

## 16.2 Candidate creation triggers

- Claude `/design` artifact → Try live;
- template fragment blend;
- 21st component adaptation;
- direct multi-step structural edit;
- worker implementation packet;
- significant responsive adaptation;
- repair cycle from visual verification.

Small deterministic edits may reuse an active Working candidate rather than creating a new branch per keystroke.

## 16.3 Worktree ownership

Each candidate record includes manager/packet ownership so two workers cannot mutate the same files simultaneously without an explicit coordination mode.

## 16.4 Staleness

If accepted base changes:

```text
candidate.base_revision != accepted.revision
→ candidate = STALE
→ compute rebase impact
→ re-run lock/coverage/provenance validation
```

No stale candidate may promote blindly.

---

# 17. CANDIDATE SCORING AND DIRECTION BOARD HONESTY

## 17.1 Score components

Candidate scorecards may aggregate:

- functional coverage;
- design-constitution fit;
- visual contract/deterministic QA;
- accessibility;
- responsive coverage;
- architecture compatibility;
- dependency/security/license risk;
- adaptation debt;
- independent VLM critique once DDE-068 exists;
- user/manager preference signal where explicitly recorded.

## 17.2 Prohibited scoring

- implementer self-rating as evidence;
- hardcoded 84/76/92 values;
- model confidence treated as visual quality;
- averaging a hard license/security failure into a pass;
- displaying a precise percentage before the score dimensions are actually available.

Before DDE-068/required evidence, candidate cards display `Not scored`, partial dimensions, or a clearly labeled compatibility estimate.

---

# 18. SOURCE BLEND, PROVENANCE AND LICENSE CONTROL

## 18.1 Node-level attribution

A selected region's source attribution derives from its component/PXG nodes:

```text
node 1 → project native
node 2 → Template C artifact
node 3 → DDE Library navigation
...
```

An attribution percentage may be based on node/component ownership or a documented weighted structural measure. The algorithm is versioned and visible.

## 18.2 Target blend weights

The Source Blend slider is a **generation preference**, not a factual claim. It can guide the next design request:

```ts
interface SourceBlendTarget {
  sourceRef: string
  weight: number
  preserveCharacteristics: string[]
  forbiddenCharacteristics: string[]
}
```

## 18.3 License gate

External source code with unknown/incompatible licensing cannot promote. Visual inspiration without code reuse still records reference provenance but follows the project's legal policy rather than pretending source-free generation.

---

# 19. MANAGER/ORCHESTRATOR — FRONTEND PROGRAMME OWNERSHIP

## 19.1 FrontendProgram

```ts
interface FrontendProgram {
  projectId: string
  managerRoleRef: string
  designDirectorRoleRef?: string
  frontendContractVersion: string
  pxgRevision: string
  acceptedDesignRevision: string
  currentMilestone: FrontendMilestone
  activeDesignSessions: string[]
  activeCandidateIds: string[]
  blockedCoverageNodeIds: string[]
  pendingAcceptanceIds: string[]
}
```

## 19.2 Design Director

Design Director can be:

- the Manager operating in design mode; or
- a delegated eligible strategic design role reporting to the Manager.

It cannot own project truth, mutate accepted scope autonomously or become a second orchestrator.

## 19.3 Manager Chair card truth

The golden card should be able to show, compactly:

```text
Manager Chair
Desired: GPT Sol
Configured: GPT Sol
Serving: unknown   (when not attested)
OCL: 1 CONFIGURED
Design Director: active
```

or an equivalent terse representation. Never compress desired/configured into "Serving" without evidence.

## 19.4 Delegation

Manager-grade work:

- interpreting frontend scope;
- choosing/locking design direction;
- reconciling cross-feature architecture;
- deciding hard source conflicts;
- approving deferrals;
- final promotion/acceptance.

Worker-grade bounded work:

- source search;
- template inspection;
- compilation/adaptation;
- screenshot gathering;
- deterministic QA;
- bounded implementation packets;
- candidate builds;
- report generation.

---

# 20. DDE-068 VISUAL VERIFICATION AS FRONTEND STUDIO'S QUALITY BACKPLANE

The golden QA/Verify features depend on DDE-068. Rev 3 integrates rather than duplicates it.

## 20.1 Verification request

```text
Candidate/Accepted revision
+ VisualContract
+ required screens/states/breakpoints
+ ProductEnvironment fixture plan
→ VerificationRun
```

## 20.2 Evidence shown in QA mode

- screenshots by breakpoint/state;
- DOM/layout geometry;
- accessibility findings;
- overflow/clipping/truncation;
- token conformance;
- density/silhouette findings;
- reduced-motion proof;
- interaction traces;
- independent critique;
- repair history;
- final gate state.

## 20.3 Accessibility badge

The Inspector may show `AA · No issues` only when a current valid evidence set covers that node/screen and target. Otherwise show:

- `Not evaluated`;
- `3 findings`;
- `Evidence stale`;
- or equivalent truthful state.

## 20.4 Pixel signoff

Pixel signoff becomes an admitted approval type only through DDE-068 change control. It cannot waive functional, accessibility-hard, security, missing-state or off-token failures.

---

# 21. COVERAGE MODE — NO SILENT OMISSION

## 21.1 Coverage summary

The top-right coverage ring is a weighted summary, while Coverage mode shows dimensions:

```text
Requirements       100%
Journeys            96%
Screens             94%
States               82%
Data binding         91%
Permissions         100%
Responsive           88%
Accessibility        79%
Analytics            73%
QA                   68%
Visual regression    64%
```

Numbers shown here are illustrative schema examples only; production values must be real.

## 21.2 Coverage blockers

Coverage mode groups:

- missing;
- regressed;
- blocked;
- deferred approved;
- not applicable approved;
- stale evidence;
- orphan code;
- orphan requirement.

## 21.3 Chat integration

User can ask:

> "What frontend is still missing for supplier promotions?"

The answer is generated from Frontend Contract/PXG/Coverage nodes and can produce a bounded implementation plan, not from model memory.

---

# 22. ARCHITECTURE MODE

Architecture mode makes the semantic and implementation structure inspectable:

- PXG graph/tree;
- route/screen topology;
- component relationships;
- data bindings;
- permission edges;
- source/provenance overlays;
- code file mapping;
- dependency graph;
- candidate delta;
- orphan/divergence findings.

It is not a decorative graph. Every visible node maps to real project records/source.

---

# 23. SOURCE MODE

Source mode unifies:

- DDE/project component libraries;
- 21st and approved web registries;
- donor repositories/artifacts;
- templates/foundations;
- mobile registries;
- Figma/design files when connected;
- Claude Design system sync status;
- source health/auth;
- license/provenance/security reports;
- bookmarks/private libraries;
- imported/adapted components.

Search result states must expose provider coverage: `COMPLETE_FOR_ENABLED_SOURCES`, `DEGRADED_PROVIDER_UNAVAILABLE`, `AUTH_REQUIRED`, etc.

---

# 24. QA MODE

QA mode is the operational surface for:

- functional tests;
- visual regression;
- DDE-068 render evidence;
- accessibility;
- responsive/device matrix;
- performance budgets;
- security/privacy UI checks;
- source/dependency risk;
- candidate acceptance gates;
- stale evidence;
- repair cycles;
- baseline governance.

A baseline-update action requires rationale and authority; it is not a "make test green" button.

---

# 25. AUTO LAYOUT & AI SUGGEST

## 25.1 Auto Layout

`Auto Layout: ON` means the editor will preserve configured layout constraints while applying deterministic direct-manipulation edits. It may:

- snap to token spacing/grid;
- maintain parent layout rules;
- propose legal drop positions;
- prevent impossible/forbidden placement;
- create an explicit mutation plan.

It may not silently redesign unrelated regions.

## 25.2 AI Suggest

`AI Suggest: ON` means passive design/quality suggestions can be generated according to policy. Suggestions are:

- non-authoritative;
- inspectable;
- dismissible;
- source/provider attributed;
- never auto-applied to accepted design;
- rate/quota aware where observable.

---

# 26. CROSS-DDE SHELL FUNCTIONALIZATION

The locked Frontend Studio image is the visual constitution for all DDE windows. Every module plugs into the same shell primitives, but its content is domain-specific.

## 26.1 Module manifest

```ts
interface DdeModuleManifest {
  id: string
  title: string
  railIcon: string
  leftNavGroups: NavGroupDescriptor[]
  workspaceModes: WorkspaceModeDescriptor[]
  inspectorContexts: InspectorContextDescriptor[]
  statusSignals: StatusSignalDescriptor[]
  attentionSources: AttentionSourceDescriptor[]
  commands: CommandDescriptor[]
  readCapabilities: ReadCapabilityDescriptor[]
}
```

## 26.2 Shared components

No DDE module recreates:

- top bar;
- rail;
- context sidebar shell;
- inspector shell;
- tab grammar;
- status bar;
- badges;
- fields;
- menus;
- dialogs;
- tree/list components;
- resizable panels;
- attention center;
- toast/error patterns.

## 26.3 Migration law

A module is migrated only when:

- it visually conforms;
- all its existing functions still work;
- its new visible controls are real;
- keyboard/accessibility behavior passes;
- no legacy parallel design system remains without an approved temporary exception.

---

# 27. DATA MODEL ADDITIONS/HARDENING

Rev 2 entities remain. Add/clarify:

```text
AcceptedDesignRevision
WorkingDesignRevision
FrontendConversation
FrontendConversationTurn
DesignSystemSnapshot
ProviderDesignSystemLink
DesignProviderCapabilitySnapshot
DesignProviderAuthState
DesignComment
DesignCommentAnchor
TemplateRecommendationRun
FoundationCandidate
FoundationLock
SourceBlendTarget
SourceAttribution
FrontendReadProjectionRevision
StudioSyncStateRecord (if server persistence is useful; otherwise derived client state)
PreviewInstrumentationSession
PreviewSelectionAnchor
AttentionItem
```

## 27.1 Append-only history

Append-only/auditable:

- accepted design revisions;
- lock changes;
- source imports/provenance;
- provider context hashes;
- candidate promotions/rejections;
- design decisions;
- comments/resolution events where governance requires;
- visual baseline changes;
- scope deferrals/not-applicable approvals.

---

# 28. SECURITY, EGRESS AND PROVIDER PRIVACY

## 28.1 Provider context policy

Before any Claude Design/21st/other external provider call:

```text
resolve project/provider policy
→ determine allowed files/nodes/assets
→ strip credentials/secrets/private user data
→ minimize to requested scope
→ hash manifest/context
→ log provider + purpose + artifact lineage
→ execute through admitted adapter/capability
```

## 28.2 OAuth/credentials

- frontend UI never stores raw provider credentials;
- OAuth/token material is handled by the existing/new Credential Broker or certified host provider mechanism;
- UI receives auth state/fingerprint/expiry metadata only as permitted;
- external MCP connection state is not equivalent to project authorization to export all source.

## 28.3 Screenshots

Preview/verification screenshots may contain sensitive project data. Use deterministic fixtures by default and redact/avoid production secrets or personal data. Evidence storage follows project retention/privacy policy.

---

# 29. PERFORMANCE & LARGE-PROJECT ENGINEERING

Target architecture assumes thousands of PXG nodes and hundreds of screens/components.

Required:

- virtualized explorer trees and candidate/source lists;
- lazy route/screen graph loading;
- incremental Coverage recomputation;
- memoized inspector descriptors;
- off-main-thread/worker computation where suitable;
- streamed provider/source results;
- cancellable searches/design requests/builds;
- preview process isolation;
- debounce/coalesce high-frequency direct-manipulation events;
- bounded screenshot/evidence caching;
- source index freshness metadata;
- candidate cleanup/retention policy;
- no UI freeze while agents/providers run.

Performance budgets are measured on representative large projects before final hardening.

---

# 30. FAILURE & RECOVERY MATRIX

| Failure | Required behavior |
|---|---|
| Gateway unavailable | editor enters offline/stale; accepted state preserved; local draft not claimed durable |
| event stream unavailable | explicit polling fallback/degraded status |
| Claude auth expired | `/design` button AUTH_REQUIRED; current candidate remains intact |
| Claude /design unavailable | typed waiting/block or certified alternate provider |
| 21st unavailable | other sources continue; source search marked degraded |
| source license unknown | candidate may preview if policy permits, cannot promote code |
| candidate build failure | show build evidence/log; accepted design untouched |
| preview crashes | restart isolated runtime; candidate/worktree retained |
| worktree dirty/conflicted | block promote; reconcile/repair flow |
| accepted base changes | candidate stale → rebase/revalidate |
| PXG/source divergence | explicit reconciliation finding; neither side blindly wins |
| lock hash changed | mutation becomes stale/conflict; replan |
| provider returns malformed artifact | quarantine/reject; record provider failure |
| DDE-068 unavailable | verification blocked; no VERIFIED/pixel signoff |
| Manager session interruption | persist FrontendProgram/packets/candidates; resume from recorded evidence |
| model serving identity unknown | UI states unknown; no model-specific authority claim |

---

# 31. MIGRATION FROM CURRENT DDE-067 — NO-BIG-BANG PLAN

## M0 — Adoption and truth reconciliation

Deliver:

- commit this document under the agreed `docs/truth` or domain-canonical path;
- update global Blueprint/Dev Plan references rather than creating a hidden competing SOT;
- correct DDE-069 projection drift in `IMPLEMENTATION_STATE.md`;
- record golden visual authority and older visual-directive supersession in `ARCHITECTURE_DECISIONS.md`;
- update `RESUME_PROMPT.md` pointer;
- preserve historic DDE-067 chapter gate as evidence.

Gate: truth files agree on current reality and next mission ordering.

**Status (2026-09-04): M0 complete.** This document is committed at `docs/truth/FRONTEND_STUDIO_REV3.md`; `ARCHITECTURE_DECISIONS.md` AD-030/AD-035/AD-036, `IMPLEMENTATION_STATE.md`'s DDE-069 section, `DEV_PLAN_REV3.md` §6, and `RESUME_PROMPT.md` all point to each other consistently. M1 onward have not started.

## M1 — Characterize and freeze DDE-067 invariants

Add/retain focused tests proving:

- command ledger/idempotency;
- donor approval scope;
- token rejection;
- workspace scoping;
- no fabricated client data;
- current commands still work.

Gate: migration can detect safety regressions.

## M2 — DDE-068 quality backplane

Implement/close required real visual verification slices per canonical DEV_PLAN.

Gate: real fixture can render → deterministic QA → critique/repair → evidence → pass.

## M3 — UI runtime and host bridge

Admit React/Vite and create the host-neutral runtime. Keep existing string renderers operational until replacement surface passes tests.

Gate: React shell can read real project/session state through `DdeHostBridge` in VS Code, Electron and tests.

## M4 — Golden shell

Implement exact shell geometry/tokens/primitives and visual-regression baseline.

Gate: canonical 1672×941 shell perceptually matches golden reference within approved tolerance; no screenshot-background trick.

## M5 — Read projections and event synchronization

Implement the data required to populate counts, source inventories, locks, QA, coverage, manager status, candidates and sync truth.

Gate: all visible high-level dashboard values are real or explicitly unavailable.

## M6 — PXG / Contract / Product Experience Template / Coverage

Implement Rev 2 semantic systems and import/reconcile existing project state.

Gate: requirement → screen/state/test trace is inspectable; no silent omission.

## M7 — Mutation / lock / live candidate runtime

Wrap existing DDE-067 edit capabilities under the new mutation planner and isolated candidate model.

Gate: drag/drop + inspector edits + rollback use real Gateway commands and cannot bypass locks.

## M8 — Source intelligence

Implement internal sources, donors, 21st adapter, template recommendations, compiler and provenance.

Gate: external artifact can be searched → inspected → sandbox-adapted → validated without accepted production mutation.

## M9 — Frontend Chat

Implement shared conversational control with reference resolution and deterministic-vs-design intent routing.

Gate: chat can inspect, mutate a candidate, query coverage and search sources using typed paths.

## M10 — Claude `/design`

Implement DesignGateway, DesignSession, DesignEditContext, DesignSystemSnapshot sync, provider status and toolbar button.

Gate vertical slice:

```text
select Hero
→ click Claude /design
→ same chat/design session opens
→ context + locks + system hash recorded
→ 3 DesignArtifacts returned
→ Direction cards appear
→ choose Direction B
→ Try live
→ isolated implementation workspace
→ real preview LIVE
→ chat refines same candidate
→ DDE-068 verify
→ promote exact design/code pair
```

## M11 — Golden functional binding closure

Complete every row in Part 8 with a real capability and automated acceptance.

Gate: no decorative visible feature remains.

## M12 — Cross-DDE migration

Move Models, Orchestration, Agents, RAG, Settings and other first-party windows to the shared shell without losing behavior.

Gate: visual + functional cross-module acceptance.

## M13 — Mobile adapters and full cross-platform validation

When project scope requires mobile, enable source adapters and Expo/device validation using the same PXG/Contract/candidate architecture.

## M14 — hardening

- large project benchmarks;
- failure injection;
- provider outage/auth expiry;
- event loss;
- candidate conflict;
- visual baseline governance;
- accessibility;
- security/privacy;
- migration cleanup/removal of legacy UI only after proof.

---

# 32. TEST ARCHITECTURE

## 32.1 Unit/contract

- schemas/serialization;
- typed command generation;
- mutation planning;
- lock conflict precedence;
- coverage propagation;
- source scoring/hard rejection;
- provider capability interpretation;
- sync-state transitions;
- inspector descriptors;
- design context minimization;
- provenance attribution.

## 32.2 Integration

- UI bridge → Gateway command acceptance → durable result projection;
- DDE-067 compatibility commands;
- candidate worktree lifecycle;
- DesignGateway fake provider contract;
- 21st adapter fake/recorded provider response;
- source compiler target-stack adaptation;
- event stream and polling fallback;
- auth expiry/re-auth state;
- PXG/source reconciliation.

## 32.3 End-to-end

- entire golden functional binding map;
- chat template blend;
- Claude `/design` vertical slice using certified/fake provider in CI and live provider certification separately;
- candidate compare/promote;
- lock conflict;
- missing coverage discovery;
- stale candidate rebase;
- saved/synced semantics;
- accessibility/keyboard;
- multi-viewport;
- DDE-068 render verification;
- cross-host VS Code/Electron smoke.

## 32.4 Visual regression

- golden 1672×941 Frontend Studio shell;
- light canonical theme;
- dark parity theme;
- 1440/1280/1024 supported layouts;
- inspector/explorer collapsed states;
- candidate dock states;
- `/design` auth/loading/results/error states;
- long text/localization resilience;
- high/low density project fixtures.

---

# 33. GOLDEN MOCKUP ACCEPTANCE CHECKLIST

A release candidate fails if any answer is "no" without an explicit approved deferral:

### Shell
- Does the production screen immediately look like the approved mockup?
- Are dimensions/density/typography/borders/spacing calibrated by screenshot evidence?
- Is the DDE shell shared rather than copied?

### Real state
- Are project name, counts, coverage, locks, QA, manager status, candidate status and sync real?
- Do unknown values remain unknown?

### Canvas
- Is the central view a real code-backed preview?
- Do selection/resize/locks map to stable project nodes?
- Do direct edits route through mutations and candidate isolation?

### Chat
- Is the composer a persistent frontend-scoped conversation?
- Does it resolve selected nodes/candidates/templates/locks?
- Can it choose deterministic actions without wasting an AI design call?

### Claude /design
- Is the toolbar button visible and easy to use?
- Does it share the chat/design session?
- Is provider capability/auth/version truthful?
- Is the design-system hash synced/governed?
- Do outputs become versioned DesignArtifacts, not direct production edits?
- Does Try live create a real isolated code candidate?

### Sources/templates
- Can Frontend Studio recommend foundations/templates rather than only accept donor law?
- Are 21st and other sources adapter-governed?
- Are licenses/provenance/dependencies/security inspected?

### Completeness
- Does Product Experience Template + Frontend Contract + PXG expose missing pages/features/states?
- Can no required obligation silently disappear?

### QA
- Is DDE-068 real and consumed by promotion?
- Are accessibility/responsive/visual findings evidence-backed?

### Manager
- Does the Project Manager own final frontend outcome?
- Are worker boundaries enforced?
- Is serving-model identity never overclaimed?

---

# 34. REV 3 CANONICAL DECISION REGISTER

**FS-R3-001 — Golden visual supersession**
The user-approved light-first 1672×941 Frontend Studio mockup is the canonical DDE visual baseline and supersedes conflicting older Frontend Studio visual-direction prose.

**FS-R3-002 — DDE shell owns its theme**
DDE app chrome uses DDE-owned semantic tokens; host editor themes cannot silently override the golden design.

**FS-R3-003 — React workbench migration**
The six DDE-067 string-template views are preserved as compatibility evidence but migrate to a host-neutral React/TypeScript/Vite workbench after dependency admission.

**FS-R3-004 — Host bridge**
All feature UI uses `DdeHostBridge`; direct VS Code API access is confined to bridge/bootstrap code.

**FS-R3-005 — No fake sync**
`Synced` requires authoritative durable revision reconciliation, not command acceptance.

**FS-R3-006 — Real read models**
All golden counts, lists, QA, locks, coverage, manager state and provider state derive from typed reads or display unavailable honestly.

**FS-R3-007 — Claude `/design` toolbar control**
Frontend Studio contains a first-class `Claude /design` button in the canvas toolbar.

**FS-R3-008 — `/design` is one control plane**
The `/design` button, Frontend Chat and direct editing share the same FrontendConversation/DesignSession/PXG/Contract/mutation/candidate architecture.

**FS-R3-009 — Structured design transport**
DDE prefers certified structured Claude Design MCP/OAuth or certified Claude Code design capability; terminal keystroke automation is not the canonical integration.

**FS-R3-010 — Design-system sync is derived**
DDE remains design-system authority; provider sync is a hashed/versioned outbound snapshot.

**FS-R3-011 — Design artifact != live app**
Claude Design artboards are design artifacts; only built code in a ready preview runtime is `LIVE`.

**FS-R3-012 — Templates before donor lock-in**
At project intake Frontend Studio can recommend foundations/templates from approved sources. Donors are atomic directives unless explicitly promoted to global law.

**FS-R3-013 — 21st source adapter**
21st is a governed external design-source adapter and never writes accepted production directly.

**FS-R3-014 — 1Code concept donor only**
1Code may inform worktree/preview/session UX but is not a production DDE dependency.

**FS-R3-015 — Mobile is first-class**
Mobile uses platform-specific source adapters and runtime/device verification, not resized web.

**FS-R3-016 — DDE shell vs target stack separation**
No Tailwind/shadcn visual layer remains the DDE shell rule; target projects may use their own admitted stack and source compiler mapping.

**FS-R3-017 — Actual Source Blend vs target blend**
Current provenance attribution and desired next-generation source weights are distinct concepts in UI/data.

**FS-R3-018 — Token display vs token write**
Inspector may show computed px for usability; DDE/project semantic token identity remains the write contract unless the Frontend Contract explicitly allows custom values.

**FS-R3-019 — Manager owns frontend programme**
Design Director is subordinate to the Project Manager/Orchestrator; final scope/lock/promotion authority is not delegated to ordinary workers.

**FS-R3-020 — Serving identity honesty**
Manager card distinguishes desired/configured/serving model state and follows ModelServingEvidence/OCL rules.

**FS-R3-021 — DDE-068 remains mandatory**
Frontend Studio V2 cannot be promoted as complete without the real visual verification/critique evidence path.

**FS-R3-022 — Current-vs-working isolation**
Accepted design revision is protected; mutable authoring occurs in a working candidate/LiveEditWorkspace.

**FS-R3-023 — Golden control functionalization**
Every visible mockup control must be software-usable or explicitly unavailable; decorative product theatre is a release failure.

**FS-R3-024 — Product Experience Template is executable completeness law**
Requirement expansion and coverage packs detect thin/missing screens, states, permissions, data, responsive, accessibility and QA obligations.

**FS-R3-025 — Cross-DDE shell migration**
All first-party DDE windows use the canonical shared shell/primitives and retain real functionality.

---

# 35. EXTERNAL PROVIDER CAPABILITY NOTES — NON-AUTHORITATIVE SNAPSHOT

These notes guide adapters but do not replace capability discovery at runtime.

- Claude Design currently supports design-system import, direct canvas editing, handoff/sync with Claude Code, `/design`, `/design-sync`, and a Claude Design MCP/OAuth path. Treat availability/version/plan state as discoverable external capability.
- 21st currently provides a searchable React component/template/theme registry and MCP/agent workflows for search, retrieval, generation and project-aware UI work. DDE still applies its own source/license/compiler gates.
- BNA UI currently exposes Expo/React Native component registry/CLI operations including an MCP server, making it suitable as a mobile source adapter candidate.
- Expo currently offers official agent integrations/MCP capabilities for documentation/EAS and, with local setup, simulator screenshots and automation; use it for mobile execution/validation rather than as project design authority.

Provider details can change without changing DDE Core contracts.

---

# 36. DEFINITION OF DONE — REV 3 TECHNICAL ARCHITECTURE

Frontend Studio Rev 3 is complete only when:

1. the golden screen is reconstructed perceptually and functionally;
2. all high-level UI data is real or explicitly unavailable;
3. the current DDE-067 safety invariants remain green;
4. the new host-neutral workbench runs in supported DDE hosts;
5. Frontend Contract/PXG/Product Experience Template/Coverage are production-backed;
6. one mutation/lock path governs chat, drag/drop, inspector, sources, agents and design providers;
7. accepted design is isolated from exploratory work;
8. 21st/templates/donors/mobile sources are governed adapters;
9. Claude `/design` button works through the same Frontend Chat/DesignSession and produces versioned artifacts/candidates;
10. design-system sync is hashed, scoped and provider-neutral;
11. Try live produces a real code-backed preview;
12. DDE-068 visual verification gates promotion;
13. candidate scores/provenance/source blend are evidence-backed;
14. saved/synced/coverage/manager/provider statuses are truthful;
15. failure/recovery paths are tested;
16. accessibility/keyboard/responsive/performance/security gates pass;
17. all other DDE windows migrate to the same shared shell without functional regression;
18. global Rev 3 truth projections are updated from implementation evidence;
19. no required frontend feature/page/state is silently omitted or thinly implemented;
20. no decorative product control remains in the golden UI.

---

# PART XXVII — CONSOLIDATED REV 2 CANONICAL BODY

The following full Rev 2 document is incorporated into Rev 3 so this file is self-contained. Rev 3 sections above harden the repository integration and take precedence only where they explicitly clarify/supersede a Rev 2 detail. All other Rev 2 rules remain binding.

---

# DDE FRONTEND STUDIO — CANONICAL ARCHITECTURE, PRODUCT EXPERIENCE SYSTEM & IMPLEMENTATION BLUEPRINT REV 2

**Status:** CANONICAL / LOCKED BASELINE WITH EXTENSIBLE IMPLEMENTATION DETAIL
**Authority:** DDE Frontend Studio architecture, product-experience, implementation and cross-DDE visual source of truth
**Supersedes:** DDE Canonical UI System — Rev 1 as a standalone document; Rev 1 is preserved below as the locked Visual Constitution layer
**Golden visual reference:** Approved DDE Frontend Studio mockup, 1672 × 941 px, 2026-09-03
**Quality bar:** Dial depth-and-breadth standard
**Change rule:** Locked decisions and golden visual law may change only through explicit user-approved revision.

---

## Document map

- **Part I:** Locked Visual Constitution (Rev 1, preserved)
- **Part II:** Canonical Architecture
- **Part III:** Product Experience System
- **Part IV:** Design Intelligence, Sources and Templates
- **Part V:** Interaction, Mutation and Locking
- **Part VI:** Candidate Runtime, Worktrees and Preview
- **Part VII:** Provenance, Licensing and Security
- **Part VIII:** Manager/Orchestrator Control
- **Part IX:** QA, Validation and Acceptance
- **Part X:** Failure Recovery and Consistency
- **Part XI:** Persistence and Domain Model
- **Part XII:** API and Event Contracts
- **Part XIII:** Cross-DDE Visual and Functional Migration
- **Part XIV:** Technical Package Architecture
- **Part XV:** Non-Functional Requirements
- **Part XVI:** Implementation Programme
- **Part XVII:** Verification Scenarios
- **Part XVIII:** Definition of Done at Dial Depth and Breadth
- **Part XIX:** Build-Time Guardrails
- **Part XX:** Canonical Decision Register
- **Part XXI:** Immediate Resume Directive

---

# PART I — LOCKED VISUAL CONSTITUTION

The following Rev 1 content is incorporated as the visual constitution. Its golden-reference decisions remain locked. Rev 2 extends it; it does not dilute it.

**Status:** LOCKED DESIGN BASELINE
**Authority:** Canonical visual and interaction source of truth for DDE desktop windows
**Golden reference:** Generated DDE Frontend Studio mockup, 1672 × 941 px, approved 2026-09-03
**Change rule:** Do not alter this baseline except through an explicit user-approved design revision.

---

## 1. Intent

The approved DDE Frontend Studio mockup is the visual constitution for DDE. The production interface must reproduce its layout logic, density, hierarchy, panel treatment, typography, spacing, chrome, interaction grammar and visual tone closely enough that a screenshot of the implemented screen is immediately recognisable as the same product.

This is not a one-screen theme. It is the global DDE product shell and design language. Frontend Studio is the most feature-rich reference implementation; every other DDE window must inherit the same shell, component language and interaction rules.

The implementation target is **perceptual equivalence, not a screenshot background**. All UI must remain semantic, accessible, responsive, testable and functional.

---

## 2. Golden-master frame

Reference viewport: **1672 × 941 px**.

Approximate desktop grid:

- Global top bar: **58 px** high.
- Global bottom status bar: **32–36 px** high.
- Far-left app rail: **44–48 px** wide.
- Primary navigation/explorer panel: **215–225 px** wide.
- Main workspace: fluid, dominant area.
- Right inspector/context panel: **310–325 px** wide.
- Main horizontal gutters: **12–16 px**.
- Standard panel interior padding: **12–16 px**.
- Dense control gap: **6–8 px**.
- Normal component gap: **10–12 px**.
- Section gap: **16–20 px**.

The interface must retain the reference's strong four-zone composition:

1. global rail,
2. contextual project/navigation panel,
3. central work surface,
4. contextual inspector.

Panels may collapse where appropriate, but their default desktop composition must preserve this geometry.

---

## 3. Global visual tokens

### 3.1 Core palette

Use these as the initial implementation tokens; final values should be visually calibrated against screenshot regression tests.

```css
:root {
  --dde-bg: #F7F8FB;
  --dde-surface: #FFFFFF;
  --dde-surface-muted: #F3F5F9;
  --dde-surface-hover: #EEF2FF;
  --dde-border: #E2E5EE;
  --dde-border-strong: #D2D7E5;
  --dde-text: #111827;
  --dde-text-secondary: #5D6473;
  --dde-text-tertiary: #8A91A1;

  --dde-primary: #4F46E5;
  --dde-primary-strong: #4338CA;
  --dde-primary-soft: #EEF2FF;
  --dde-blue: #2563EB;
  --dde-violet: #7C3AED;
  --dde-indigo-deep: #0D1C4F;

  --dde-success: #22C55E;
  --dde-warning: #F59E0B;
  --dde-danger: #EF4444;
  --dde-info: #3B82F6;
}
```

The application chrome is predominantly neutral white/light-grey. Saturated colour is reserved for:

- selected states,
- active modes,
- AI actions,
- status indicators,
- lock states,
- preview content,
- data visualisation,
- deliberate focal emphasis.

Do not flood the global chrome with gradients. The dramatic dark-indigo/violet gradient seen in the reference hero belongs to the **content being designed**, not to the DDE application shell.

### 3.2 Typography

Primary UI family: **Inter** where available, with a system sans-serif fallback.

```css
--dde-font-ui: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
               "Segoe UI", sans-serif;
```

Recommended scale:

- 11 px: metadata, counts, tertiary labels.
- 12 px: compact controls, breadcrumb/status text.
- 13 px: standard navigation and inspector labels.
- 14 px: primary controls and body UI.
- 15–16 px: panel/module headings.
- 18–20 px: workspace heading where needed.

Weights:

- 400 normal secondary text,
- 500 controls and labels,
- 600 headings/selected items,
- 700 only for rare high-emphasis values.

The visual target is crisp and restrained, not oversized SaaS typography.

### 3.3 Radius

```css
--radius-xs: 4px;
--radius-sm: 6px;
--radius-md: 8px;
--radius-lg: 10px;
--radius-xl: 12px;
```

- Small controls: 6–8 px.
- Cards: 8–10 px.
- Chat composer and major floating controls: 10–12 px.
- Pills/badges may use full rounding.

### 3.4 Borders and shadows

Borders do most of the structural work.

```css
--shadow-panel: 0 1px 2px rgba(15, 23, 42, .04),
                0 4px 14px rgba(15, 23, 42, .035);
--shadow-float: 0 8px 24px rgba(15, 23, 42, .08);
```

Avoid heavy cards and exaggerated elevation. The reference relies on fine borders, subtle shadow and whitespace.

---

## 4. Universal DDE shell

Every first-party DDE screen must use the same top-level shell unless a documented fullscreen mode requires otherwise.

```text
┌────────────────────────────────────────────────────────────────────┐
│ GLOBAL TOP BAR                                                     │
├──────┬──────────────────────┬──────────────────────┬────────────────┤
│ APP  │ CONTEXT / NAV        │ MAIN WORKSPACE       │ INSPECTOR /    │
│ RAIL │ PANEL                │                      │ CONTEXT PANEL  │
│      │                      │                      │                │
│      │                      │                      │                │
├──────┴──────────────────────┴──────────────────────┴────────────────┤
│ GLOBAL STATUS / BREADCRUMB BAR                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Global top bar

Must preserve the reference's rhythm:

- DDE/product title at left.
- active project/workspace selector.
- save/sync/runtime status.
- central mode tabs where relevant.
- right-aligned health/coverage/status indicator.
- activity/notification/help/profile controls.

No screen should invent a radically different header.

### Far-left app rail

This is the module switcher, not a second navigation tree.

Characteristics:

- icon-first,
- narrow,
- persistent,
- selected module shown with a soft tinted rounded square,
- settings and collapse controls anchored near bottom.

### Context navigation panel

Changes by DDE module but keeps identical styling:

- title + search/menu row,
- collapsible groups,
- small numeric counters,
- nested items,
- status dots,
- optional bottom contextual card such as Orchestrator/Manager Chair.

### Right context panel

In Frontend Studio it is the Inspector. Elsewhere it can become:

- model details,
- task packet details,
- agent details,
- execution trace,
- integration details,
- project metadata,
- run configuration,
- test evidence.

It must retain the same width, header grammar, sections, dividers and control density.

### Global status bar

Use for:

- breadcrumbs,
- health/error/warning status,
- runtime state,
- active automation/AI state,
- version/build metadata.

It is a persistent low-height diagnostic strip, not a marketing footer.

---

## 5. Frontend Studio canonical composition

Frontend Studio is the reference implementation of the full DDE shell.

### Left explorer groups

Required conceptual groups:

- Screens
- Journeys
- Components
- Sources
  - DDE Library
  - 21st MCP
  - Donor Sources
  - Internal Components
  - mobile registries where applicable
- Templates
- Locks
  - Style Locks
  - Section Locks
  - Component Locks
  - Behaviour Locks
- QA
  - Issues
  - Accessibility
  - Responsive
  - Visual regression

Bottom card:

- Orchestrator state
- current Manager Chair
- frontend Design Director role/state
- activity visualisation
- clear active/paused/error status

### Top workspace mode tabs

Frontend Studio modes are first-class and use one consistent tab bar:

- Design
- Coverage
- Architecture
- QA
- Source

Modes change the central workspace and context panels without navigating to an unrelated page.

### Canvas toolbar

Replicate the compact tool row:

- target viewport selector,
- selection tool,
- hand/pan,
- comment/annotation,
- layout/grid options,
- zoom,
- fullscreen/fit controls.

### Live canvas

The design canvas must:

- render the actual project UI,
- support direct selection,
- show resize/selection handles,
- show lock badges on protected regions,
- preserve realistic app content,
- support desktop/tablet/mobile viewports,
- support overlays for grids, spacing, data binding and state simulation.

### Frontend chat composer

The chat composer is a **permanent first-class surface**, visually matching the approved mockup.

It must understand:

- selected node(s),
- current screen,
- locked state,
- chosen candidate,
- design sources,
- component provenance,
- frontend contract,
- project scope,
- responsive target,
- current worktree/candidate.

It must create planned frontend mutations rather than uncontrolled code edits.

Examples:

- "Blend Template C's hero into this locked page and preserve navigation and typography."
- "Use Candidate B's sidebar but keep the current content hierarchy."
- "Find a better mobile pattern for the selected section."
- "Apply this table treatment to all supplier screens except audit logs."

### Candidate / Directions dock

Keep the bottom candidate strip from the reference as a permanent concept.

Candidate cards contain:

- thumbnail,
- neutral Direction A/B/C identity,
- match/quality score,
- change count,
- warnings if any,
- current/locked status,
- provenance/source blend,
- preview/select/compare controls.

The active production design is explicitly labelled **Current (Locked)** when locked.

### Source Blend

The source-blend panel is part of the canonical design language.

It should show where the selected composition came from, for example:

- 60% Template C / Hero Variant 2,
- 40% DDE Library / Navigation.

This is not a cosmetic percentage. It must be backed by actual component/provenance records.

---

## 6. Locked-design semantics

The visual lock iconography in the mockup becomes functional product semantics.

Supported lock types:

- Global Design Lock
- Screen Lock
- Section Lock
- Component Lock
- Style Lock
- Structure Lock
- Behaviour Lock
- Content Lock
- Token Lock

Locked elements cannot be silently overwritten by:

- drag/drop,
- chat,
- template imports,
- 21st/BNA/gluestack retrieval,
- `/design`,
- autonomous agents,
- refactors.

A requested mutation crossing a lock boundary must be planned and disclosed before execution.

---

## 7. Canonical interaction grammar

### Selection

- blue/indigo selection outline,
- compact square handles,
- contextual lock chip,
- selected node mirrored in Inspector.

### Hover

- quiet surface tint,
- no large motion,
- tooltip after normal delay where icon meaning is not obvious.

### Active / selected

- pale indigo/blue background,
- saturated blue/indigo icon/text,
- stronger border where necessary.

### AI action

- sparkle motif is allowed but should stay subtle,
- primary send/apply actions use the saturated violet/indigo button treatment seen in the mockup,
- never make the entire UI feel "AI themed".

### Destructive action

- red is reserved for genuine destructive or failed states.

### Animation

- 120–180 ms micro-transitions,
- 180–240 ms panel/candidate transitions,
- standard ease-out curves,
- no decorative bouncing,
- reduced-motion support required.

---

## 8. Cross-DDE screen mapping

Every DDE window inherits the canonical shell and visual grammar.

### Projects / Home

Left context panel:

- Projects
- Recent
- Workspaces
- Templates
- Archived

Main workspace:

- project cards/list,
- health/coverage,
- recent activity,
- resume actions.

Right panel:

- selected project summary,
- source-of-truth state,
- manager model,
- current milestone,
- risk/coverage.

### Models

Left context panel:

- All Models
- Manager Eligible
- Worker Eligible
- Harnesses
- Fallbacks
- Policies

Main workspace:

- model catalogue/table/cards,
- role assignment visualisation,
- capability and availability state.

Right panel:

- selected model details,
- harness/auth source,
- manager-chair eligibility,
- worker role rules,
- cost/limits where available,
- health/failover.

### Orchestration

Left context panel:

- Manager Chair
- Active Agents
- Queues
- Delegations
- Policies
- History

Main workspace:

- orchestration graph,
- task lanes,
- delegation packets,
- evidence/verification state.

Right panel:

- selected agent/task execution detail.

### Agents / Runs

Main area uses the same high-density panel language for:

- task packets,
- live output,
- diffs,
- validation,
- artifacts,
- approvals.

### RAG / Knowledge

Use the same shell for:

- sources,
- collections,
- indexes,
- retrieval tests,
- citations,
- provenance,
- freshness/health.

### Settings

Do not fall back to a generic settings page unrelated to the rest of DDE. Preserve:

- shell,
- rail,
- contextual left nav,
- compact inspector/detail pattern,
- identical typography and controls.

---

## 9. Responsive rules

DDE is desktop-first but must degrade deliberately.

### ≥ 1440 px

Reference layout visible in full.

### 1180–1439 px

- narrow inspector slightly,
- allow collapsible context panel,
- keep canvas dominant.

### 900–1179 px

- inspector becomes overlay/drawer,
- left context panel collapsible,
- top modes may compress but remain visible.

### < 900 px

Companion/monitoring mode only unless explicitly supporting full editing.

Do not destroy the product's information architecture simply to fit a narrow viewport.

---

## 10. Implementation architecture

All DDE windows must consume shared primitives rather than copy CSS.

Recommended conceptual packages:

```text
packages/ui/
  tokens/
  primitives/
  controls/
  panels/
  navigation/
  inspector/
  status/
  overlays/
  data-display/

packages/dde-shell/
  AppRail
  GlobalTopBar
  ContextSidebar
  Workspace
  InspectorPanel
  StatusBar
  ShellLayout

packages/frontend-studio/
  Canvas
  FrontendChat
  CandidateDock
  SourceBlend
  Locks
  Coverage
  ExperienceGraph
  MutationPlanner
```

No DDE module is allowed to create a parallel private design system.

---

## 11. Anti-drift enforcement

The approved image becomes a **golden visual regression target**.

Required controls:

1. screenshot tests at the canonical 1672 × 941 viewport;
2. component visual regression tests;
3. design-token linting;
4. forbidden raw-colour/raw-spacing rules where practical;
5. shared-shell dependency enforcement;
6. review check for any custom component that duplicates an existing primitive;
7. reference-image comparison before Frontend Studio visual acceptance;
8. cross-window consistency tests.

### Acceptance categories

- **Geometry:** major columns, header, inspector, toolbar and status bar align with the golden layout.
- **Density:** interface remains compact and information-rich.
- **Typography:** sizes/weights remain within the canonical scale.
- **Colour:** chrome stays neutral with restrained blue/indigo/violet emphasis.
- **Borders/elevation:** thin borders and subtle shadows dominate.
- **Interaction:** selected/locked/active states reproduce the reference grammar.
- **Consistency:** every DDE module visibly belongs to the same product.

A screen can be functionally correct and still fail the DDE UI gate if it visually drifts from this baseline.

---

## 12. Frontend coverage and completeness

The design lock does not permit feature thinning.

Frontend Studio must be driven by the DDE comprehensive Product Experience Template and the project Frontend Contract so that every applicable:

- persona,
- journey,
- surface,
- route,
- screen,
- feature,
- component,
- state,
- permission,
- responsive mode,
- error case,
- accessibility requirement,
- data contract,
- analytics event,
- acceptance criterion

is either:

- implemented,
- explicitly deferred,
- explicitly not applicable,
- or blocked with a recorded reason.

Nothing is silently omitted.

---

## 13. Orchestrator authority

The project Manager/Orchestrator owns the frontend programme.

It is responsible for:

- design completeness,
- source selection,
- candidate generation,
- locking decisions,
- delegation,
- conflict detection,
- integration sequencing,
- implementation verification,
- visual regression,
- final frontend acceptance.

Worker agents may search, generate, adapt, inspect and test, but they do not independently redefine locked frontend architecture or product scope.

---

## 14. Non-negotiable rules

1. **This approved mockup is the canonical DDE visual baseline.**
2. **All DDE windows inherit the same shell and visual language.**
3. **No module creates its own incompatible UI system.**
4. **Chat, drag/drop, templates, MCP imports and AI design operations share one mutation/state architecture.**
5. **Locks are functional constraints, not decorative badges.**
6. **The project Manager/Orchestrator owns frontend design and coverage.**
7. **Templates and donor repos are candidate sources, not automatically the law.**
8. **Retrieve before inventing, but validate every retrieved asset.**
9. **Every frontend change must preserve product coverage unless scope is explicitly changed.**
10. **Visual regression against the golden reference is a release gate.**

---

## 15. Definition of done for the reconstruction

The Frontend Studio reconstruction is not complete until:

- the production shell matches the approved screenshot at the canonical desktop viewport;
- the project explorer, modes, canvas, inspector, frontend chat, candidate dock, source blend, lock states, orchestrator card and status bar are functional;
- all controls are backed by real state rather than static decoration;
- responsive states are implemented;
- accessibility passes the chosen target;
- all DDE screens use the shared shell and design tokens;
- screenshot regression is automated;
- no known visual forks remain;
- the user can move between DDE modules without feeling that they entered a different application.

---

# PART II — Canonical Architecture

## 16. Rev 2 authority, scope and relationship to Rev 1

Rev 2 consolidates the locked visual constitution with the architecture, product-experience, orchestration, state, coverage, sourcing, implementation and verification systems required to make Frontend Studio a production system rather than a visual concept.

### 16.1 Authority hierarchy

When two instructions appear to conflict, use this precedence order:

1. explicit user-approved project scope or explicit user-approved lock override;
2. project Source of Truth and Frontend Contract;
3. this Rev 2 blueprint;
4. the locked Rev 1 Visual Constitution embedded in Part I;
5. project Design Constitution and accepted design decisions;
6. current accepted implementation state;
7. selected donor constraints;
8. retrieved template/component characteristics;
9. model or agent preference.

No lower-ranked source may silently override a higher-ranked source.

### 16.2 Non-negotiable exhaustiveness invariant

Frontend Studio must never equate "a page exists" with "the feature is complete." A feature is complete only when every applicable surface, state, interaction, permission, data dependency, responsive mode, error path, accessibility obligation, analytics obligation and acceptance criterion has an explicit disposition.

Every applicable requirement must end in one of these terminal states:

- `VERIFIED`;
- `DEFERRED_APPROVED`;
- `NOT_APPLICABLE_APPROVED`;
- `BLOCKED_RECORDED`.

There is no implicit "probably covered" state.

### 16.3 Frontend Studio is a governed development environment

Frontend Studio is simultaneously:

- a visual editor;
- a design intelligence environment;
- a template/component discovery environment;
- a project experience modeler;
- a frontend implementation planner;
- a candidate/worktree controller;
- a visual QA and regression environment;
- a provenance and licensing control surface;
- a frontend-specific conversational interface;
- an orchestration surface controlled by the project Manager/Orchestrator.

It is not merely a Figma clone, code playground, prompt box, template browser or screenshot editor.

---

## 17. System context and boundaries

```text
PROJECT SOURCE OF TRUTH
        │
        ├──────────────► Project Manager / Orchestrator
        │                         │
        │                         ▼
        │                Frontend Programme State
        │                         │
        ▼                         ▼
Frontend Contract ───────► Product Experience Graph
        │                         │
        │          ┌──────────────┼─────────────────────┐
        │          │              │                     │
        ▼          ▼              ▼                     ▼
Design Sources   Chat        Direct Manipulation    /design & Agents
        │          │              │                     │
        └──────────┴──────────────┼─────────────────────┘
                                  ▼
                         Mutation Planner
                                  │
                                  ▼
                         Candidate Runtime
                                  │
                     ┌────────────┼────────────┐
                     ▼            ▼            ▼
                  Preview      Code Diff      QA
                     │            │            │
                     └────────────┼────────────┘
                                  ▼
                            Acceptance Gate
                                  │
                                  ▼
                          Production Frontend
```

### 17.1 Required boundaries

- Source discovery cannot write production code directly.
- Chat cannot bypass locks or coverage rules.
- Drag/drop cannot bypass the mutation planner.
- `/design` cannot overwrite the accepted production design directly.
- MCP providers are adapters and data/code sources, never sovereign design authorities.
- Candidate branches/worktrees cannot become production without reconciliation and acceptance.
- UI components cannot be imported without provenance and dependency assessment.
- Manager/Orchestrator acceptance cannot be delegated to a worker model that is not Manager-Chair eligible.

---

# PART III — Product Experience System

## 18. Project Experience Graph (PXG)

The Project Experience Graph is the canonical semantic representation of what the frontend means. Source files implement the graph; they are not the graph itself.

### 18.1 Graph hierarchy

```text
ProjectExperience
├── ProductArchetypes[]
├── Personas[]
├── Organisations/Roles[]
├── Surfaces[]
├── Journeys[]
├── Features[]
├── Routes[]
├── Screens[]
│   ├── Regions[]
│   ├── Components[]
│   ├── States[]
│   ├── Interactions[]
│   └── ResponsiveVariants[]
├── DataContracts[]
├── PermissionRules[]
├── AccessibilityRequirements[]
├── AnalyticsObligations[]
├── DesignTokens[]
├── DesignSources[]
├── ProvenanceRecords[]
├── Locks[]
├── AcceptanceCriteria[]
└── CoverageNodes[]
```

### 18.2 Core node contract

Every PXG node has, at minimum:

```ts
interface ExperienceNode {
  id: string
  type: ExperienceNodeType
  name: string
  description?: string
  parentId?: string
  childIds: string[]
  requirementIds: string[]
  sourceOfTruthRefs: SourceRef[]
  applicability: 'required' | 'optional' | 'not_applicable' | 'deferred'
  coverageState: CoverageState
  lockIds: string[]
  provenanceIds: string[]
  acceptanceCriteriaIds: string[]
  implementationRefs: ImplementationRef[]
  createdAt: string
  updatedAt: string
}
```

### 18.3 Screen node contract

A screen is not valid unless it declares:

- surface and route;
- target personas/roles;
- upstream entry points;
- downstream transitions;
- feature responsibilities;
- data contracts;
- permissions;
- supported states;
- responsive variants;
- accessibility obligations;
- telemetry/analytics obligations;
- loading/empty/error/offline behavior;
- acceptance criteria;
- implementation mapping;
- test evidence.

### 18.4 State taxonomy

At minimum Frontend Studio must model these state families where applicable:

- initial;
- loading;
- skeleton;
- empty;
- partial;
- populated;
- success;
- warning;
- degraded;
- validation error;
- server error;
- permission denied;
- unauthenticated;
- offline;
- stale data;
- realtime reconnecting;
- destructive confirmation;
- optimistic update;
- rollback/failure;
- feature unavailable;
- maintenance mode.

### 18.5 Relationship integrity

The graph engine must detect:

- orphan screens;
- features with no surface;
- journeys with missing transition nodes;
- permissions with no UI manifestation;
- API contracts consumed by no component;
- screens with no acceptance criteria;
- accepted requirements with no coverage nodes;
- components present in source but absent from provenance where external code was used.

---

## 19. Frontend Contract

The Frontend Contract is the project-specific machine-readable agreement between product scope and frontend implementation.

### 19.1 Required sections

```text
FrontendContract
├── ProjectIdentity
├── SupportedPlatforms
├── ProductArchetypes
├── PersonasAndRoles
├── Surfaces
├── Journeys
├── FeatureObligations
├── RouteAndScreenInventory
├── StateObligations
├── ResponsiveRequirements
├── AccessibilityTarget
├── LocalizationRequirements
├── BrandAndDesignRules
├── DesignTokens
├── DonorConstraints
├── SourcePolicies
├── ComponentPolicies
├── DataContracts
├── PermissionModel
├── AnalyticsRequirements
├── PerformanceBudgets
├── SecurityAndPrivacyRequirements
├── AcceptanceCriteria
├── CoveragePolicy
└── ExplicitDeferralsAndExclusions
```

### 19.2 Requirement expansion pipeline

```text
Source requirement
      ↓
Requirement normalisation
      ↓
Persona/role impact
      ↓
Journey impact
      ↓
Surface impact
      ↓
Screen/route obligations
      ↓
State and interaction obligations
      ↓
Data/permission obligations
      ↓
Responsive/accessibility obligations
      ↓
Acceptance criteria
      ↓
Coverage nodes
```

### 19.3 Contract change semantics

A scope change creates a versioned contract revision. Existing implemented features are never silently rewritten to fit changed requirements. The system must generate an impact report covering:

- affected routes/screens;
- affected components;
- affected tests;
- affected data contracts;
- affected locks;
- candidate design invalidation;
- required migration work;
- deprecations.

---

## 20. DDE Comprehensive Product Experience Template

DDE shall ship with a deep reference template whose purpose is completeness, not visual sameness. It represents the maximum product-experience surface DDE knows how to reason about.

### 20.1 Template rule

Projects opt branches in or out explicitly. The absence of a branch must be an explicit applicability decision, not an omission.

### 20.2 Product archetypes

The reference template must include, at minimum:

1. authentication and identity;
2. onboarding;
3. account/profile;
4. organisation/workspace management;
5. role and permission management;
6. marketplace/catalogue;
7. commerce/cart/checkout;
8. payments and financial status surfaces;
9. subscriptions/recurring services;
10. bookings/appointments;
11. service/work-order management;
12. asset management;
13. logistics/delivery;
14. communication/messaging;
15. notifications;
16. collaboration/group work;
17. document management;
18. forms/data capture;
19. analytics/reporting;
20. dashboards/command centres;
21. CRM/customer operations;
22. supplier/vendor operations;
23. inventory/stock;
24. workflow/approvals;
25. search/discovery;
26. comparison/configuration;
27. AI assistant/copilot;
28. knowledge/RAG;
29. settings/preferences;
30. administration;
31. audit/compliance;
32. support/help/issue handling;
33. developer/integration surfaces where applicable;
34. offline/resilient mobile operation where applicable.

### 20.3 Atomic archetype mapping

Each archetype must define:

- personas;
- entry points;
- primary journeys;
- secondary journeys;
- screens;
- drawers/modals/popovers;
- forms;
- tables/lists/cards;
- empty states;
- failure states;
- mobile-specific adaptations;
- accessibility requirements;
- permissions;
- notifications;
- analytics events;
- backend/API dependencies;
- acceptance criteria;
- common anti-patterns.

### 20.4 Example: logistics live tracking

```text
LOGISTICS_LIVE_TRACKING
├── Customer
│   ├── OrderDetails.entry
│   ├── Tracking.screen
│   │   ├── Map
│   │   ├── DriverMarker
│   │   ├── Destination
│   │   ├── Route
│   │   ├── ETA
│   │   ├── StatusTimeline
│   │   ├── ContactActions
│   │   └── ProofOfDelivery.result
│   └── States
│       ├── preparing
│       ├── awaiting_assignment
│       ├── assigned
│       ├── en_route
│       ├── nearby
│       ├── delivered
│       ├── tracking_unavailable
│       └── connection_lost
├── Driver
│   ├── Queue
│   ├── AssignedJob
│   ├── Navigation
│   └── ProofOfDelivery
├── Operations
│   ├── FleetMap
│   ├── DriverQueue
│   ├── Exceptions
│   └── Reassignment
└── Shared
    ├── Permissions
    ├── Privacy
    ├── EventStream
    ├── Analytics
    └── AcceptanceTests
```

### 20.5 Example: product comparison

The reference template must expand product comparison beyond a single comparison page into selection entry points, compare tray, attribute normalization, variant handling, unavailable data, mobile layout, saved/shareable comparison where in scope, accessibility, analytics, and return-to-shopping behavior.

---

## 21. Coverage Engine

### 21.1 Coverage states

```text
UNASSESSED
APPLICABILITY_CONFIRMED
REQUIRED
DESIGNED
IMPLEMENTED
WIRED
TESTED
VERIFIED
BLOCKED
DEFERRED
NOT_APPLICABLE
FAILED
REGRESSED
```

### 21.2 Coverage dimensions

Coverage scoring must not collapse everything into one misleading percentage. DDE must preserve separate dimensions:

- requirement coverage;
- journey coverage;
- screen coverage;
- state coverage;
- data-binding coverage;
- permission coverage;
- responsive coverage;
- accessibility coverage;
- analytics coverage;
- QA coverage;
- visual-regression coverage.

An overall number may be displayed only as a weighted summary with drill-down.

### 21.3 Frontend Coverage Matrix

Minimum columns:

| Requirement | Feature | Journey | Surface | Screen | States | Data | Permissions | Responsive | A11y | QA | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|

### 21.4 Regression propagation

When a verified dependency changes, dependent nodes must be marked `REGRESSED` or `REVERIFY_REQUIRED`, not left green.

Example:

```text
DesignToken changed
  → affected components
  → affected screens
  → affected visual baselines
  → re-run visual QA
```

---

# PART IV — Design Intelligence, Sources and Templates

## 22. Design Source abstraction

All source systems must implement a common adapter interface.

```ts
interface DesignSourceAdapter {
  id: string
  capabilities(): Promise<SourceCapabilities>
  search(query: DesignSearchQuery): Promise<DesignCandidate[]>
  inspect(candidateId: string): Promise<DesignCandidateDetail>
  fetch(candidateId: string): Promise<SourceArtifact>
  license(candidateId: string): Promise<LicenseAssessment>
  health(): Promise<SourceHealth>
}
```

### 22.1 Source classes

- project-native components;
- DDE approved global library;
- organisation/private library;
- selected donor repositories;
- 21st and comparable web registries;
- mobile registries;
- Figma or design-file sources where connected;
- generated candidate sources;
- archived accepted candidates.

### 22.2 Retrieval order

Default priority:

1. current project approved component;
2. project private library;
3. organisation approved library;
4. DDE global approved library;
5. suitable external registry candidate;
6. qualified donor implementation;
7. adapted template;
8. generated candidate;
9. from-scratch implementation.

This is a default, not an absolute override of project-specific design requirements.

---

## 23. Template intelligence pipeline

```text
Frontend obligation
      ↓
Semantic design query
      ↓
Parallel source search
      ↓
Candidate normalization
      ↓
Compatibility analysis
      ↓
Visual/design constitution fit
      ↓
Functional coverage analysis
      ↓
License/provenance/security analysis
      ↓
Dependency cost analysis
      ↓
Adaptation estimate
      ↓
Ranked candidate board
```

### 23.1 Candidate score dimensions

Candidates may be scored on:

- product-fit;
- feature coverage;
- design-system fit;
- responsive fitness;
- accessibility fitness;
- architecture compatibility;
- dependency burden;
- performance cost;
- security posture;
- license confidence;
- adaptation cost;
- maintainability;
- provenance confidence;
- project reuse value.

Scores must be explainable. An overall score cannot hide a hard failure such as incompatible license or broken dependency constraints.

### 23.2 Hard rejection reasons

- unknown or incompatible license;
- unsupported framework/runtime;
- known critical dependency vulnerability without approved mitigation;
- inaccessible structure where remediation cost exceeds threshold;
- incompatible project architecture;
- violation of locked design constraints;
- hidden remote runtime dependency not allowed by the project;
- unsafe code-generation pattern.

---

## 24. Donor repository decomposition

Donor repos are evidence sources, not automatic product law.

Each selected donor must be decomposed into atomic directives:

```text
DonorDirective
├── scope
├── category
├── strength
├── source_ref
├── applies_to
├── excludes
└── rationale
```

Categories:

- `VISUAL_INSPIRATION`;
- `LAYOUT_REFERENCE`;
- `INTERACTION_LAW`;
- `INFORMATION_ARCHITECTURE_LAW`;
- `MOTION_REFERENCE`;
- `COMPONENT_DONOR`;
- `TECHNICAL_ARCHITECTURE_DONOR`;
- `ACCESSIBILITY_REFERENCE`;
- `FORBIDDEN_CHARACTERISTIC`.

Strengths:

- `HARD`;
- `STRONG`;
- `SOFT`;
- `INSPIRATION_ONLY`.

Example:

```text
Donor: X
navigation                 HARD
information density        STRONG
typography                 IGNORE
hero composition           INSPIRATION_ONLY
colour system               FORBIDDEN
command palette behaviour  HARD
```

---

## 25. Web design-source adapters

### 25.1 21st adapter

The 21st adapter is used for component/template/theme discovery and retrieval, never as direct uncontrolled code insertion.

Required adapter responsibilities:

- search and retrieval;
- artifact inspection;
- dependency extraction;
- license/provenance capture;
- component decomposition;
- project-framework compatibility;
- token adaptation estimate;
- sandbox import;
- validation before promotion.

### 25.2 Other web registries

DDE may support other registries through the same adapter contract. No provider-specific behavior may leak into the Product Experience Graph or mutation engine.

---

## 26. Mobile design-source and validation adapters

### 26.1 Mobile component sources

DDE should support adapters for approved React Native/Expo ecosystems such as:

- BNA UI;
- gluestack;
- React Native Reusables;
- internal DDE mobile library;
- approved donor repositories.

### 26.2 Mobile runtime validation

Expo and device-agent tooling belong to the validation/execution side of Frontend Studio.

The mobile loop must support:

```text
candidate screen
   ↓
build/run
   ↓
launch simulator/device
   ↓
screenshot
   ↓
inspect hierarchy
   ↓
interact
   ↓
collect logs/network/performance
   ↓
compare
   ↓
repair
```

### 26.3 Version gating

Every adapter records supported library/runtime versions. DDE must fail closed on incompatible generator/library combinations rather than assuming backward compatibility.

---

## 27. Internal DDE component intelligence

The internal library must not become a dump of near-duplicate UI.

### 27.1 Component identity model

Each approved component records:

- semantic purpose;
- supported variants;
- required tokens;
- supported states;
- responsive behavior;
- accessibility contract;
- dependencies;
- provenance;
- usage count;
- owning package;
- replacement/deprecation relationship.

### 27.2 Duplicate detection

Before introducing a component, DDE compares candidates by:

- semantic role;
- API/props shape;
- visual similarity;
- behavior similarity;
- dependency graph;
- source provenance.

Results:

- `REUSE_EXISTING`;
- `ADD_VARIANT`;
- `FORK_JUSTIFIED`;
- `NEW_COMPONENT`;
- `REJECT_DUPLICATE`.

---

## 28. Design System Compiler

External design artifacts are never pasted blindly into production.

```text
External artifact
      ↓
Source/AST analysis
      ↓
Component decomposition
      ↓
Semantic classification
      ↓
Dependency extraction
      ↓
Token extraction
      ↓
Project primitive mapping
      ↓
CSS/style normalization
      ↓
Responsive normalization
      ↓
Accessibility remediation
      ↓
Event/data-binding isolation
      ↓
Security/static analysis
      ↓
Sandbox build
      ↓
Visual/behavior validation
      ↓
Project-ready component
```

### 28.1 Compiler outputs

- adapted source;
- dependency manifest;
- token mapping report;
- unsupported behavior report;
- accessibility report;
- provenance record;
- visual delta report;
- tests or generated test obligations.

---

# PART V — Interaction, Mutation and Locking

## 29. Unified Frontend Mutation Protocol

Every editing mechanism emits structured mutations.

### 29.1 Mutation operations

```text
ADD
REMOVE
MOVE
REORDER
REPLACE
MERGE
SPLIT
RESTYLE
REBIND_DATA
REBIND_ACTION
CHANGE_VARIANT
ADAPT_RESPONSIVE
PROPAGATE
LOCK
UNLOCK
DEPRECATE
RESTORE
REVERT
```

### 29.2 Mutation envelope

```ts
interface FrontendMutation {
  id: string
  projectId: string
  candidateId?: string
  actor: ActorRef
  origin: 'chat' | 'drag_drop' | 'template' | 'mcp' | 'agent' | 'manual' | 'system'
  intent: string
  operations: MutationOperation[]
  targetNodeIds: string[]
  preserveNodeIds: string[]
  lockAssertions: LockAssertion[]
  coverageImpact: CoverageImpact
  dependencyImpact: DependencyImpact
  provenanceChanges: ProvenanceChange[]
  preconditions: Precondition[]
  validationPlan: ValidationPlan
  rollbackPlan: RollbackPlan
  status: MutationStatus
}
```

### 29.3 Mandatory mutation pipeline

```text
Intent
 ↓
Reference resolution
 ↓
Graph target resolution
 ↓
Lock check
 ↓
Coverage impact
 ↓
Dependency impact
 ↓
Conflict analysis
 ↓
Mutation plan
 ↓
Candidate/worktree apply
 ↓
Build/preview
 ↓
Validation
 ↓
User/manager accept or revise
```

---

## 30. Frontend chat architecture

The Frontend Studio chat is context-aware and frontend-scoped.

### 30.1 Context package

Every chat turn may receive:

- selected node(s);
- screen/route;
- visible viewport;
- current candidate;
- accepted design version;
- active locks;
- Design Constitution;
- Frontend Contract;
- PXG slice;
- project component inventory;
- relevant source candidates;
- recent mutations;
- current errors/warnings;
- worktree/runtime state.

### 30.2 Reference resolution

Natural references such as "this", "that sidebar", "Template C", "the locked hero", "Candidate B" must resolve to concrete IDs before execution.

Ambiguity rule:

- if one interpretation is high-confidence and non-destructive, produce a preview plan;
- if multiple materially different interpretations remain, ask for clarification or show competing plans;
- never guess through a lock boundary.

### 30.3 Chat command classes

- inspect/explain;
- search/source;
- compare;
- propose;
- mutate candidate;
- propagate pattern;
- verify;
- undo/revert;
- coverage query;
- missing-screen discovery;
- responsive adaptation;
- accessibility remediation.

### 30.4 Example

User instruction:

> Take the hero section from Template C and blend it into the locked selection. Keep navigation, typography and our existing search component.

Resulting plan:

```text
TARGET      current.home.hero
IMPORT      TemplateC.hero.variant2
PRESERVE    current.global.navigation
PRESERVE    current.design.typography
PRESERVE    current.components.search
ADAPT       spacing → project tokens
ADAPT       CTA → project Button
CHECK       hero Section Lock
CHECK       homepage coverage
VALIDATE    desktop/tablet/mobile + visual regression
OUTPUT      Candidate D
```

---

## 31. Lock model and conflict engine

### 31.1 Lock scope

Locks can target:

- project;
- design system;
- token;
- surface;
- screen;
- region;
- component;
- behavior;
- content;
- responsive rule;
- data binding.

### 31.2 Lock attributes

```text
lock_id
scope
target
owner
reason
strength
created_from_decision
allowed_mutations[]
requires_approval_from[]
expires_at?
```

### 31.3 Conflict precedence

```text
Explicit current user instruction with approved unlock
      >
Frontend Contract
      >
Hard project locks
      >
Design Constitution
      >
Accepted current design
      >
Strong donor directives
      >
Retrieved template/component
      >
Generated suggestion
```

### 31.4 Conflict outcomes

- `NO_CONFLICT`;
- `AUTO_ADAPT_SAFE`;
- `PREVIEW_REQUIRED`;
- `APPROVAL_REQUIRED`;
- `REJECT_LOCKED`;
- `SCOPE_CHANGE_REQUIRED`.

---

# PART VI — Candidate Runtime, Worktrees and Preview

## 32. Candidate lifecycle

```text
PROPOSED
  ↓
MATERIALIZING
  ↓
BUILDING
  ↓
PREVIEW_READY
  ↓
VALIDATING
  ↓
VALIDATED
  ↓
SHORTLISTED
  ↓
ACCEPTED / REJECTED / SUPERSEDED
```

### 32.1 Isolation invariant

Each candidate must use an isolated branch/worktree or equivalent sandbox. No exploratory candidate modifies the accepted production branch directly.

### 32.2 Candidate record

```text
candidate_id
direction_label
source_mix
originating_instruction
worktree_ref
commit_ref
preview_url/runtime_ref
visual_baselines
coverage_delta
qa_results
build_status
provenance
score_breakdown
accepted_status
```

### 32.3 Candidate board

The UI may show Direction A/B/C without model identity. Model/provider information remains available in provenance/technical detail but should not bias user selection by default.

### 32.4 Reconciliation

Acceptance is not a blind merge. Reconciliation must:

- rebase against latest accepted implementation;
- re-run lock checks;
- re-run coverage impact;
- resolve component duplication;
- re-run build/test/visual QA;
- update PXG and provenance;
- update baselines;
- mark superseded candidates.

---

## 33. Live preview architecture

The live canvas must render the real application or a faithful isolated runtime, not a fake screenshot representation.

### 33.1 Preview capabilities

- desktop/tablet/mobile viewports;
- route navigation;
- seeded realistic data;
- state switching;
- permission switching;
- theme switching where supported;
- offline/degraded simulation;
- loading/error simulation;
- grid/spacing overlay;
- bounding-box selection;
- component hierarchy inspection;
- data-binding inspection.

### 33.2 Preview safety

Destructive real-world actions must be stubbed or routed to safe local/test environments unless explicitly authorized.

---

# PART VII — Provenance, Licensing and Security

## 34. Provenance ledger

Every externally derived artifact gets a provenance record.

Required fields:

```text
source_provider
source_type
source_identifier
source_url_or_repo_ref
author_if_known
license
license_confidence
commercial_use_status
attribution_requirement
retrieved_at
source_version_or_commit
source_hash
imported_hash
dependencies
modifications
compiler_report
security_scan_ref
projects_using
supersedes/superseded_by
```

### 34.1 Unknown license rule

`UNKNOWN` license confidence blocks production import by default.

### 34.2 Source Blend

The visible Source Blend panel is backed by actual node-level provenance. Percentages must be derived from attributable regions/components, not fabricated stylistic estimates.

---

## 35. Dependency and security gate

Imported artifacts undergo:

- package/dependency extraction;
- known-vulnerability scan where tooling supports it;
- unsafe script detection;
- remote asset/service detection;
- license compatibility check;
- framework/runtime compatibility;
- code-quality/static checks;
- permission/privacy review where applicable.

No external MCP or registry may bypass this gate.

---

# PART VIII — Manager/Orchestrator Control

## 36. Frontend programme state machine

The project Manager/Orchestrator owns this lifecycle:

```text
DISCOVER
  ↓
MODEL_EXPERIENCE
  ↓
ASSESS_COVERAGE
  ↓
SOURCE_OPTIONS
  ↓
EXPLORE_DIRECTIONS
  ↓
COMPARE
  ↓
LOCK_DECISIONS
  ↓
PLAN_IMPLEMENTATION
  ↓
DELEGATE
  ↓
IMPLEMENT
  ↓
VERIFY
  ↓
RECONCILE
  ↓
ACCEPT
  ↓
MONITOR_REGRESSION
```

### 36.1 Manager-exclusive responsibilities

A Manager-Chair-eligible model must retain authority for:

- interpreting frontend scope where it materially affects product behavior;
- accepting design direction;
- approving lock changes;
- reconciling conflicting donor/template constraints;
- approving scope deferrals;
- accepting final candidate integration;
- resolving cross-feature conflicts;
- declaring frontend milestone completion.

### 36.2 Worker-delegable responsibilities

Workers may:

- search registries;
- inspect templates;
- gather screenshots;
- classify components;
- run accessibility checks;
- run visual tests;
- implement bounded packets;
- prepare candidate worktrees;
- generate reports;
- execute deterministic validations.

### 36.3 Quality-first rule

Frontend work is not complete because an agent returned successfully. Completion is determined by coverage, tests, visual equivalence, integration evidence and acceptance gates.

---

## 37. Delegation packet schema

Each frontend packet must include:

```text
packet_id
objective
bounded_scope
PXG_nodes
FrontendContract_refs
locks
allowed_files/areas
forbidden_changes
source_candidates
acceptance_criteria
required_tests
visual_reference
rollback_expectation
reporting_format
```

A worker may not widen its packet because an alternative implementation seems easier.

---

# PART IX — QA, Validation and Acceptance

## 38. Comprehensive QA matrix

Every applicable screen/feature must be assessed across:

### 38.1 Functional

- route reachable;
- core actions work;
- state transitions work;
- data bound correctly;
- permissions enforced;
- forms validate;
- destructive actions confirm;
- realtime updates recover;
- optimistic updates roll back correctly.

### 38.2 Visual

- golden screenshot comparison;
- component regression;
- spacing/tokens;
- typography;
- alignment;
- overflow/clipping;
- long-content resilience;
- empty/loading/error visual states.

### 38.3 Responsive

At minimum validate project-supported breakpoints and orientation states. Mobile apps additionally validate device classes, safe areas, keyboard avoidance and touch ergonomics.

### 38.4 Accessibility

Where applicable:

- keyboard navigation;
- focus visibility/order;
- semantic labels;
- screen-reader semantics;
- color contrast;
- target sizes;
- reduced motion;
- form error association;
- table/list semantics;
- modal focus trapping/restoration.

### 38.5 Performance

Project-specific budgets should include relevant measures such as:

- bundle growth;
- render cost;
- interaction latency;
- layout shift;
- animation frame stability;
- image/media optimization;
- mobile startup and screen transition performance.

### 38.6 Compatibility

Validate supported browsers/platforms/runtime versions defined in the Frontend Contract.

### 38.7 Security/privacy

Validate that UI does not leak unauthorized state, sensitive data, debug information or cross-role data.

---

## 39. Visual regression strategy

### 39.1 Golden master

The approved 1672 × 941 DDE Frontend Studio mockup remains the canonical shell regression target.

### 39.2 Baseline layers

- global shell baseline;
- module baseline;
- screen baseline;
- critical component baseline;
- responsive baseline;
- state baseline.

### 39.3 Failure triage

A visual diff must be classified as:

- intended accepted change;
- benign rendering variance;
- design-system drift;
- layout regression;
- missing content/state;
- responsive regression;
- unknown requiring review.

Baselines cannot be blindly updated to make tests green.

---

## 40. Acceptance gate

A candidate may be accepted only when:

- required build passes;
- required functional tests pass;
- required visual tests pass;
- no hard lock conflict remains;
- no unresolved coverage regression remains;
- provenance is complete;
- required license/security checks pass;
- accessibility target is satisfied or approved exceptions recorded;
- responsive target is satisfied;
- PXG and source implementation reconcile;
- Manager/Orchestrator acceptance is recorded.

---

# PART X — Failure Recovery and Consistency

## 41. Failure classes

DDE must handle at least:

- source adapter offline;
- MCP unavailable;
- source authentication expired;
- candidate dependency install failure;
- compilation failure;
- runtime preview failure;
- visual-test infrastructure failure;
- model timeout/rate limit;
- partial worker completion;
- dirty/conflicted worktree;
- lock metadata mismatch;
- PXG/source divergence;
- unsupported framework version;
- license uncertainty;
- imported component vulnerability;
- stale candidate after production changed.

### 41.1 Recovery principles

- fail closed on lock/license/security uncertainty;
- preserve accepted production state;
- preserve mutation and agent audit history;
- never update baselines simply to hide failure;
- mark affected coverage as blocked/regressed;
- surface actionable recovery steps;
- allow safe retry/idempotent re-execution where practical.

### 41.2 Model interruption recovery

A worker/model interruption must persist:

- packet state;
- files changed;
- validation completed;
- validation remaining;
- candidate/worktree reference;
- assumptions made;
- unresolved blockers.

The next eligible agent resumes from recorded evidence rather than redoing or guessing.

---

## 42. PXG/source reconciliation

A periodic and pre-release reconciliation job compares:

```text
Frontend Contract
↕
Project Experience Graph
↕
Routes/screens/components in source
↕
Tests
↕
Visual baselines
```

Divergence creates explicit findings. Production source is not automatically trusted over the contract, and the graph is not automatically trusted over executable source.

---

# PART XI — Persistence and Domain Model

## 43. Core persistent entities

```text
DesignProject
FrontendContract
FrontendContractVersion
DesignConstitution
ExperienceNode
ExperienceEdge
CoverageNode
CoverageAssessment
DesignSource
SourceAdapterConfig
SourceArtifact
Template
TemplateFragment
ComponentDefinition
ComponentUsage
Candidate
CandidateScore
WorktreeRecord
PreviewSession
FrontendMutation
MutationOperation
Lock
DesignDecision
ProvenanceRecord
LicenseAssessment
DependencyAssessment
ValidationPlan
ValidationResult
VisualBaseline
VisualDiff
Review
AcceptanceRecord
OrchestrationPacket
AgentExecution
```

### 43.1 Append-only decisions

Design decisions, acceptance events, lock changes and provenance imports should be append-only/auditable. Current state can be materialized from events, but historical decisions must remain inspectable.

---

## 44. Suggested storage boundaries

Conceptually:

```text
frontend_domain
  pxg
  contract
  coverage
  mutations
  locks
  candidates
  provenance
  validation

source_adapters
  web
  mobile
  donor
  figma

runtime
  worktrees
  previews
  screenshot_baselines
  test_artifacts
```

Exact persistence technology may follow DDE's broader architecture, but domain boundaries must remain intact.

---

# PART XII — API and Event Contracts

## 45. Internal API capability groups

Frontend Studio requires internal services/capabilities for:

- PXG query/mutation;
- Frontend Contract versions;
- coverage evaluation;
- source search/inspection/import;
- candidate creation;
- worktree lifecycle;
- preview lifecycle;
- mutation planning/application;
- lock evaluation;
- provenance recording;
- validation execution;
- baseline management;
- acceptance/reconciliation.

### 45.1 Important events

```text
frontend.contract.updated
frontend.coverage.regressed
frontend.source.imported
frontend.candidate.created
frontend.candidate.preview_ready
frontend.mutation.planned
frontend.mutation.applied
frontend.lock.conflict
frontend.validation.failed
frontend.validation.passed
frontend.candidate.accepted
frontend.baseline.updated
frontend.pxg.divergence_detected
```

Events enable the orchestrator and UI to stay synchronized without hard-coupling modules.

---

# PART XIII — Cross-DDE Visual and Functional Migration

## 46. DDE module catalogue

Every first-party DDE module must inherit the canonical shell and receive its own atomic screen map. The minimum module catalogue is:

1. Home / Projects;
2. Project Overview;
3. Source of Truth / Documents;
4. Frontend Studio;
5. Backend / Service Architecture where exposed;
6. Models;
7. Harnesses;
8. Orchestration;
9. Agents;
10. Tasks / Packets;
11. Runs / Sessions;
12. Validation / QA;
13. RAG / Knowledge;
14. Integrations / MCP;
15. Git / Worktrees / Changes;
16. Runtime / Environments;
17. Automations;
18. Logs / Observability;
19. Security / Privacy / Policy;
20. Settings.

The actual repo may name or group modules differently, but no current DDE window may escape the visual-system migration by virtue of legacy implementation.

---

## 47. Atomic module mapping requirement

For every module create:

```text
Module
├── purpose
├── personas
├── left-nav groups
├── primary workspace views
├── right-inspector contexts
├── commands/actions
├── empty/loading/error states
├── filters/search
├── permissions
├── notifications
├── status-bar signals
├── responsive behavior
├── deep links
├── telemetry
└── acceptance criteria
```

A module is not considered migrated because its colors match the new shell.

---

## 48. Example: Models module

```text
MODELS
├── All Models
├── Manager Eligible
├── Worker Eligible
├── Harnesses
├── Role Policies
├── Fallbacks
├── Health
└── History
```

Main workspace should support:

- unified model catalogue;
- harness/source identity;
- Manager Chair eligibility;
- worker eligibility;
- allowed task classes;
- failover chain;
- health/availability;
- constraints/limits;
- policy conflicts;
- audit of role changes.

The Inspector presents selected model/harness detail using the canonical compact panel grammar.

---

## 49. Example: Orchestration module

```text
ORCHESTRATION
├── Manager Chair
├── Active Agents
├── Queues
├── Delegations
├── Policies
├── Evidence
└── History
```

Main workspace supports graph/lanes showing packet ownership, dependencies, model/harness identity, status, evidence and blockers. The Inspector provides selected packet/agent/run details.

---

# PART XIV — Technical Package Architecture

## 50. Suggested package structure

```text
packages/
  ui/
    tokens/
    primitives/
    controls/
    navigation/
    panels/
    inspector/
    status/
    overlays/
    data-display/
    accessibility/

  dde-shell/
    app-rail/
    top-bar/
    context-sidebar/
    workspace/
    inspector-panel/
    status-bar/
    shell-layout/

  frontend-domain/
    pxg/
    contract/
    coverage/
    locks/
    mutations/
    provenance/

  frontend-studio/
    canvas/
    chat/
    candidates/
    source-blend/
    directions/
    coverage-mode/
    architecture-mode/
    qa-mode/
    source-mode/

  design-sources/
    adapters/
    registry/
    donor/
    compiler/

  candidate-runtime/
    worktrees/
    previews/
    reconciliation/

  visual-qa/
    baselines/
    screenshots/
    diffing/
    reporting/
```

This is conceptual; implementation must reconcile with the actual repository rather than blindly creating parallel structure.

### 50.1 Anti-duplication rule

Before creating any new package or primitive, the implementer must search the actual repo for an existing equivalent and record reuse/migration rationale.

---

# PART XV — Non-Functional Requirements

## 51. Performance

Frontend Studio must remain usable under large projects. Requirements include:

- virtualized large trees/lists where needed;
- incremental PXG loading;
- incremental coverage recomputation;
- debounced visual updates;
- isolated preview runtime;
- background candidate validation;
- cancellation of stale searches/builds;
- no UI freeze while agent/model operations run.

### 51.1 Large-project targets

Exact targets should be benchmarked against the DDE repo and hardware, but architecture must assume thousands of experience nodes, hundreds of screens/components and many historical candidate/validation records.

---

## 52. Accessibility of Frontend Studio itself

The editor must support:

- full keyboard navigation for core commands;
- visible focus states;
- labeled icon buttons;
- accessible trees/tabs/dialogs;
- non-color-only status communication;
- reduced motion;
- scalable UI text without destroying essential layout;
- screen-reader-relevant labels for controls and inspector state where practical.

---

## 53. Security and privacy

Frontend Studio must:

- preserve DDE's no-unapproved-export/privacy requirements;
- avoid sending full proprietary project source to external services unless explicitly allowed by connector/provider policy and project configuration;
- minimize context passed to external providers;
- log source/provider access;
- distinguish local/subscription harness use from external API upload;
- protect secrets from visual previews, logs and generated screenshots;
- prevent worker agents from reading unrelated sensitive project areas when packet scope does not require it.

---

# PART XVI — Implementation Programme

## 54. Phase 0 — Repository reconnaissance and freeze

Before implementation:

- inventory all current DDE screens/windows;
- inventory existing UI frameworks/components;
- inventory current Frontend Studio code;
- inventory model/orchestration interfaces relevant to Frontend Studio;
- identify duplicate design systems;
- locate current routing/state architecture;
- capture screenshots of every current screen;
- map current implementation to this blueprint;
- create migration risk register.

No major UI rewrite begins before this audit is recorded.

---

## 55. Phase 1 — Canonical tokens and primitives

Deliver:

- token package;
- typography/radius/border/shadow rules;
- buttons/inputs/tabs/badges/tooltips/menus;
- panels/section headers;
- tree/list patterns;
- selection/lock visuals;
- icon treatment;
- accessibility foundations;
- Storybook/component harness if compatible with repo.

Gate: component visual tests green.

---

## 56. Phase 2 — Shared DDE shell

Implement:

- App Rail;
- Global Top Bar;
- Context Sidebar;
- Workspace;
- Inspector Panel;
- Status Bar;
- responsive collapse/drawer behavior.

Gate: shell matches golden reference at canonical viewport within approved visual tolerance.

---

## 57. Phase 3 — Frontend Studio skeleton

Implement real versions of:

- project explorer;
- mode tabs;
- canvas toolbar;
- live canvas container;
- inspector;
- frontend chat surface;
- candidate dock;
- Source Blend;
- orchestrator card;
- status bar integration.

No fake decorative controls are accepted.

---

## 58. Phase 4 — Product Experience Graph and Frontend Contract

Deliver schemas, persistence, validators, graph explorer and project contract generation/migration path.

Gate: existing project frontend can be represented without silent missing routes/screens/features.

---

## 59. Phase 5 — Coverage Engine

Deliver atomic coverage calculation, matrix, regression propagation and blocking/deferral workflows.

Gate: selected project scope produces traceable requirement-to-screen-to-test coverage.

---

## 60. Phase 6 — Mutation and lock engine

Deliver unified mutation protocol for chat/direct editing/templates/agents; enforce locks and rollback.

Gate: no supported mutation path can bypass lock checks.

---

## 61. Phase 7 — Source adapters and Design System Compiler

Start with approved high-value providers and internal sources. Build adapter contracts so providers can be added/removed without rewriting Frontend Studio.

Gate: imported candidate can be traced, adapted, sandbox-built and rejected safely.

---

## 62. Phase 8 — Candidate/worktree runtime

Deliver isolated branches/worktrees, previews, candidate status, diffing, reconciliation and cleanup.

Gate: multiple design directions can coexist without production collision.

---

## 63. Phase 9 — Frontend chat and design orchestration

Wire chat to PXG + mutation planner + candidate runtime. Integrate Manager/Orchestrator control and bounded worker delegation.

Gate: a complex instruction such as "blend Template C's hero into the locked selection while preserving navigation, typography and project search" produces a safe preview candidate and correct provenance.

---

## 64. Phase 10 — Comprehensive QA automation

Deliver functional, accessibility, responsive and visual validation pipelines, including mobile validation where applicable.

Gate: acceptance record cannot be produced without required evidence.

---

## 65. Phase 11 — Cross-DDE migration

Migrate every DDE module to the shared shell and canonical component system using atomic module maps.

Gate: no legacy window visually or interactionally appears to be a separate product without an approved exception.

---

## 66. Phase 12 — Hardening and performance

- large-project benchmarks;
- failure injection;
- adapter outages;
- model interruption recovery;
- dirty-worktree recovery;
- security reviews;
- provenance audits;
- regression-baseline governance;
- accessibility pass;
- cleanup of old/parallel UI systems.

---

# PART XVII — Verification Scenarios

## 67. Mandatory end-to-end scenarios

### Scenario A — Blend a template fragment

User selects locked home screen and asks chat to blend Template C hero while preserving navigation and typography.

Must prove:

- references resolved;
- lock check performed;
- source artifact inspected;
- provenance recorded;
- compiler adapts component;
- candidate worktree created;
- preview rendered;
- visual/functional QA run;
- current production unchanged before acceptance;
- acceptance merges safely.

### Scenario B — Find missing project frontend coverage

User asks: "What frontend is missing for supplier promotions?"

Must return coverage from Contract/PXG, not model memory, including missing screens, states, permissions and tests.

### Scenario C — Mobile design adaptation

User requests mobile equivalent of accepted web feature.

Must inspect mobile requirements, search approved mobile sources, create candidate, run on supported Expo/device runtime, capture screenshots/interactions, validate touch/accessibility and preserve cross-platform product semantics.

### Scenario D — Locked conflict

Agent attempts to replace a hard-locked navigation component.

System must block or require approved unlock; no silent overwrite.

### Scenario E — External source failure

21st or another provider is unavailable mid-search.

System must continue with remaining sources, label degraded search coverage and never claim complete provider coverage.

### Scenario F — Scope change regression

Frontend Contract adds a new required state to an existing feature.

Coverage must regress the affected feature and dependent tests until implemented and verified.

---

# PART XVIII — Definition of Done at Dial Depth and Breadth

## 68. Rev 2 programme Definition of Done

Frontend Studio reaches the required depth-and-breadth standard only when all of the following are true:

### Visual system

- canonical shell visually matches the approved golden reference;
- all DDE windows inherit the same visual language;
- visual drift is automatically detected.

### Product completeness

- Frontend Contract exists and is versioned;
- PXG represents all applicable project frontend scope;
- Product Experience Template applicability is explicit;
- no required feature/screen/state can disappear silently;
- coverage dimensions are measurable and inspectable.

### Editing architecture

- chat, drag/drop, imports, templates and agent operations share the mutation protocol;
- locks are enforced consistently;
- undo/revert and audit records exist;
- accepted design is protected from exploratory work.

### Design intelligence

- project/internal/external sources are searchable through adapters;
- donor repos are atomically classified;
- candidates are ranked with explainable dimensions;
- external code passes provenance/license/security/compatibility gates;
- retrieve-before-invent is enforced without blocking justified bespoke work.

### Candidate runtime

- multiple design directions run in isolation;
- live previews are real;
- worktree conflicts and stale candidates are handled;
- acceptance reconciles graph, code, tests and provenance.

### Orchestration

- Project Manager owns frontend programme state;
- Manager-Chair eligibility is enforced;
- workers receive bounded packets;
- lower-tier agents cannot redefine scope/locks independently;
- interrupted work can resume from recorded state.

### QA

- functional, responsive, accessibility, performance and visual validation operate at required scope;
- mobile runtime validation exists for mobile projects;
- regression baselines are governed;
- acceptance evidence is inspectable.

### Cross-DDE consistency

- each module has an atomic migration map;
- no module uses an unapproved parallel design system;
- settings, models, orchestration, agents, RAG, runtime and all other windows look and behave like parts of the same DDE product.

---

# PART XIX — Build-Time Guardrails

## 69. Forbidden implementation shortcuts

The following are explicit failures:

- using the golden mockup as a background image;
- hardcoding fake candidate scores or provenance percentages;
- shipping decorative controls with no backing state;
- importing external components directly into production;
- allowing chat to write around locks;
- treating "page implemented" as coverage completion;
- auto-approving unknown licenses;
- updating visual baselines to hide regressions;
- giving a worker model authority to accept cross-feature scope changes;
- copying Rev 1 styles separately into each DDE module;
- creating a second component system because migration is inconvenient;
- silently dropping mobile/responsive/error/accessibility states;
- claiming an MCP/registry search was comprehensive when that source was unavailable.

---

## 70. Required implementation artifacts

The implementation programme must maintain, in-repo and versioned:

```text
FRONTEND_STUDIO_REV2.md                      ← this blueprint
FRONTEND_CONTRACT.schema.*
PXG.schema.*
FRONTEND_COVERAGE_STATE.*
DESIGN_SOURCE_ADAPTER_CONTRACT.*
FRONTEND_MUTATION_PROTOCOL.*
LOCK_MODEL.*
PROVENANCE_SCHEMA.*
VISUAL_REGRESSION_POLICY.*
FRONTEND_IMPLEMENTATION_STATE.md
FRONTEND_DECISION_LOG.md
FRONTEND_MIGRATION_MAP.md
FRONTEND_RESUME_PROMPT.md
```

Exact extensions follow the actual repo stack.

---

# PART XX — Canonical Decision Register

## 71. Locked decisions introduced or consolidated by Rev 2

**FS-REV2-001 — Golden visual baseline**
The approved 1672 × 941 Frontend Studio mockup remains the canonical visual reference.

**FS-REV2-002 — Shared DDE shell**
All first-party DDE windows inherit one shell and design language.

**FS-REV2-003 — Project Experience Graph**
Frontend semantics are represented canonically in the PXG; source files implement it.

**FS-REV2-004 — Frontend Contract**
Project requirements are translated into explicit frontend obligations through a versioned contract.

**FS-REV2-005 — Comprehensive Product Experience Template**
DDE uses a Dial-depth reference template to prevent silent omissions.

**FS-REV2-006 — Explicit applicability**
Template branches are required, deferred or not applicable by explicit decision.

**FS-REV2-007 — Unified mutation protocol**
Chat, drag/drop, templates, MCP imports, manual edits and agents share one mutation architecture.

**FS-REV2-008 — Functional locks**
Locks are enforced by the mutation/conflict engine and cannot be silently bypassed.

**FS-REV2-009 — Donors as atomic directives**
A donor repo is not global design law unless explicitly designated; its relevant qualities are classified atomically.

**FS-REV2-010 — Templates as candidates**
Templates/components from 21st and other providers are candidate sources, not automatic project foundations.

**FS-REV2-011 — Retrieve before inventing**
Frontend Studio searches approved internal/external sources before creating new components, while permitting justified bespoke design.

**FS-REV2-012 — Design System Compiler**
External source artifacts must be normalized, adapted and validated before production use.

**FS-REV2-013 — Isolated candidates**
Exploratory design directions use isolated candidate worktrees/runtimes.

**FS-REV2-014 — Manager ownership**
The project Manager/Orchestrator owns the frontend design programme and final acceptance.

**FS-REV2-015 — Worker boundaries**
Workers may perform bounded search, implementation and validation but may not independently redefine scope or locked architecture.

**FS-REV2-016 — Multi-dimensional coverage**
Completeness is measured across requirements, states, data, permissions, responsive, accessibility and QA dimensions.

**FS-REV2-017 — Provenance required**
Every externally derived production artifact must have traceable provenance and license/security assessment.

**FS-REV2-018 — Mobile first-class path**
Mobile Frontend Studio uses platform-appropriate component sources and runtime/device validation rather than treating mobile as resized web.

**FS-REV2-019 — Golden regression governance**
Visual baselines are controlled evidence and cannot be changed merely to make tests pass.

**FS-REV2-020 — No silent omission**
No project feature, screen, state or acceptance obligation may be silently omitted or thinly implemented.

---

# PART XXI — Immediate Resume Directive

## 72. How an implementing manager must use this document

An implementing Manager/Orchestrator must not begin by rewriting Frontend Studio from assumptions. It must:

1. read the actual current DDE source-of-truth documents and implementation state;
2. inventory the current repository and identify the exact Frontend Studio and shared UI files;
3. map the existing implementation against every relevant Rev 2 domain;
4. preserve working functionality unless explicitly superseded;
5. create/update the Frontend Contract and PXG foundation before feature-completeness claims;
6. implement the shared shell and golden visual system through reusable primitives;
7. migrate Frontend Studio incrementally behind verification gates;
8. implement source adapters through common contracts rather than provider-specific hacks;
9. keep candidate work isolated;
10. prove each phase with deterministic checks, screenshots and coverage evidence;
11. migrate the remaining DDE windows only after shared primitives are stable;
12. update implementation-state and decision-log documents continuously.

The manager is expected to continue autonomously through unblocked implementation phases, stopping only for decisions that genuinely require user authority, hard external credentials/access, or an irreconcilable source-of-truth conflict.

---

## 73. Final canonical statement

DDE Frontend Studio is a **quality-governed product-experience engineering system**. Its purpose is not simply to make interfaces attractive or to let an AI edit React code. Its purpose is to ensure that the complete intended product experience is modeled, sourced, designed, implemented, tested, preserved and evolved without silent omissions, uncontrolled design drift or untraceable external dependencies.

The approved Frontend Studio image defines how that system looks. The Product Experience Graph and Frontend Contract define what it must contain. The mutation, lock, candidate, provenance and QA systems define how it may change. The Project Manager/Orchestrator remains accountable for the final outcome.
