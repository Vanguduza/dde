# DDE Frontend Studio — functional binding matrix

<!-- GENERATED FILE. Edit `docs/truth/golden/frontend_binding_matrix.json` and run `uv run python -m scripts.render_binding_matrix`. -->

**Authority:** docs/truth/FRONTEND_STUDIO_REV3.md section 8 (Golden UI - quantum functional binding map); AD-035; AD-036

**Closure rule:** A golden visible-control row is finally VERIFIED only when every applicable DOMAIN, READ, COMMAND, STATE, UI, WIRED, E2E and VISUAL layer is VERIFIED. Applicability is explicit; UI, WIRED, E2E and VISUAL are mandatory for every golden control unless the row contract itself is changed through canonical change control. Backend-only evidence can never prove UI, WIRED, E2E or VISUAL. TYPED_UNAVAILABLE and BLOCKED_EXTERNAL remain non-verified. AD-039 independently blocks PIXEL_REFERENCE conformance until the approved golden artifact is present.

## Final ledger state

| Final status | Rows |
|---|---:|
| `UNBOUND` | 0 |
| `TYPED_UNAVAILABLE` | 9 |
| `BOUND` | 67 |
| `VERIFIED` | 23 |
| **total** | **99** |

Final status is derived. It is never authored independently of the eight layers.
`NOT_APPLICABLE` is legal only with an explicit reason in canonical JSON.

## Global top bar

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#81-global-top-bar`

| ID | Feature | DOMAIN | READ | COMMAND | STATE | UI | WIRED | E2E | VISUAL | FINAL |
|---|---|---|---|---|---|---|---|---|---|---|
| TB-01 | Product title / module identity | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `BOUND` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `BOUND` |
| TB-02 | Project selector | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |
| TB-03 | Saved timestamp | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| TB-04 | Sync status chip | `VERIFIED` | `BOUND` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `BOUND` |
| TB-05 | Design mode tab | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |
| TB-06 | Coverage mode tab | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |
| TB-07 | Architecture mode tab | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |
| TB-08 | QA mode tab | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |
| TB-09 | Source mode tab | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |
| TB-10 | Coverage ring | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| TB-11 | Activity / metrics icon | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `BOUND` |
| TB-12 | Attention notification badge | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `BOUND` |
| TB-13 | Help | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `NOT_APPLICABLE` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `BOUND` |
| TB-14 | User avatar / principal | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `BOUND` |

Notes:

- **TB-02** — Packaged production-host project switching is proven end-to-end, including authoritative screen readback in both projects and return navigation.
- **TB-03** — Sync provenance is projected from the durable Frontend Studio snapshot; packaged editor-host browser E2E remains outstanding.
- **TB-04** — StudioSyncSnapshot distinguishes durable revision from command acceptance. The M7 mutation engine is implemented, but pending-mutation state is not yet projected into FrontendReadService, so the chip must not overclaim SYNCED.
- **TB-11** — Reconciled at commits 09c4249 and 23f773f; packaged production-host E2E remains a separate gate.
- **TB-12** — Reconciled at commits 09c4249 and 23f773f; packaged production-host E2E remains a separate gate.
- **TB-13** — Reconciled at commits 09c4249 and 23f773f; packaged production-host E2E remains a separate gate.
- **TB-14** — Reconciled at commits 09c4249 and 23f773f; packaged production-host E2E remains a separate gate.

## App rail and project explorer

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#82-app-rail-and-project-explorer`

