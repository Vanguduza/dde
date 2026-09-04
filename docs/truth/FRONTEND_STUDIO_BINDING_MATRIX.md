# DDE Frontend Studio — functional binding matrix

<!-- GENERATED FILE. Edit `docs/truth/golden/frontend_binding_matrix.json` and run `uv run python -m scripts.render_binding_matrix`. -->

**Authority:** docs/truth/FRONTEND_STUDIO_REV3.md section 8 (Golden UI - quantum functional binding map); AD-035; AD-036

**Closure rule:** A visible golden control is VERIFIED only when every applicable DOMAIN, READ, COMMAND, UI, WIRED, E2E and VISUAL layer is VERIFIED. UI and VISUAL are always applicable. TYPED_UNAVAILABLE is final only when no required layer is silently UNBOUND.

**Final status is derived:** every applicable DOMAIN / READ / COMMAND / UI / WIRED / E2E / VISUAL layer must be VERIFIED before the row is VERIFIED.

## Ledger state

| Status | Rows |
|---|---:|
| `UNBOUND` | 89 |
| `TYPED_UNAVAILABLE` | 9 |
| `BOUND` | 1 |
| `VERIFIED` | 0 |
| **total** | **99** |

## Global top bar

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#81-global-top-bar`

| ID | Feature | Visual contract | Read model | Command | Domain | Read | Command evidence | UI | Wired | E2E | Visual | Implementation | Tests | Final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TB-01 | Product title / module identity | Left of top bar, 58px band, 15-16px 600 weight | `shell.module_registry` | — | `NOT_APPLICABLE` | `BOUND` | `NOT_APPLICABLE` | `BOUND` | `NOT_APPLICABLE` | `NOT_APPLICABLE` | `BOUND` | `interfaces/dde-studio/ui/src/shell/DdeShell.tsx` `interfaces/dde-studio/ui/src/shell/GlobalTopBar.tsx` `interfaces/dde-studio/ui/src/styles/global.css` `interfaces/dde-studio/ui/src/styles/tokens.css` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `BOUND` |
| TB-02 | Project selector | Active ProjectIdentity chip beside title | `FrontendStudioSnapshot.project` | `frontend.project.switch` | `UNBOUND` | `BOUND` | `UNBOUND` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/GlobalTopBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `UNBOUND` |
| TB-03 | Saved timestamp | 12px tertiary text next to sync chip | `StudioSyncSnapshot.durable_revision_at` | — | `UNBOUND` | `UNBOUND` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| TB-04 | Sync status chip | Pill; colour by state | `StudioSyncSnapshot.state` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/GlobalTopBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `UNBOUND` |
| TB-05 | Design mode tab | Centre tab row, selected tab tinted | `FrontendStudioSnapshot.mode` | `frontend.mode.select` | `UNBOUND` | `BOUND` | `UNBOUND` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `interfaces/dde-studio/ui/src/shell/GlobalTopBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `UNBOUND` |
| TB-06 | Coverage mode tab | Same tab row | `CoverageSummary` | `frontend.mode.select` | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `engine/studio/coverage/scoring.py` `engine/studio/coverage/service.py` `interfaces/dde-studio/ui/src/shell/GlobalTopBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_coverage_engine.py` `tests/unit/test_frontend_studio_characterization_postgres.py` `tests/unit/test_frontend_studio_domain_postgres.py` | `UNBOUND` |
| TB-07 | Architecture mode tab | Same tab row | `PxgGraphSnapshot` | `frontend.mode.select` | `UNBOUND` | `BOUND` | `UNBOUND` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `interfaces/dde-studio/ui/src/shell/GlobalTopBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `UNBOUND` |
| TB-08 | QA mode tab | Same tab row | `QaFindingInventory` | `frontend.mode.select` | `UNBOUND` | `BOUND` | `UNBOUND` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `interfaces/dde-studio/ui/src/shell/GlobalTopBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `UNBOUND` |
| TB-09 | Source mode tab | Same tab row | `DesignSourceInventory` | `frontend.mode.select` | `UNBOUND` | `BOUND` | `UNBOUND` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `interfaces/dde-studio/ui/src/shell/GlobalTopBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `UNBOUND` |
| TB-10 | Coverage ring | Right-aligned ring + percentage | `CoverageSummary.weighted_percent` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `engine/studio/coverage/scoring.py` `engine/studio/coverage/service.py` `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/GlobalTopBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_coverage_engine.py` `tests/unit/test_frontend_studio_characterization_postgres.py` `tests/unit/test_frontend_studio_domain_postgres.py` | `UNBOUND` |
| TB-11 | Activity / metrics icon | Icon button | `FrontendActivityProjection` | — | `UNBOUND` | `UNBOUND` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| TB-12 | Attention notification badge | Count badge on bell icon | `AttentionCenterSnapshot` | `frontend.attention.acknowledge` | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/GlobalTopBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `UNBOUND` |
| TB-13 | Help | Icon button | `shell.help_registry` | — | `UNBOUND` | `UNBOUND` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| TB-14 | User avatar / principal | Circular avatar at far right | `session.principal` | — | `UNBOUND` | `UNBOUND` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |

