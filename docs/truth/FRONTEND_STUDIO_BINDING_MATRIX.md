# DDE Frontend Studio — functional binding matrix

<!-- GENERATED FILE. Edit `docs/truth/golden/frontend_binding_matrix.json` and run `uv run python -m scripts.render_binding_matrix`. -->

**Authority:** docs/truth/FRONTEND_STUDIO_REV3.md section 8 (Golden UI - quantum functional binding map); AD-035; AD-036

**Closure rule:** At DDE-069 closure no row may be UI_ONLY, and no mandatory row may be UNBOUND. A row that is TYPED_UNAVAILABLE must carry a note naming why the capability is absent and what would close it.

## Ledger state

| Status | Rows |
|---|---:|
| `UNBOUND` | 39 |
| `TYPED_UNAVAILABLE` | 22 |
| `BOUND` | 0 |
| `VERIFIED` | 38 |
| **total** | **99** |

## Global top bar

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#81-global-top-bar`

| ID | Feature | Visual contract | Read model | Command | State transition | Capability | Permission | Failure states | Implementation | Tests | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TB-01 | Product title / module identity | Left of top bar, 58px band, 15-16px 600 weight | `shell.module_registry` | — | — | — | any authenticated principal | `MODULE_UNKNOWN` | `interfaces/dde-studio/ui/src/shell/DdeShell.tsx` `interfaces/dde-studio/ui/src/shell/GlobalTopBar.tsx` `interfaces/dde-studio/ui/src/styles/global.css` `interfaces/dde-studio/ui/src/styles/tokens.css` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `VERIFIED` |
| TB-02 | Project selector | Active ProjectIdentity chip beside title | `FrontendStudioSnapshot.project` | `frontend.project.switch` | active project changes | — | principal grant on target project | `NO_PROJECT` `PROJECT_UNAVAILABLE` `SCOPE_DENIED` | `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/GlobalTopBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `UNBOUND` |
| TB-03 | Saved timestamp | 12px tertiary text next to sync chip | `StudioSyncSnapshot.durable_revision_at` | — | — | — | project read | `UNKNOWN` | — | — | `UNBOUND` |
| TB-04 | Sync status chip | Pill; colour by state | `StudioSyncSnapshot.state` | — | LOCAL_PENDING->COMMAND_ACCEPTED->PERSISTING->DURABLE->PROJECTING->SYNCED | — | project read | `FAILED` `STALE` `OFFLINE` `CONFLICT` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/GlobalTopBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `TYPED_UNAVAILABLE` |
| TB-05 | Design mode tab | Centre tab row, selected tab tinted | `FrontendStudioSnapshot.mode` | `frontend.mode.select` | studio mode transition | — | project read | — | `interfaces/dde-studio/ui/src/shell/GlobalTopBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `VERIFIED` |
| TB-06 | Coverage mode tab | Same tab row | `CoverageSummary` | `frontend.mode.select` | studio mode transition | — | project read | `COVERAGE_UNASSESSED` | `engine/studio/coverage/scoring.py` `engine/studio/coverage/service.py` `interfaces/dde-studio/ui/src/shell/GlobalTopBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_coverage_engine.py` `tests/unit/test_frontend_studio_characterization_postgres.py` `tests/unit/test_frontend_studio_domain_postgres.py` | `VERIFIED` |
| TB-07 | Architecture mode tab | Same tab row | `PxgGraphSnapshot` | `frontend.mode.select` | studio mode transition | — | project read | `PXG_EMPTY` | `interfaces/dde-studio/ui/src/shell/GlobalTopBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `VERIFIED` |
| TB-08 | QA mode tab | Same tab row | `QaFindingInventory` | `frontend.mode.select` | studio mode transition | — | project read | `VERIFICATION_UNAVAILABLE` | `interfaces/dde-studio/ui/src/shell/GlobalTopBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `VERIFIED` |
| TB-09 | Source mode tab | Same tab row | `DesignSourceInventory` | `frontend.mode.select` | studio mode transition | — | project read | `PROVIDER_DEGRADED` | `interfaces/dde-studio/ui/src/shell/GlobalTopBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `VERIFIED` |
| TB-10 | Coverage ring | Right-aligned ring + percentage | `CoverageSummary.weighted_percent` | — | — | — | project read | `UNASSESSED` `BLOCKED` `PARTIAL` | `engine/studio/coverage/scoring.py` `engine/studio/coverage/service.py` `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/GlobalTopBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_coverage_engine.py` `tests/unit/test_frontend_studio_characterization_postgres.py` `tests/unit/test_frontend_studio_domain_postgres.py` | `VERIFIED` |
| TB-11 | Activity / metrics icon | Icon button | `FrontendActivityProjection` | — | — | — | project read | `NOT_ADMITTED` | — | — | `UNBOUND` |
| TB-12 | Attention notification badge | Count badge on bell icon | `AttentionCenterSnapshot` | `frontend.attention.acknowledge` | attention item acknowledged | — | project read | `UNKNOWN_NOT_SHOWN_AS_COUNT` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/GlobalTopBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `VERIFIED` |
| TB-13 | Help | Icon button | `shell.help_registry` | — | — | — | any authenticated principal | — | — | — | `UNBOUND` |
| TB-14 | User avatar / principal | Circular avatar at far right | `session.principal` | — | — | — | own session | `UNAUTHENTICATED` | — | — | `UNBOUND` |

Notes:

- **TB-04** — StudioSyncSnapshot distinguishes durable revision from accepted command, but pending-mutation counting needs the DDE-069 M7 mutation engine; until then the chip must not claim SYNCED on a 202 alone.

## App rail and project explorer

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#82-app-rail-and-project-explorer`