| ID | Feature | DOMAIN | READ | COMMAND | STATE | UI | WIRED | E2E | VISUAL | FINAL |
|---|---|---|---|---|---|---|---|---|---|---|
| EX-01 | App rail module icons | `NOT_APPLICABLE` | `VERIFIED` | `TYPED_UNAVAILABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `TYPED_UNAVAILABLE` |
| EX-02 | Project heading + menu | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |
| EX-03 | Explorer search | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |
| EX-04 | Screens group + count | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |
| EX-05 | Journeys group + count | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `BOUND` |
| EX-06 | Components group + count | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `BOUND` |
| EX-07 | Sources group | `TYPED_UNAVAILABLE` | `BOUND` | `NOT_APPLICABLE` | `TYPED_UNAVAILABLE` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `TYPED_UNAVAILABLE` |
| EX-08 | DDE Library source | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `BOUND` | `BOUND` |
| EX-09 | 21st MCP source | `VERIFIED` | `VERIFIED` | `VERIFIED` | `TYPED_UNAVAILABLE` | `BOUND` | `BOUND` | `BLOCKED_EXTERNAL` | `BOUND` | `TYPED_UNAVAILABLE` |
| EX-10 | Donor Sources | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `BOUND` | `BOUND` |
| EX-11 | Internal Components | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| EX-12 | Source numeric badges | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| EX-13 | Templates group | `TYPED_UNAVAILABLE` | `BOUND` | `BOUND` | `TYPED_UNAVAILABLE` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `TYPED_UNAVAILABLE` |
| EX-14 | Template entries | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `BOUND` | `BOUND` |
| EX-15 | Locks group + count | `VERIFIED` | `BOUND` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `BOUND` |
| EX-16 | Style Locks | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |
| EX-17 | Section Locks | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |
| EX-18 | Component Locks | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |
| EX-19 | Behaviour Locks | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |
| EX-20 | QA group | `NOT_APPLICABLE` | `BOUND` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| EX-21 | QA Issues count | `NOT_APPLICABLE` | `BOUND` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| EX-22 | Accessibility count | `TYPED_UNAVAILABLE` | `BOUND` | `NOT_APPLICABLE` | `TYPED_UNAVAILABLE` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `TYPED_UNAVAILABLE` |

Notes:

- **EX-01** — Frontend Studio is the only packaged module; later modules remain explicitly unavailable and are not fabricated.
- **EX-02** — Project heading and project-state menu are bound to current host/project projections.
- **EX-03** — Reconciled after the 09c4249/23f773f closure packets; production-host E2E remains separate.
- **EX-07** — DesignSourceRegistry is DDE-069 M8. The explorer group is listed with an UNKNOWN count (Availability.NOT_IMPLEMENTED) rather than hidden or shown as zero.
- **EX-08** — M8 implements DDE Library inventory/search/fetch/admission with real PostgreSQL lifecycle proof. Explorer status-dot grammar and packaged React → production Gateway/PostgreSQL browser E2E remain open.
- **EX-09** — M8 implements a fail-closed 21st MCP adapter. Live provider execution remains externally blocked; no direct-network fallback exists.
- **EX-10** — Existing Donor Lab remains authoritative and is now projected through M8 Source Intelligence; exact Explorer status-dot grammar remains open.
- **EX-11** — M8 project-native adapter now supplies the real component inventory; final status remains BOUND pending production E2E.
- **EX-12** — M8 replaces the prior placeholder source counts with real provider counts or typed unknown/degraded state.
- **EX-13** — TemplateRecommendationService is DDE-069 M8; the group reports NOT_IMPLEMENTED.
- **EX-14** — M8 implements durable template recommendations; golden Explorer nesting remains to be closed.
- **EX-15** — LockService is implemented. The current FrontendReadService still exposes the Locks group as an unavailable count; a real LockInventory projection is required before this read is complete.
- **EX-16** — Authoritative LockService per-kind inventory now projects into the four canonical nested Explorer lock counts. Packaged editor-host E2E remains outstanding.
- **EX-17** — Authoritative LockService per-kind inventory now projects into the four canonical nested Explorer lock counts. Packaged editor-host E2E remains outstanding.
- **EX-18** — Authoritative LockService per-kind inventory now projects into the four canonical nested Explorer lock counts. Packaged editor-host E2E remains outstanding.
- **EX-19** — Authoritative LockService per-kind inventory now projects into the four canonical nested Explorer lock counts. Packaged editor-host E2E remains outstanding.
- **EX-20** — Explorer QA adapts the current mission-scoped Screen Audit matrix; no duplicate QA persistence authority is introduced.
- **EX-21** — Explorer QA adapts the current mission-scoped Screen Audit matrix; no duplicate QA persistence authority is introduced.
- **EX-22** — Accessibility count is derived from current Screen Audit dimensions only when every current screen is assessed; otherwise the Explorer renders a typed unknown reason.

## Orchestrator card

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#83-orchestrator-card`