Notes:

- **TB-04** — StudioSyncSnapshot distinguishes durable revision from accepted command, but pending-mutation counting needs the DDE-069 M7 mutation engine; until then the chip must not claim SYNCED on a 202 alone.

## App rail and project explorer

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#82-app-rail-and-project-explorer`

| ID | Feature | Visual contract | Read model | Command | Domain | Read | Command evidence | UI | Wired | E2E | Visual | Implementation | Tests | Final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EX-01 | App rail module icons | 44-48px rail, tinted rounded square on selected | `shell.module_registry` | `shell.module.select` | `UNBOUND` | `BOUND` | `UNBOUND` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `interfaces/dde-studio/ui/src/shell/AppRail.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `UNBOUND` |
| EX-02 | Project heading + menu | 215-225px panel header row | `ProjectExplorerSnapshot.project` | — | `UNBOUND` | `BOUND` | `NOT_APPLICABLE` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `UNBOUND` |
| EX-03 | Explorer search | Search icon in header row | `ProjectExplorerSnapshot (filtered)` | — | `UNBOUND` | `UNBOUND` | `NOT_APPLICABLE` | `BOUND` | `UNBOUND` | `UNBOUND` | `BOUND` | — | — | `UNBOUND` |
| EX-04 | Screens group + count | Collapsible group, 11px numeric counter | `ScreenTreeSnapshot` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `engine/studio/pxg/service.py` `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `UNBOUND` |
| EX-05 | Journeys group + count | Same | `JourneyInventory` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `engine/studio/pxg/service.py` `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `UNBOUND` |
| EX-06 | Components group + count | Same | `ComponentInventory` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `engine/studio/pxg/service.py` `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `UNBOUND` |
| EX-07 | Sources group | Collapsible group | `DesignSourceInventory` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `UNBOUND` |
| EX-08 | DDE Library source | Nested item + status dot | `DesignSourceInventory[internal]` | `frontend.source.search` | `VERIFIED` | `VERIFIED` | `BOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `UNBOUND` |
| EX-09 | 21st MCP source | Nested item + status dot | `DesignSourceInventory[twentyfirst]` | `frontend.source.search` | `VERIFIED` | `VERIFIED` | `BOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `UNBOUND` |
| EX-10 | Donor Sources | Nested item + status dot | `DesignSourceInventory[donor]` | `frontend.donors.run_discovery` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| EX-11 | Internal Components | Nested item + count | `ComponentInventory[project_native]` | — | `UNBOUND` | `UNBOUND` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| EX-12 | Source numeric badges | 11px counter or em-dash | `DesignSourceInventory[*].indexed_count` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `UNBOUND` |
| EX-13 | Templates group | Collapsible group | `TemplateInventory` | `frontend.source.import_candidate` | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `UNBOUND` |
| EX-14 | Template entries | Nested neutral-identity items | `TemplateInventory.entries` | — | `UNBOUND` | `UNBOUND` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| EX-15 | Locks group + count | Collapsible group + counter | `LockInventory` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `engine/studio/locks/resolution.py` `engine/studio/locks/service.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `UNBOUND` |
| EX-16 | Style Locks | Nested item + count | `LockInventory[STYLE]` | `frontend.lock.create|update|remove` | `VERIFIED` | `VERIFIED` | `BOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/locks/service.py` `engine/studio/locks/resolution.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` | `UNBOUND` |
| EX-17 | Section Locks | Nested item + count | `LockInventory[SECTION]` | `frontend.lock.create|update|remove` | `VERIFIED` | `VERIFIED` | `BOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/locks/service.py` `engine/studio/locks/resolution.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` | `UNBOUND` |
| EX-18 | Component Locks | Nested item + count | `LockInventory[COMPONENT]` | `frontend.lock.create|update|remove` | `VERIFIED` | `VERIFIED` | `BOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/locks/service.py` `engine/studio/locks/resolution.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` | `UNBOUND` |
| EX-19 | Behaviour Locks | Nested item + count | `LockInventory[BEHAVIOUR]` | `frontend.lock.create|update|remove` | `VERIFIED` | `VERIFIED` | `BOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/locks/service.py` `engine/studio/locks/resolution.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` | `UNBOUND` |
| EX-20 | QA group | Collapsible group | `QaFindingInventory` | — | `UNBOUND` | `UNBOUND` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| EX-21 | QA Issues count | Nested item + count | `QaFindingInventory.unresolved` | — | `UNBOUND` | `UNBOUND` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| EX-22 | Accessibility count | Nested item + count | `QaFindingInventory[accessibility]` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/acceptance/defaults.py` `engine/studio/acceptance/service.py` `schemas/design/screen_acceptance_defaults.json` | `tests/unit/test_screen_acceptance_binding.py` `tests/unit/test_screen_acceptance_binding_postgres.py` | `UNBOUND` |