| ID | Feature | Visual contract | Read model | Command | State transition | Capability | Permission | Failure states | Implementation | Tests | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| EX-01 | App rail module icons | 44-48px rail, tinted rounded square on selected | `shell.module_registry` | `shell.module.select` | active module changes | — | module grant | `MODULE_UNAVAILABLE` | `interfaces/dde-studio/ui/src/shell/AppRail.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `VERIFIED` |
| EX-02 | Project heading + menu | 215-225px panel header row | `ProjectExplorerSnapshot.project` | — | — | — | project read | — | `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `VERIFIED` |
| EX-03 | Explorer search | Search icon in header row | `ProjectExplorerSnapshot (filtered)` | — | — | — | project read | `INDEX_UNAVAILABLE` | — | — | `UNBOUND` |
| EX-04 | Screens group + count | Collapsible group, 11px numeric counter | `ScreenTreeSnapshot` | — | — | — | project read | `UNKNOWN` `EMPTY` `LOAD_FAILED` | `engine/studio/pxg/service.py` `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `VERIFIED` |
| EX-05 | Journeys group + count | Same | `JourneyInventory` | — | — | — | project read | `UNKNOWN` `EMPTY` `LOAD_FAILED` | `engine/studio/pxg/service.py` `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `VERIFIED` |
| EX-06 | Components group + count | Same | `ComponentInventory` | — | — | — | project read | `UNKNOWN` `EMPTY` `LOAD_FAILED` | `engine/studio/pxg/service.py` `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `VERIFIED` |
| EX-07 | Sources group | Collapsible group | `DesignSourceInventory` | — | — | — | project read | `PROVIDER_DEGRADED` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `TYPED_UNAVAILABLE` |
| EX-08 | DDE Library source | Nested item + status dot | `DesignSourceInventory[internal]` | `frontend.source.search` | source search run | `capability.frontend_source_search` | project read | `UNAVAILABLE` `EMPTY` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `TYPED_UNAVAILABLE` |
| EX-09 | 21st MCP source | Nested item + status dot | `DesignSourceInventory[twentyfirst]` | `frontend.source.search` | source search run | `capability.frontend_source_search` | project read + external egress admission | `AUTH_REQUIRED` `PROVIDER_OFFLINE` `NOT_ADMITTED` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `TYPED_UNAVAILABLE` |
| EX-10 | Donor Sources | Nested item + status dot | `DesignSourceInventory[donor]` | `frontend.donors.run_discovery` | donor discovery run | `capability.donor_search` | donor_reuse approval for adoption | `APPROVAL_REQUIRED` `SOURCE_CLASS_FORBIDS` | — | — | `UNBOUND` |
| EX-11 | Internal Components | Nested item + count | `ComponentInventory[project_native]` | — | — | — | project read | `EMPTY` | — | — | `UNBOUND` |
| EX-12 | Source numeric badges | 11px counter or em-dash | `DesignSourceInventory[*].indexed_count` | — | — | — | project read | `UNKNOWN` `STALE` `ERROR` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `TYPED_UNAVAILABLE` |
| EX-13 | Templates group | Collapsible group | `TemplateInventory` | `frontend.source.import_candidate` | foundation candidate created | — | project read | `EMPTY` `PROVIDER_DEGRADED` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `TYPED_UNAVAILABLE` |
| EX-14 | Template entries | Nested neutral-identity items | `TemplateInventory.entries` | — | — | — | project read | `EMPTY` | — | — | `UNBOUND` |
| EX-15 | Locks group + count | Collapsible group + counter | `LockInventory` | — | — | — | project read | `UNKNOWN` | `engine/studio/locks/resolution.py` `engine/studio/locks/service.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `VERIFIED` |
| EX-16 | Style Locks | Nested item + count | `LockInventory[STYLE]` | `frontend.lock.create|update|remove` | lock lifecycle | — | lock authority | `LOCK_DENIED` | `engine/studio/locks/service.py` `engine/studio/locks/resolution.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` | `VERIFIED` |
| EX-17 | Section Locks | Nested item + count | `LockInventory[SECTION]` | `frontend.lock.create|update|remove` | lock lifecycle | — | lock authority | `LOCK_DENIED` | `engine/studio/locks/service.py` `engine/studio/locks/resolution.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` | `VERIFIED` |
| EX-18 | Component Locks | Nested item + count | `LockInventory[COMPONENT]` | `frontend.lock.create|update|remove` | lock lifecycle | — | lock authority | `LOCK_DENIED` | `engine/studio/locks/service.py` `engine/studio/locks/resolution.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` | `VERIFIED` |
| EX-19 | Behaviour Locks | Nested item + count | `LockInventory[BEHAVIOUR]` | `frontend.lock.create|update|remove` | lock lifecycle | — | lock authority | `LOCK_DENIED` | `engine/studio/locks/service.py` `engine/studio/locks/resolution.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` | `VERIFIED` |
| EX-20 | QA group | Collapsible group | `QaFindingInventory` | — | — | — | project read | `VERIFICATION_UNAVAILABLE` | — | — | `UNBOUND` |
| EX-21 | QA Issues count | Nested item + count | `QaFindingInventory.unresolved` | — | — | — | project read | `UNKNOWN` | — | — | `UNBOUND` |
| EX-22 | Accessibility count | Nested item + count | `QaFindingInventory[accessibility]` | — | — | — | project read | `NOT_EVALUATED` | `engine/studio/acceptance/defaults.py` `engine/studio/acceptance/service.py` `schemas/design/screen_acceptance_defaults.json` | `tests/unit/test_screen_acceptance_binding.py` `tests/unit/test_screen_acceptance_binding_postgres.py` | `TYPED_UNAVAILABLE` |