| ID | Feature | DOMAIN | READ | COMMAND | STATE | UI | WIRED | E2E | VISUAL | FINAL |
|---|---|---|---|---|---|---|---|---|---|---|
| OR-01 | Orchestrator status | `TYPED_UNAVAILABLE` | `BOUND` | `NOT_APPLICABLE` | `TYPED_UNAVAILABLE` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `TYPED_UNAVAILABLE` |
| OR-02 | Manager Chair identity | `TYPED_UNAVAILABLE` | `BOUND` | `NOT_APPLICABLE` | `TYPED_UNAVAILABLE` | `BOUND` | `BOUND` | `BOUND` | `BOUND` | `TYPED_UNAVAILABLE` |
| OR-03 | Desired/Configured/Serving split | `TYPED_UNAVAILABLE` | `BOUND` | `NOT_APPLICABLE` | `TYPED_UNAVAILABLE` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `TYPED_UNAVAILABLE` |
| OR-04 | Design Director role | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `BOUND` |
| OR-05 | Activity visualisation | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `BOUND` |
| OR-06 | Status dot | `TYPED_UNAVAILABLE` | `BOUND` | `NOT_APPLICABLE` | `TYPED_UNAVAILABLE` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `TYPED_UNAVAILABLE` |

Notes:

- **OR-01** — No orchestrator runtime is wired to the Studio; runtime_state is UNKNOWN rather than a decorative ACTIVE dot.
- **OR-02** — Manager Chair serving identity remains deliberately UNATTESTED until ModelServingEvidence exists; the typed unavailable projection is now wired to the visible card.
- **OR-03** — Blueprint Rev 3 section 5.4 ModelServingEvidence is unimplemented, so serving_confidence is UNATTESTED and desired/configured/serving stay separate and empty.
- **OR-04** — Reconciled after the 09c4249/23f773f closure packets; production-host E2E remains separate.
- **OR-05** — Reconciled at commits 09c4249 and 23f773f; packaged production-host E2E remains a separate gate.
- **OR-06** — Role health has no backing projection; the dot renders UNKNOWN.

## Canvas toolbar

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#84-canvas-toolbar`

| ID | Feature | DOMAIN | READ | COMMAND | STATE | UI | WIRED | E2E | VISUAL | FINAL |
|---|---|---|---|---|---|---|---|---|---|---|
| CT-01 | Viewport selector | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| CT-02 | Select tool | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |
| CT-03 | Hand / pan tool | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |
| CT-04 | Comment tool | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| CT-05 | Grid / overlay options | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |
| CT-06 | Claude /design button | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |
| CT-07 | Zoom control | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |
| CT-08 | Fullscreen / fit | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |

Notes:

- **CT-01** — Viewport changes start a new code-backed preview session. frontend.preview.set_state remains reserved for browser LIVE/RUNTIME_ERROR attestations.
- **CT-02** — Select is presentation-only editor interaction state; row-specific browser proof shows SELECT restores iframe pointer interaction.
- **CT-03** — Pan is presentation-only editor interaction state; row-specific browser proof shows PAN disables iframe pointer capture and physically scrolls the canvas.
- **CT-04** — Reconciled at commits 09c4249 and 23f773f; packaged production-host E2E remains a separate gate.
- **CT-05** — Grid is presentation-only overlay state. Contract corrected: frontend.preview.set_state is reserved for browser LIVE/RUNTIME_ERROR lifecycle attestation and must not carry grid options.
- **CT-06** — Closed by a dedicated certified Claude Design transport (engine/studio/design/claude_transport.py): the authenticated Claude Code executable is used only as a bounded structured host for the official claude-design MCP, with an ephemeral allowlist admitting nothing but mcp__claude-design__* (plus ToolSearch and the harness result emitter), no session persistence and a machine-readable manifest contract instead of final prose. The stream is checked against those flags: MCP connection, offered tools, executed tools, permission denials and per-direction write evidence. Activation is explicit (DDE_CLAUDE_DESIGN_ENABLED); an unconfigured deployment still reports NOT_CERTIFIED and the gateway still refuses with no fallback. capability.claude_code_invoke remains forbidden as a substitute. A recorded live run proved provider CERTIFIED, /design through Universal DDE Chat, persisted DesignSession/DesignArtifacts, Try live's isolated candidate, a code-backed preview reaching LIVE only on a matching content hash, and promotion still refused by the verification gate.
- **CT-07** — Canvas zoom is presentation-only React state; it scales the live preview and selection overlay without issuing Gateway commands or mutating candidate/PXG state.
- **CT-08** — Fit and Fullscreen are presentation-only host/editor state; browser proof covers fit, real fullscreen, and typed HOST_UNSUPPORTED failure.

## Real canvas and selection

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#85-real-canvas-and-selection`