Notes:

- **EX-07** — DesignSourceRegistry is DDE-069 M8. The explorer group is listed with an UNKNOWN count (Availability.NOT_IMPLEMENTED) rather than hidden or shown as zero.
- **EX-08** — Internal source adapter is DDE-069 M8; the group reports NOT_IMPLEMENTED.
- **EX-09** — 21st adapter is DDE-069 M8; the group reports NOT_IMPLEMENTED.
- **EX-12** — Source inventories are DDE-069 M8; badges render an em-dash from CountValue.unknown rather than a fabricated number.
- **EX-13** — TemplateRecommendationService is DDE-069 M8; the group reports NOT_IMPLEMENTED.
- **EX-22** — Generated screens now carry mandatory visual_critique bindings whose rubric includes accessibility, so evidence has a real producer; the QaFindingInventory read that aggregates it is DDE-069 M17. Until then the badge renders Not evaluated rather than a fabricated AA.

## Orchestrator card

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#83-orchestrator-card`

| ID | Feature | Visual contract | Read model | Command | Domain | Read | Command evidence | UI | Wired | E2E | Visual | Implementation | Tests | Final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OR-01 | Orchestrator status | Bottom card of explorer, status dot | `OrchestratorFrontendStatus.runtime_state` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `UNBOUND` |
| OR-02 | Manager Chair identity | Name row inside card | `OrchestratorFrontendStatus.manager_chair` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `UNBOUND` |
| OR-03 | Desired/Configured/Serving split | Three distinct labelled values | `OrchestratorFrontendStatus.model_roles` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `UNBOUND` |
| OR-04 | Design Director role | Subordinate role row | `OrchestratorFrontendStatus.design_director` | — | `UNBOUND` | `UNBOUND` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| OR-05 | Activity visualisation | Compact waveform of real events | `OrchestratorFrontendStatus.activity_window` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `UNBOUND` |
| OR-06 | Status dot | Colour by typed health | `OrchestratorFrontendStatus.health` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `engine/studio/reads.py` `interfaces/dde-studio/ui/src/components/Honest.tsx` `interfaces/dde-studio/ui/src/shell/ContextSidebar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `UNBOUND` |

Notes:

- **OR-01** — No orchestrator runtime is wired to the Studio; runtime_state is UNKNOWN rather than a decorative ACTIVE dot.
- **OR-02** — Manager-chair identity has no backing projection yet; the card shows no name.
- **OR-03** — Blueprint Rev 3 section 5.4 ModelServingEvidence is unimplemented, so serving_confidence is UNATTESTED and desired/configured/serving stay separate and empty.
- **OR-05** — No frontend activity projection exists; the count is UNKNOWN, not a random waveform.
- **OR-06** — Role health has no backing projection; the dot renders UNKNOWN.

## Canvas toolbar

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#84-canvas-toolbar`