Notes:

- **EX-07** — DesignSourceRegistry is DDE-069 M8. The explorer group is listed with an UNKNOWN count (Availability.NOT_IMPLEMENTED) rather than hidden or shown as zero.
- **EX-08** — Internal source adapter is DDE-069 M8; the group reports NOT_IMPLEMENTED.
- **EX-09** — 21st adapter is DDE-069 M8; the group reports NOT_IMPLEMENTED.
- **EX-12** — Source inventories are DDE-069 M8; badges render an em-dash from CountValue.unknown rather than a fabricated number.
- **EX-13** — TemplateRecommendationService is DDE-069 M8; the group reports NOT_IMPLEMENTED.
- **EX-22** — Generated screens now carry mandatory visual_critique bindings whose rubric includes accessibility, so evidence has a real producer; the QaFindingInventory read that aggregates it is DDE-069 M17. Until then the badge renders Not evaluated rather than a fabricated AA.

## Orchestrator card

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#83-orchestrator-card`

| ID | Feature | Visual contract | Read model | Command | State transition | Capability | Permission | Failure states | Implementation | Tests | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| OR-01 | Orchestrator status | Bottom card of explorer, status dot | `OrchestratorFrontendStatus.runtime_state` | — | ACTIVE\|PAUSED\|WAITING\|DEGRADED\|UNKNOWN | — | project read | `UNKNOWN` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `TYPED_UNAVAILABLE` |
| OR-02 | Manager Chair identity | Name row inside card | `OrchestratorFrontendStatus.manager_chair` | — | — | — | project read | `SERVING_UNKNOWN` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `TYPED_UNAVAILABLE` |
| OR-03 | Desired/Configured/Serving split | Three distinct labelled values | `OrchestratorFrontendStatus.model_roles` | — | — | — | project read | `SERVING_UNATTESTED` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `TYPED_UNAVAILABLE` |
| OR-04 | Design Director role | Subordinate role row | `OrchestratorFrontendStatus.design_director` | — | — | — | project read | `UNASSIGNED` | — | — | `UNBOUND` |
| OR-05 | Activity visualisation | Compact waveform of real events | `OrchestratorFrontendStatus.activity_window` | — | — | — | project read | `NO_ACTIVITY` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `TYPED_UNAVAILABLE` |
| OR-06 | Status dot | Colour by typed health | `OrchestratorFrontendStatus.health` | — | — | — | project read | `UNKNOWN` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `TYPED_UNAVAILABLE` |