| ID | Feature | DOMAIN | READ | COMMAND | STATE | UI | WIRED | E2E | VISUAL | FINAL |
|---|---|---|---|---|---|---|---|---|---|---|
| CV-01 | Live preview surface | `BOUND` | `BOUND` | `BOUND` | `BOUND` | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `BOUND` |
| CV-02 | LIVE badge | `BOUND` | `BOUND` | `NOT_APPLICABLE` | `BOUND` | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `BOUND` |
| CV-03 | Route / screen navigation | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| CV-04 | Selection outline | `NOT_APPLICABLE` | `BOUND` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `BOUND` |
| CV-05 | Resize handles | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| CV-06 | Section lock chip | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `NOT_APPLICABLE` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| CV-07 | Style lock chip | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `NOT_APPLICABLE` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| CV-08 | State simulation controls | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |

Notes:

- **CV-01** — A real code-backed prototype-HTML PreviewRuntimeAdapter and PreviewService now exist. The React workbench still renders the prior honest unavailable Design surface, so UI/WIRED/E2E remain incomplete.
- **CV-02** — No LIVE badge is rendered because nothing satisfies its five conditions (revision + build + runtime + health + route). DDE-069 M9.
- **CV-04** — Stable pxg_key instrumentation is implemented in the code-backed prototype preview. DOM geometry remains overlay metadata only; the React selection outline is still unbound.
- **CV-05** — Reconciled after the 09c4249/23f773f closure packets; production-host E2E remains separate.
- **CV-06** — Effective lock chips are projected from the same governed Inspector descriptor as the Lock tab; combined packaged editor-host browser E2E remains outstanding.
- **CV-07** — Effective lock chips are projected from the same governed Inspector descriptor as the Lock tab; combined packaged editor-host browser E2E remains outstanding.
- **CV-08** — Reconciled at commits 09c4249 and 23f773f; packaged production-host E2E remains a separate gate.

## Frontend Chat composer

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#86-frontend-chat-composer`

| ID | Feature | DOMAIN | READ | COMMAND | STATE | UI | WIRED | E2E | VISUAL | FINAL |
|---|---|---|---|---|---|---|---|---|---|---|
| CH-01 | Chat composer | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |
| CH-02 | Selection-aware context chips | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `BOUND` |
| CH-03 | Context/scope settings | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |
| CH-04 | Send | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |
| CH-05 | Reference resolution (this/Candidate B) | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `BOUND` |
| CH-06 | Design-class intent routing | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `BOUND` |
| CH-07 | Deterministic edit routing | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `BOUND` |
| CH-08 | Undo / revert | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `BOUND` |

Notes:

- **CH-03** — Context is durable on FrontendConversation and updated through frontend.chat.set_context; Cursor-class context UI now exposes screen/candidate/viewport, Ask/Plan/Execute mode, model/profile selection, pinned references and explicit context-budget inclusion/omission. Production E2E remains BOUND until PostgreSQL/Redis infrastructure is available.

## Candidate / Directions dock

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#87-candidatedirections-dock`

| ID | Feature | DOMAIN | READ | COMMAND | STATE | UI | WIRED | E2E | VISUAL | FINAL |
|---|---|---|---|---|---|---|---|---|---|---|
| CA-01 | Candidate cards | `VERIFIED` | `BOUND` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `BOUND` |
| CA-02 | Candidate thumbnail | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| CA-03 | Candidate score | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| CA-04 | Score classification | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| CA-05 | Change count | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| CA-06 | Current (Locked) card | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `BOUND` |
| CA-07 | Try live | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| CA-08 | Compare | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| CA-09 | Promote / accept | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |

Notes:

- **CA-02** — Candidate thumbnails now render exact code-backed PreviewDocument content; production E2E remains BOUND.
- **CA-03** — M8 CandidateScorecard is implemented and evidence-backed; final status remains BOUND pending production E2E.
- **CA-04** — Clickable evidence-backed score explanation is implemented; final status remains BOUND pending production E2E.
- **CA-06** — Accepted Current is sourced from durable PXG revision and effective LockService inventory. The golden locked chip appears only when active locks actually exist; zero locks renders NO ACTIVE LOCKS rather than inventing a lock.
- **CA-07** — Direction A/B/C React cards and selected-artifact Try Live are implemented; the combined packaged VS Code-host -> real Gateway -> PostgreSQL browser run remains the final CA-07 proof obligation.
- **CA-08** — Candidate compare is implemented for two real LIVE preview documents; production E2E remains BOUND.