| ID | Feature | Visual contract | Read model | Command | Domain | Read | Command evidence | UI | Wired | E2E | Visual | Implementation | Tests | Final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CT-01 | Viewport selector | Compact select, e.g. Desktop 1440 | `PreviewViewportState` | `frontend.preview.set_state` | `UNBOUND` | `BOUND` | `UNBOUND` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `interfaces/dde-studio/ui/src/frontend-studio/FrontendStudioWorkspace.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `UNBOUND` |
| CT-02 | Select tool | Icon toggle | `editor.interaction_mode` | — | `UNBOUND` | `UNBOUND` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| CT-03 | Hand / pan tool | Icon toggle | `editor.interaction_mode` | — | `UNBOUND` | `UNBOUND` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| CT-04 | Comment tool | Icon toggle | `DesignCommentInventory` | `frontend.comment.create|resolve` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| CT-05 | Grid / overlay options | Icon toggle + menu | `PreviewOverlayState` | `frontend.preview.set_state` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| CT-06 | Claude /design button | Accent AI-action button in toolbar | `DesignProviderStatus` | `frontend.design.request` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `VERIFIED` | `engine/studio/design/context.py` `engine/studio/design/gateway.py` `engine/studio/design/providers.py` `interfaces/dde-studio/ui/src/frontend-studio/FrontendStudioWorkspace.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_design_gateway_postgres.py` `tests/unit/test_frontend_chat_intent.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `TYPED_UNAVAILABLE` |
| CT-07 | Zoom control | Percentage stepper | `editor.canvas_transform` | — | `UNBOUND` | `BOUND` | `NOT_APPLICABLE` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `interfaces/dde-studio/ui/src/frontend-studio/FrontendStudioWorkspace.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `UNBOUND` |
| CT-08 | Fullscreen / fit | Icon buttons | `editor.presentation_state` | — | `UNBOUND` | `UNBOUND` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |

Notes:

- **CT-06** — The control is present where the golden composition puts it and the DesignGateway behind it is real: it compiles an allowlisted DesignEditContext, records the design-system hash, quarantines malformed artifacts and creates isolated candidates through Try live. What is absent is a certified Claude Design transport, so the provider reports NOT_CERTIFIED and the gateway refuses with no fallback. Driving it through capability.claude_code_invoke would be a generic code-generation prompt labelled /design, which section 23 forbids by name.

## Real canvas and selection

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#85-real-canvas-and-selection`