Notes:

- **OR-01** — No orchestrator runtime is wired to the Studio; runtime_state is UNKNOWN rather than a decorative ACTIVE dot.
- **OR-02** — Manager-chair identity has no backing projection yet; the card shows no name.
- **OR-03** — Blueprint Rev 3 section 5.4 ModelServingEvidence is unimplemented, so serving_confidence is UNATTESTED and desired/configured/serving stay separate and empty.
- **OR-05** — No frontend activity projection exists; the count is UNKNOWN, not a random waveform.
- **OR-06** — Role health has no backing projection; the dot renders UNKNOWN.

## Canvas toolbar

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#84-canvas-toolbar`

| ID | Feature | Visual contract | Read model | Command | State transition | Capability | Permission | Failure states | Implementation | Tests | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CT-01 | Viewport selector | Compact select, e.g. Desktop 1440 | `PreviewViewportState` | `frontend.preview.set_state` | viewport changes | — | project read | — | `interfaces/dde-studio/ui/src/frontend-studio/FrontendStudioWorkspace.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `VERIFIED` |
| CT-02 | Select tool | Icon toggle | `editor.interaction_mode` | — | SELECT mode | — | project read | — | — | — | `UNBOUND` |
| CT-03 | Hand / pan tool | Icon toggle | `editor.interaction_mode` | — | PAN mode | — | project read | — | — | — | `UNBOUND` |
| CT-04 | Comment tool | Icon toggle | `DesignCommentInventory` | `frontend.comment.create|resolve` | comment lifecycle | — | project read | `ANCHOR_LOST` | — | — | `UNBOUND` |
| CT-05 | Grid / overlay options | Icon toggle + menu | `PreviewOverlayState` | `frontend.preview.set_state` | overlay toggles | — | project read | — | — | — | `UNBOUND` |
| CT-06 | Claude /design button | Accent AI-action button in toolbar | `DesignProviderStatus` | `frontend.design.request` | DesignSession + DesignArtifacts created | `capability.frontend_design_request` | design provider admission | `PROVIDER_AUTH_REQUIRED` `PROVIDER_UNAVAILABLE` `CAPABILITY_UNAVAILABLE` `ARTIFACT_REJECTED` | `interfaces/dde-studio/ui/src/frontend-studio/FrontendStudioWorkspace.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `TYPED_UNAVAILABLE` |
| CT-07 | Zoom control | Percentage stepper | `editor.canvas_transform` | — | — | — | project read | — | `interfaces/dde-studio/ui/src/frontend-studio/FrontendStudioWorkspace.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `VERIFIED` |
| CT-08 | Fullscreen / fit | Icon buttons | `editor.presentation_state` | — | — | — | project read | `HOST_UNSUPPORTED` | — | — | `UNBOUND` |

Notes:

- **CT-06** — The control is present in the canvas toolbar exactly where the golden composition puts it, rendered disabled with the reason on the element. DesignGateway and a certified provider are DDE-069 M10; a button that opened a generic chat would be the theatre the mission forbids.

## Real canvas and selection

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#85-real-canvas-and-selection`