## Source Blend

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#88-source-blend`

| ID | Feature | DOMAIN | READ | COMMAND | STATE | UI | WIRED | E2E | VISUAL | FINAL |
|---|---|---|---|---|---|---|---|---|---|---|
| SB-01 | Actual attribution | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `BOUND` | `BOUND` |
| SB-02 | Target blend slider | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `BOUND` | `BOUND` |

Notes:

- **SB-01** — M8 implements actual provenance attribution. Target preferences do not rewrite history; named-source presentation remains open.
- **SB-02** — M8 implements target blend as a future-generation preference. Golden slider grammar remains for UI closure.

## Inspector

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#89-inspector`

| ID | Feature | DOMAIN | READ | COMMAND | STATE | UI | WIRED | E2E | VISUAL | FINAL |
|---|---|---|---|---|---|---|---|---|---|---|
| IN-01 | Selected node header | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `BOUND` |
| IN-02 | Layout tab | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| IN-03 | Style tab | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| IN-04 | Behaviour tab | `NOT_APPLICABLE` | `BOUND` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| IN-05 | Responsive tab | `NOT_APPLICABLE` | `BOUND` | `BOUND` | `BOUND` | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `BOUND` |
| IN-06 | Lock tab | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `BOUND` |
| IN-07 | Source / code tab | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| IN-08 | Type: Stack | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| IN-09 | Direction | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| IN-10 | Gap (px + token) | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `BOUND` |
| IN-11 | Padding (px + token) | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| IN-12 | Behaviour: animation | `BOUND` | `BOUND` | `BOUND` | `BOUND` | `BOUND` | `BOUND` | `BOUND` | `BOUND` | `BOUND` |
| IN-13 | Provenance section | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| IN-14 | View Source | `NOT_APPLICABLE` | `BOUND` | `NOT_APPLICABLE` | `BOUND` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| IN-15 | Accessibility badge | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `BOUND` |
| IN-16 | Responsive breakpoint buttons | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `VERIFIED` | `BOUND` |

Notes:

- **IN-01** — InspectorDescriptor and mission-scoped read transport are implemented. The existing React panel still receives selectedKey=null, so no UI completion is claimed.
- **IN-07** — Real source mapping/reveal exists; Inspector golden closure must convert it into the required Source/code tab.
- **IN-11** — The control is implemented with token-bound dual display. Repository token authority currently resolves space8 to 40px; the golden 64px example has no authorised spacing token, so DDE shows space8 · 40px and refuses raw 64px until token authority changes.
- **IN-13** — M8 accepted provenance is now visible in Inspector; final status remains BOUND pending production E2E.
- **IN-15** — Same as EX-22: the accessibility rubric dimension is bound by default, but the inspector's read of its result is M17. Renders Not evaluated.

## Status bar

Specification: `docs/truth/FRONTEND_STUDIO_REV3.md#810-status-bar`

| ID | Feature | DOMAIN | READ | COMMAND | STATE | UI | WIRED | E2E | VISUAL | FINAL |
|---|---|---|---|---|---|---|---|---|---|---|
| ST-01 | Breadcrumb | `VERIFIED` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| ST-02 | Error count | `VERIFIED` | `BOUND` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `BOUND` |
| ST-03 | Warning count | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `BOUND` | `BOUND` |
| ST-04 | Auto Layout state | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| ST-05 | AI Suggest state | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `BOUND` | `BOUND` | `VERIFIED` | `BOUND` |
| ST-06 | Build / version | `NOT_APPLICABLE` | `VERIFIED` | `NOT_APPLICABLE` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` | `VERIFIED` |

Notes:

- **ST-01** — Breadcrumb now uses projected project/screen labels and the selected Inspector/PXG title; raw PXG keys and hard-coded Project text are no longer the visible selected path.
- **ST-03** — Reconciled at commits 09c4249 and 23f773f; packaged production-host E2E remains a separate gate.
- **ST-04** — Reconciled at commits 09c4249 and 23f773f; packaged production-host E2E remains a separate gate.
- **ST-05** — Reconciled at commits 09c4249 and 23f773f; packaged production-host E2E remains a separate gate.
- **ST-06** — Sync provenance is projected from the durable Frontend Studio snapshot; packaged editor-host browser E2E remains outstanding.