| ID | Feature | Visual contract | Read model | Command | Domain | Read | Command evidence | UI | Wired | E2E | Visual | Implementation | Tests | Final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CV-01 | Live preview surface | Dominant central area, code-backed | `FrontendCanvasSnapshot` | `frontend.preview.start|stop` | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `VERIFIED` | `interfaces/dde-studio/ui/src/frontend-studio/FrontendStudioWorkspace.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `TYPED_UNAVAILABLE` |
| CV-02 | LIVE badge | Small pill on canvas chrome | `FrontendCanvasSnapshot.preview_badge` | — | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `NOT_APPLICABLE` | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `VERIFIED` | `interfaces/dde-studio/ui/src/frontend-studio/FrontendStudioWorkspace.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `TYPED_UNAVAILABLE` |
| CV-03 | Route / screen navigation | Breadcrumb + in-preview routing | `ScreenTreeSnapshot + PreviewRuntime route` | `frontend.preview.set_state` | `VERIFIED` | `VERIFIED` | `BOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/pxg/service.py` `engine/studio/reads.py` `engine/studio/reads.py` | `tests/unit/test_frontend_studio_domain_postgres.py` | `UNBOUND` |
| CV-04 | Selection outline | Indigo outline on selected node | `PreviewSelectionAnchor` | — | `UNBOUND` | `UNBOUND` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| CV-05 | Resize handles | Corner/edge handles on selection | `InspectorDescriptor (layout group)` | `frontend.mutation.plan|apply` | `VERIFIED` | `VERIFIED` | `BOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/mutations/planner.py` `engine/studio/mutations/executor.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `UNBOUND` |
| CV-06 | Section lock chip | Chip on locked region | `LockInventory (effective)` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/locks/service.py` `engine/studio/locks/resolution.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` | `UNBOUND` |
| CV-07 | Style lock chip | Chip on style-locked node | `LockInventory (effective)` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/locks/service.py` `engine/studio/locks/resolution.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` | `UNBOUND` |
| CV-08 | State simulation controls | Overlay control for loading/empty/error/role | `PreviewScenarioState` | `frontend.preview.set_state` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |

Notes:

- **CV-01** — The canvas region exists with the correct dominance and toolbar; the code-backed preview runtime is DDE-069 M9. Showing a screenshot here would violate the LIVE-badge rule (section 9.3).
- **CV-02** — No LIVE badge is rendered because nothing satisfies its five conditions (revision + build + runtime + health + route). DDE-069 M9.

## Frontend Chat composer

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#86-frontend-chat-composer`

| ID | Feature | Visual contract | Read model | Command | Domain | Read | Command evidence | UI | Wired | E2E | Visual | Implementation | Tests | Final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CH-01 | Chat composer | Permanent floating composer, 10-12px radius | `FrontendConversation` | `frontend.chat.send` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/chat/intent.py` `engine/studio/chat/service.py` | `tests/unit/test_design_gateway_postgres.py` `tests/unit/test_frontend_chat_intent.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `UNBOUND` |
| CH-02 | Selection-aware context chips | Removable chips above composer | `DesignEditContext` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/chat/intent.py` `engine/studio/chat/service.py` | `tests/unit/test_design_gateway_postgres.py` `tests/unit/test_frontend_chat_intent.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `UNBOUND` |
| CH-03 | Context/scope settings | Slider/settings icon | `FrontendConversation.context_policy` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/chat/intent.py` `engine/studio/chat/service.py` | `tests/unit/test_design_gateway_postgres.py` `tests/unit/test_frontend_chat_intent.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `UNBOUND` |
| CH-04 | Send | Primary action button | `IntentRouterDecision` | `frontend.chat.send` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/chat/intent.py` `engine/studio/chat/service.py` | `tests/unit/test_design_gateway_postgres.py` `tests/unit/test_frontend_chat_intent.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `UNBOUND` |
| CH-05 | Reference resolution (this/Candidate B) | Inline resolved reference | `FrontendConversation.selected_node_ids` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/chat/intent.py` `engine/studio/chat/service.py` | `tests/unit/test_design_gateway_postgres.py` `tests/unit/test_frontend_chat_intent.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `UNBOUND` |
| CH-06 | Design-class intent routing | Routed to DesignGateway | `DesignSessionReadModel` | `frontend.design.request|refine` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/chat/intent.py` `engine/studio/chat/service.py` `engine/studio/design/context.py` `engine/studio/design/gateway.py` `engine/studio/design/providers.py` | `tests/unit/test_design_gateway_postgres.py` `tests/unit/test_frontend_chat_intent.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `UNBOUND` |
| CH-07 | Deterministic edit routing | Routed to MutationPlanner, no model call | `MutationPlan` | `frontend.mutation.plan|apply` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/chat/intent.py` `engine/studio/chat/service.py` `engine/studio/mutations/executor.py` `engine/studio/mutations/planner.py` | `tests/unit/test_design_gateway_postgres.py` `tests/unit/test_frontend_chat_intent.py` `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `UNBOUND` |
| CH-08 | Undo / revert | Chat command + inspector action | `MutationHistory` | `frontend.mutation.revert` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/mutations/planner.py` `engine/studio/mutations/executor.py` | `tests/unit/test_frontend_mutation_engine_postgres.py` | `UNBOUND` |

Notes:

- **CH-03** — Context scope is held on the FrontendConversation and set through frontend.chat.set_context; a per-turn provider/policy inspector UI is M17.

## Candidate / Directions dock

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#87-candidatedirections-dock`