| ID | Feature | Visual contract | Read model | Command | State transition | Capability | Permission | Failure states | Implementation | Tests | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CV-01 | Live preview surface | Dominant central area, code-backed | `FrontendCanvasSnapshot` | `frontend.preview.start|stop` | DESIGN\|BUILDING\|LIVE\|PROMOTED\|VERIFIED\|DISCARDED | `capability.frontend_preview` | project read | `RENDER_FAILED` `BUILD_FAILED` `RUNTIME_UNAVAILABLE` | `interfaces/dde-studio/ui/src/frontend-studio/FrontendStudioWorkspace.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `TYPED_UNAVAILABLE` |
| CV-02 | LIVE badge | Small pill on canvas chrome | `FrontendCanvasSnapshot.preview_badge` | — | LIVE only with revision+build+runtime+route | — | project read | `DESIGN_ONLY` `BUILDING` `UNHEALTHY` | `interfaces/dde-studio/ui/src/frontend-studio/FrontendStudioWorkspace.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `TYPED_UNAVAILABLE` |
| CV-03 | Route / screen navigation | Breadcrumb + in-preview routing | `ScreenTreeSnapshot + PreviewRuntime route` | `frontend.preview.set_state` | route change | — | project read | `ROUTE_UNKNOWN` | `engine/studio/pxg/service.py` `engine/studio/reads.py` `engine/studio/reads.py` | `tests/unit/test_frontend_studio_domain_postgres.py` | `VERIFIED` |
| CV-04 | Selection outline | Indigo outline on selected node | `PreviewSelectionAnchor` | — | selection changes | — | project read | `SOURCE_MAPPING_UNAVAILABLE` | — | — | `UNBOUND` |
| CV-05 | Resize handles | Corner/edge handles on selection | `InspectorDescriptor (layout group)` | `frontend.mutation.plan|apply` | mutation planned then applied to candidate | — | mutation authority | `LOCK_DENIED` `STALE_REVISION` `MUTATION_INVALID` | `engine/studio/mutations/planner.py` `engine/studio/mutations/executor.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `VERIFIED` |
| CV-06 | Section lock chip | Chip on locked region | `LockInventory (effective)` | — | — | — | project read | — | `engine/studio/locks/service.py` `engine/studio/locks/resolution.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` | `VERIFIED` |
| CV-07 | Style lock chip | Chip on style-locked node | `LockInventory (effective)` | — | — | — | project read | — | `engine/studio/locks/service.py` `engine/studio/locks/resolution.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` | `VERIFIED` |
| CV-08 | State simulation controls | Overlay control for loading/empty/error/role | `PreviewScenarioState` | `frontend.preview.set_state` | scenario change | — | project read | `SCENARIO_UNSUPPORTED` | — | — | `UNBOUND` |

Notes:

- **CV-01** — The canvas region exists with the correct dominance and toolbar; the code-backed preview runtime is DDE-069 M9. Showing a screenshot here would violate the LIVE-badge rule (section 9.3).
- **CV-02** — No LIVE badge is rendered because nothing satisfies its five conditions (revision + build + runtime + health + route). DDE-069 M9.

## Frontend Chat composer

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#86-frontend-chat-composer`

| ID | Feature | Visual contract | Read model | Command | State transition | Capability | Permission | Failure states | Implementation | Tests | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CH-01 | Chat composer | Permanent floating composer, 10-12px radius | `FrontendConversation` | `frontend.chat.send` | conversation turn appended | — | project read | `PROVIDER_UNAVAILABLE` `APPROVAL_REQUIRED` | — | — | `UNBOUND` |
| CH-02 | Selection-aware context chips | Removable chips above composer | `DesignEditContext` | — | planned scope changes | — | project read | `REFERENCE_UNRESOLVED` | — | — | `UNBOUND` |
| CH-03 | Context/scope settings | Slider/settings icon | `FrontendConversation.context_policy` | — | — | — | project read | — | — | — | `UNBOUND` |
| CH-04 | Send | Primary action button | `IntentRouterDecision` | `frontend.chat.send` | intent routed | — | project read | `INTENT_AMBIGUOUS` | — | — | `UNBOUND` |
| CH-05 | Reference resolution (this/Candidate B) | Inline resolved reference | `FrontendConversation.selected_node_ids` | — | — | — | project read | `AMBIGUOUS_REFERENCE` | — | — | `UNBOUND` |
| CH-06 | Design-class intent routing | Routed to DesignGateway | `DesignSessionReadModel` | `frontend.design.request|refine` | design artifacts created | `capability.frontend_design_request` | design provider admission | `PROVIDER_UNAVAILABLE` `AUTH_REQUIRED` | — | — | `UNBOUND` |
| CH-07 | Deterministic edit routing | Routed to MutationPlanner, no model call | `MutationPlan` | `frontend.mutation.plan|apply` | candidate mutated | — | mutation authority | `LOCK_DENIED` `STALE_REVISION` | `engine/studio/mutations/planner.py` `engine/studio/mutations/executor.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `VERIFIED` |
| CH-08 | Undo / revert | Chat command + inspector action | `MutationHistory` | `frontend.mutation.revert` | candidate rolled back | — | mutation authority | `NOT_REVERTIBLE` | `engine/studio/mutations/planner.py` `engine/studio/mutations/executor.py` | `tests/unit/test_frontend_mutation_engine_postgres.py` | `VERIFIED` |

## Candidate / Directions dock

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#87-candidatedirections-dock`