| ID | Feature | Visual contract | Read model | Command | Domain | Read | Command evidence | UI | Wired | E2E | Visual | Implementation | Tests | Final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CA-01 | Candidate cards | Bottom strip cards with thumbnails | `CandidateBoardSnapshot` | `frontend.candidate.create` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `VERIFIED` | `engine/studio/candidates/service.py` `engine/studio/candidates/lifecycle.py` | `tests/unit/test_frontend_mutation_engine_postgres.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `TYPED_UNAVAILABLE` |
| CA-02 | Candidate thumbnail | Rendered candidate screenshot | `CandidateBoardSnapshot[].thumbnail_ref` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `VERIFIED` | `engine/studio/candidates/service.py` `engine/studio/candidates/lifecycle.py` | `tests/unit/test_frontend_mutation_engine_postgres.py` | `TYPED_UNAVAILABLE` |
| CA-03 | Candidate score | Numeric score or 'Not scored' | `CandidateScorecard` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `VERIFIED` | `engine/studio/candidates/service.py` `engine/studio/candidates/lifecycle.py` | `tests/unit/test_frontend_mutation_engine_postgres.py` | `TYPED_UNAVAILABLE` |
| CA-04 | Score classification | Good/Medium chip, clickable explanation | `CandidateScorecard.classification` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `VERIFIED` | `engine/studio/candidates/service.py` `engine/studio/candidates/lifecycle.py` | `tests/unit/test_frontend_mutation_engine_postgres.py` | `TYPED_UNAVAILABLE` |
| CA-05 | Change count | 'N changes' from real structural diff | `MutationPlan delta` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/mutations/projection.py` `engine/studio/mutations/planner.py` `engine/studio/mutations/executor.py` | `tests/unit/test_frontend_mutation_engine_postgres.py` | `UNBOUND` |
| CA-06 | Current (Locked) card | Accepted revision card with lock chip | `AcceptedDesignRevision` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/candidates/service.py` `engine/studio/candidates/lifecycle.py` `engine/studio/mutations/projection.py` | `tests/unit/test_frontend_mutation_engine_postgres.py` | `UNBOUND` |
| CA-07 | Try live | Card action button | `CandidateWorkspace` | `frontend.design.try_live` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/candidates/lifecycle.py` `engine/studio/candidates/service.py` `engine/studio/design/context.py` `engine/studio/design/gateway.py` `engine/studio/design/providers.py` | `tests/unit/test_design_gateway_postgres.py` `tests/unit/test_frontend_chat_intent.py` `tests/unit/test_frontend_mutation_engine_postgres.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `UNBOUND` |
| CA-08 | Compare | Card action; side-by-side real renders | `CandidateBoardSnapshot (compare mode)` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `VERIFIED` | `engine/studio/candidates/service.py` `engine/studio/candidates/lifecycle.py` | `tests/unit/test_frontend_mutation_engine_postgres.py` | `TYPED_UNAVAILABLE` |
| CA-09 | Promote / accept | Card action; governed gate | `FrontendAcceptanceRecord` | `frontend.candidate.promote` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/candidates/promotion.py` | `tests/unit/test_frontend_mutation_engine_postgres.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `UNBOUND` |

Notes:

- **CA-01** — The candidate domain is implemented, but the React strip deliberately renders a typed unavailable state until the preview runtime can supply real thumbnails. No candidate card is fabricated.
- **CA-02** — Thumbnails require the preview runtime (DDE-069 M9); the card shows a typed NOT_RENDERED state.
- **CA-03** — No CandidateScorecard exists; DDE-069 M8/M17 work. Cards render 'Not scored' rather than a fabricated percentage (FRONTEND_STUDIO_REV3 section 17.2 forbids hardcoded 84/76/92).
- **CA-04** — Classification derives from a score that does not exist yet; the chip renders 'Not scored'.
- **CA-08** — Compare requires two rendered candidates (DDE-069 M9).

## Source Blend

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#88-source-blend`