| ID | Feature | Visual contract | Read model | Command | State transition | Capability | Permission | Failure states | Implementation | Tests | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CA-01 | Candidate cards | Bottom strip cards with thumbnails | `CandidateBoardSnapshot` | `frontend.candidate.create` | candidate lifecycle | — | project read | `EMPTY` `GENERATING` `FAILED` | `engine/studio/candidates/service.py` `engine/studio/candidates/lifecycle.py` | `tests/unit/test_frontend_mutation_engine_postgres.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `VERIFIED` |
| CA-02 | Candidate thumbnail | Rendered candidate screenshot | `CandidateBoardSnapshot[].thumbnail_ref` | — | — | `capability.browser` | project read | `NOT_RENDERED` `RENDER_FAILED` | `engine/studio/candidates/service.py` `engine/studio/candidates/lifecycle.py` | `tests/unit/test_frontend_mutation_engine_postgres.py` | `TYPED_UNAVAILABLE` |
| CA-03 | Candidate score | Numeric score or 'Not scored' | `CandidateScorecard` | — | — | — | project read | `UNSCORED` `PARTIAL` | `engine/studio/candidates/service.py` `engine/studio/candidates/lifecycle.py` | `tests/unit/test_frontend_mutation_engine_postgres.py` | `TYPED_UNAVAILABLE` |
| CA-04 | Score classification | Good/Medium chip, clickable explanation | `CandidateScorecard.classification` | — | — | — | project read | `UNSCORED` | `engine/studio/candidates/service.py` `engine/studio/candidates/lifecycle.py` | `tests/unit/test_frontend_mutation_engine_postgres.py` | `TYPED_UNAVAILABLE` |
| CA-05 | Change count | 'N changes' from real structural diff | `MutationPlan delta` | — | — | — | project read | `UNKNOWN` | `engine/studio/mutations/projection.py` `engine/studio/mutations/planner.py` `engine/studio/mutations/executor.py` | `tests/unit/test_frontend_mutation_engine_postgres.py` | `VERIFIED` |
| CA-06 | Current (Locked) card | Accepted revision card with lock chip | `AcceptedDesignRevision` | — | — | — | project read | — | `engine/studio/candidates/service.py` `engine/studio/candidates/lifecycle.py` `engine/studio/mutations/projection.py` | `tests/unit/test_frontend_mutation_engine_postgres.py` | `VERIFIED` |
| CA-07 | Try live | Card action button | `CandidateWorkspace` | `frontend.design.try_live` | artifact -> isolated candidate workspace | `capability.frontend_candidate` | mutation authority | `BUILD_FAILED` `WORKTREE_CONFLICT` | `engine/studio/candidates/service.py` `engine/studio/candidates/lifecycle.py` | `tests/unit/test_frontend_mutation_engine_postgres.py` | `TYPED_UNAVAILABLE` |
| CA-08 | Compare | Card action; side-by-side real renders | `CandidateBoardSnapshot (compare mode)` | — | — | — | project read | `NOT_RENDERED` | `engine/studio/candidates/service.py` `engine/studio/candidates/lifecycle.py` | `tests/unit/test_frontend_mutation_engine_postgres.py` | `TYPED_UNAVAILABLE` |
| CA-09 | Promote / accept | Card action; governed gate | `FrontendAcceptanceRecord` | `frontend.candidate.promote` | candidate -> accepted revision | `capability.frontend_candidate` | manager acceptance authority | `PROMOTION_DENIED` `VERIFICATION_FAILED` `CRITIC_UNAVAILABLE` `STALE_REVISION` `LOCK_DENIED` | `engine/studio/candidates/promotion.py` | `tests/unit/test_frontend_mutation_engine_postgres.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `VERIFIED` |