| ID | Feature | Visual contract | Read model | Command | Domain | Read | Command evidence | UI | Wired | E2E | Visual | Implementation | Tests | Final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SB-01 | Actual attribution | Named sources with computed percentages | `SourceBlendSnapshot.attribution` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/design/context.py` `engine/studio/design/gateway.py` `engine/studio/design/providers.py` | `tests/unit/test_design_gateway_postgres.py` `tests/unit/test_frontend_chat_intent.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `UNBOUND` |
| SB-02 | Target blend slider | Generation preference control | `SourceBlendTarget` | `frontend.design.request (blend target)` | `VERIFIED` | `VERIFIED` | `BOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/design/context.py` `engine/studio/design/gateway.py` `engine/studio/design/providers.py` | `tests/unit/test_design_gateway_postgres.py` `tests/unit/test_frontend_chat_intent.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `UNBOUND` |

Notes:

- **SB-01** — SourceBlend attribution needs the provenance service over source adapters (DDE-069 M8). Named sources without computed percentages is the honest interim, per section 8.8.
- **SB-02** — The target-blend preference is accepted by the design request path but has no UI control until M8 gives it real sources to blend.

## Inspector

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#89-inspector`

| ID | Feature | Visual contract | Read model | Command | Domain | Read | Command evidence | UI | Wired | E2E | Visual | Implementation | Tests | Final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| IN-01 | Selected node header | 310-325px panel header, stable selection | `PreviewSelectionAnchor` | — | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `NOT_APPLICABLE` | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `TYPED_UNAVAILABLE` | `VERIFIED` | `interfaces/dde-studio/ui/src/frontend-studio/InspectorPanel.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `TYPED_UNAVAILABLE` |
| IN-02 | Layout tab | Descriptor group tab | `InspectorDescriptor[layout]` | `frontend.mutation.plan|apply` | `VERIFIED` | `VERIFIED` | `BOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/mutations/planner.py` `engine/studio/mutations/executor.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` | `UNBOUND` |
| IN-03 | Style tab | Descriptor group tab | `InspectorDescriptor[style]` | `frontend.mutation.plan|apply` | `VERIFIED` | `VERIFIED` | `BOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/mutations/planner.py` `engine/studio/mutations/executor.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `UNBOUND` |
| IN-04 | Behaviour tab | Descriptor group tab | `InspectorDescriptor[behavior]` | `frontend.mutation.plan|apply` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| IN-05 | Responsive tab | Descriptor group tab | `InspectorDescriptor[responsive]` | `frontend.mutation.plan|apply` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| IN-06 | Lock tab | Lock inventory + actions | `LockInventory (effective)` | `frontend.lock.create|update|remove` | `VERIFIED` | `VERIFIED` | `BOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/locks/service.py` `engine/studio/locks/resolution.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `UNBOUND` |
| IN-07 | Source / code tab | Read-only source mapping + reveal | `SourceMappingSnapshot` | — | `UNBOUND` | `UNBOUND` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| IN-08 | Type: Stack | Enum descriptor control | `InspectorDescriptor[layout].type` | `frontend.mutation.apply` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| IN-09 | Direction | Enum descriptor control | `InspectorDescriptor[layout].direction` | `frontend.mutation.apply` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| IN-10 | Gap (px + token) | '24 px  space-6' dual display | `InspectorDescriptor[layout].gap` | `frontend.mutation.apply` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/mutations/planner.py` `engine/studio/mutations/executor.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `UNBOUND` |
| IN-11 | Padding (px + token) | Same dual display | `InspectorDescriptor[layout].padding` | `frontend.mutation.apply` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/mutations/planner.py` `engine/studio/mutations/executor.py` | `tests/unit/test_frontend_mutation_engine.py` `tests/unit/test_frontend_mutation_engine_postgres.py` `tests/unit/test_frontend_studio_e2e_postgres.py` | `UNBOUND` |
| IN-12 | Behaviour: animation | Tokenised motion reference control | `InspectorDescriptor[behavior].animation` | `frontend.motion.set_animation` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| IN-13 | Provenance section | Source artifact, licence, security state | `ProvenanceRecord` | — | `UNBOUND` | `UNBOUND` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| IN-14 | View Source | Reveal-file action | `SourceFileRef` | — | `UNBOUND` | `UNBOUND` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| IN-15 | Accessibility badge | AA / findings / Not evaluated | `QaFindingInventory[accessibility]` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `engine/studio/acceptance/defaults.py` `engine/studio/acceptance/service.py` `schemas/design/screen_acceptance_defaults.json` | `tests/unit/test_screen_acceptance_binding.py` `tests/unit/test_screen_acceptance_binding_postgres.py` | `UNBOUND` |
| IN-16 | Responsive breakpoint buttons | Segmented control | `PreviewViewportState` | `frontend.preview.set_state` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |

Notes:

- **IN-01** — The inspector panel exists at the locked width with a designed no-selection state. Stable selection needs the preview instrumentation layer (DDE-069 M9); the mutation path it would drive is already real and governed.
- **IN-15** — Same as EX-22: the accessibility rubric dimension is bound by default, but the inspector's read of its result is M17. Renders Not evaluated.

## Status bar

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#810-status-bar`

| ID | Feature | Visual contract | Read model | Command | Domain | Read | Command evidence | UI | Wired | E2E | Visual | Implementation | Tests | Final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ST-01 | Breadcrumb | 32-36px bar, selected path from PXG | `PxgGraphSnapshot path` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `engine/studio/pxg/service.py` `engine/studio/reads.py` `interfaces/dde-studio/ui/src/shell/StatusBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_studio_domain_postgres.py` | `UNBOUND` |
| ST-02 | Error count | 'No errors' / count | `QaFindingInventory.blocking` | — | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `engine/studio/coverage/scoring.py` `engine/studio/coverage/service.py` `engine/studio/reads.py` `interfaces/dde-studio/ui/src/shell/StatusBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` `tests/unit/test_frontend_coverage_engine.py` `tests/unit/test_frontend_studio_domain_postgres.py` | `UNBOUND` |
| ST-03 | Warning count | 'N warnings' | `QaFindingInventory.warnings` | — | `UNBOUND` | `UNBOUND` | `NOT_APPLICABLE` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| ST-04 | Auto Layout state | ON/OFF toggle | `EditorAssistState.auto_layout` | `frontend.editor.set_assist` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| ST-05 | AI Suggest state | ON/OFF toggle | `EditorAssistState.ai_suggest` | `frontend.editor.set_assist` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | `UNBOUND` | — | — | `UNBOUND` |
| ST-06 | Build / version | Studio build + project revision | `StudioSyncSnapshot.build` | — | `UNBOUND` | `BOUND` | `NOT_APPLICABLE` | `VERIFIED` | `UNBOUND` | `UNBOUND` | `VERIFIED` | `interfaces/dde-studio/ui/src/shell/StatusBar.tsx` | `interfaces/dde-studio/ui/visual/shell.spec.ts` | `UNBOUND` |