Notes:

- **CA-02** — Thumbnails require the preview runtime (DDE-069 M9); the card shows a typed NOT_RENDERED state.
- **CA-03** — No CandidateScorecard exists; DDE-069 M8/M17 work. Cards render 'Not scored' rather than a fabricated percentage (FRONTEND_STUDIO_REV3 section 17.2 forbids hardcoded 84/76/92).
- **CA-04** — Classification derives from a score that does not exist yet; the chip renders 'Not scored'.
- **CA-07** — Try live requires the candidate preview runtime (DDE-069 M9); the action is disabled with a typed reason.
- **CA-08** — Compare requires two rendered candidates (DDE-069 M9).

## Source Blend

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#88-source-blend`

| ID | Feature | Visual contract | Read model | Command | State transition | Capability | Permission | Failure states | Implementation | Tests | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SB-01 | Actual attribution | Named sources with computed percentages | `SourceBlendSnapshot.attribution` | — | — | — | project read | `ATTRIBUTION_UNCOMPUTABLE` | — | — | `UNBOUND` |
| SB-02 | Target blend slider | Generation preference control | `SourceBlendTarget` | `frontend.design.request (blend target)` | next generation preference recorded | — | project read | — | — | — | `UNBOUND` |

## Inspector

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#89-inspector`

| ID | Feature | Visual contract | Read model | Command | State transition | Capability | Permission | Failure states | Implementation | Tests | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| IN-01 | Selected node header | 310-325px panel header, stable selection | `PreviewSelectionAnchor` | — | — | — | project read | `NO_SELECTION` `SOURCE_MAPPING_UNAVAILABLE` | `interfaces/dde-studio/ui/src/frontend-studio/InspectorPanel.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `TYPED_UNAVAILABLE` |
| IN-02 | Layout tab | Descriptor group tab | `InspectorDescriptor[layout]` | `frontend.mutation.plan|apply` | layout mutation | — | mutation authority | `UNSUPPORTED_PROPERTY` `LOCK_DENIED` | `engine/studio/mutations/planner.py` `engine/studio/mutations/executor.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` | `VERIFIED` |
| IN-03 | Style tab | Descriptor group tab | `InspectorDescriptor[style]` | `frontend.mutation.plan|apply` | style mutation | — | mutation authority | `UNSUPPORTED_PROPERTY` `LOCK_DENIED` `OFF_TOKEN_REFUSED` | `engine/studio/mutations/planner.py` `engine/studio/mutations/executor.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `VERIFIED` |
| IN-04 | Behaviour tab | Descriptor group tab | `InspectorDescriptor[behavior]` | `frontend.mutation.plan|apply` | behaviour mutation | — | mutation authority | `UNSUPPORTED_PROPERTY` `LOCK_DENIED` | — | — | `UNBOUND` |
| IN-05 | Responsive tab | Descriptor group tab | `InspectorDescriptor[responsive]` | `frontend.mutation.plan|apply` | responsive rule mutation | — | mutation authority | `UNSUPPORTED_PROPERTY` | — | — | `UNBOUND` |
| IN-06 | Lock tab | Lock inventory + actions | `LockInventory (effective)` | `frontend.lock.create|update|remove` | lock lifecycle | — | lock authority | `LOCK_DENIED` | `engine/studio/locks/service.py` `engine/studio/locks/resolution.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `VERIFIED` |
| IN-07 | Source / code tab | Read-only source mapping + reveal | `SourceMappingSnapshot` | — | — | — | source read policy | `SOURCE_MAPPING_UNAVAILABLE` `ACCESS_DENIED` | — | — | `UNBOUND` |
| IN-08 | Type: Stack | Enum descriptor control | `InspectorDescriptor[layout].type` | `frontend.mutation.apply` | layout type mutation | — | mutation authority | `UNSUPPORTED_PROPERTY` | — | — | `UNBOUND` |
| IN-09 | Direction | Enum descriptor control | `InspectorDescriptor[layout].direction` | `frontend.mutation.apply` | layout direction mutation | — | mutation authority | `UNSUPPORTED_PROPERTY` | — | — | `UNBOUND` |
| IN-10 | Gap (px + token) | '24 px  space-6' dual display | `InspectorDescriptor[layout].gap` | `frontend.mutation.apply` | token-bound spacing mutation | — | mutation authority | `OFF_TOKEN_REFUSED` | `engine/studio/mutations/planner.py` `engine/studio/mutations/executor.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `VERIFIED` |
| IN-11 | Padding (px + token) | Same dual display | `InspectorDescriptor[layout].padding` | `frontend.mutation.apply` | token-bound spacing mutation | — | mutation authority | `OFF_TOKEN_REFUSED` | `engine/studio/mutations/planner.py` `engine/studio/mutations/executor.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `VERIFIED` |
| IN-12 | Behaviour: animation | Tokenised motion reference control | `InspectorDescriptor[behavior].animation` | `frontend.motion.set_animation` | motion mutation | — | mutation authority | `OFF_TOKEN_REFUSED` | — | — | `UNBOUND` |
| IN-13 | Provenance section | Source artifact, licence, security state | `ProvenanceRecord` | — | — | — | provenance read | `UNKNOWN_PROVENANCE` `LICENCE_UNKNOWN` | — | — | `UNBOUND` |
| IN-14 | View Source | Reveal-file action | `SourceFileRef` | — | — | — | source read policy | `ACCESS_DENIED` `SOURCE_MAPPING_UNAVAILABLE` | — | — | `UNBOUND` |
| IN-15 | Accessibility badge | AA / findings / Not evaluated | `QaFindingInventory[accessibility]` | — | — | — | project read | `NOT_EVALUATED` | `engine/studio/acceptance/defaults.py` `engine/studio/acceptance/service.py` `schemas/design/screen_acceptance_defaults.json` | `tests/unit/test_screen_acceptance_binding.py` `tests/unit/test_screen_acceptance_binding_postgres.py` | `TYPED_UNAVAILABLE` |
| IN-16 | Responsive breakpoint buttons | Segmented control | `PreviewViewportState` | `frontend.preview.set_state` | viewport + responsive rule set change | — | project read | — | — | — | `UNBOUND` |

Notes:

- **IN-01** — The inspector panel exists at the locked width with a designed no-selection state. Stable selection needs the preview instrumentation layer (DDE-069 M9); the mutation path it would drive is already real and governed.
- **IN-15** — Same as EX-22: the accessibility rubric dimension is bound by default, but the inspector's read of its result is M17. Renders Not evaluated.

## Status bar

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#810-status-bar`

| ID | Feature | Visual contract | Read model | Command | State transition | Capability | Permission | Failure states | Implementation | Tests | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ST-01 | Breadcrumb | 32-36px bar, selected path from PXG | `PxgGraphSnapshot path` | — | — | — | project read | `NO_SELECTION` | `engine/studio/pxg/service.py` `engine/studio/reads.py` `interfaces/dde-studio/ui/src/shell/StatusBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `VERIFIED` |
| ST-02 | Error count | 'No errors' / count | `QaFindingInventory.blocking` | — | — | — | project read | `UNKNOWN` | `engine/studio/coverage/scoring.py` `engine/studio/coverage/service.py` `engine/studio/reads.py` `interfaces/dde-studio/ui/src/shell/StatusBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_coverage_engine.py` `tests/unit/test_frontend_studio_domain_postgres.py` | `VERIFIED` |
| ST-03 | Warning count | 'N warnings' | `QaFindingInventory.warnings` | — | — | — | project read | `UNKNOWN` | — | — | `UNBOUND` |
| ST-04 | Auto Layout state | ON/OFF toggle | `EditorAssistState.auto_layout` | `frontend.editor.set_assist` | assist toggled | — | project read | — | — | — | `UNBOUND` |
| ST-05 | AI Suggest state | ON/OFF toggle | `EditorAssistState.ai_suggest` | `frontend.editor.set_assist` | assist toggled; suggestions never auto-mutate accepted design | — | project read | `PROVIDER_UNAVAILABLE` | — | — | `UNBOUND` |
| ST-06 | Build / version | Studio build + project revision | `StudioSyncSnapshot.build` | — | — | — | any authenticated principal | `UNKNOWN` | `interfaces/dde-studio/ui/src/shell/StatusBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `VERIFIED` |
