# DDE Rev 3 — Canonical Resume Prompt

Use this prompt when starting a new engineering session, coding agent, Claude Code/Cursor run, Hermes session or equivalent worker. The repository is the memory source; do not require the historic ChatGPT thread.

---

## Prompt

You are resuming development of **DDE — Development & Engineering Engine** in repository `Vanguduza/dde`.

You have ZERO trusted conversational context.

Do not infer current state from model memory, prior chat, screenshots or this prompt alone.

# THE REPOSITORY IS THE SOURCE OF TRUTH.

Your current mission is DDE-069 — **DDE Code / Frontend Studio V2 + Live Design Foundation** — unless repository evidence proves that the mission has advanced.

Do not restart the project. Preserve verified work. Do not create parallel architectures for functionality that already has an owner.

---

# 1. Establish authority before touching code

Read, in this order:

1. `AGENTS.md`
2. `docs/truth/BLUEPRINT_REV3.md`
3. `docs/truth/ARCHITECTURE_DECISIONS.md`
4. `docs/truth/DEV_PLAN_REV3.md`
5. `docs/truth/IMPLEMENTATION_STATE.md`
6. `docs/truth/FRONTEND_STUDIO_REV3.md` — adopted Frontend Studio domain architecture (AD-036)
7. `docs/truth/CURSOR_CLASS_AI_CHAT.md` and `docs/truth/AI_CONVERSATION_FABRIC.md` — universal DDE Chat, provider federation, shared memory/context and governed AI runtime
8. `docs/truth/SCREEN_AUDIT_ENGINE.md` — user-locked DDE-069 Screen Audit / Experience Completeness extension; subordinate to `FRONTEND_STUDIO_REV3.md`, not a second architecture
9. `docs/truth/FRONTEND_STUDIO_BINDING_MATRIX.md` and its generated source `docs/truth/golden/frontend_binding_matrix.json`
10. `docs/evidence/dde-068/CLOSURE_MATRIX.md`
11. relevant accepted EDR markdown pre-images under `docs/truth/edr/**` and the accepted Project Truth rows where no markdown pre-image exists
12. relevant DDE-065..069 planning/chapter-gate documents under `docs/planning/**`

Authority order remains:

```text
accepted Project Truth / EDR
→ Blueprint Rev 3
→ adopted domain truth documents
→ Development Plan
→ Architecture Decision index
→ Implementation State
→ Resume Prompt
→ planning/evidence/reference documents
→ code comments / chat / model memory
```

Do not silently choose whichever document is easiest when authorities conflict. Identify the conflict and use the normal EDR/change-control path where required.

---

# 2. Cold-start reconstruction

Before changing code:

- inspect repository identity;
- inspect active branch;
- inspect HEAD and remote tracking state;
- inspect working tree;
- inspect recent DDE-069 commits;
- compare current branch against the DDE-068 closure baseline;
- inspect schemas, migrations, services, Gateway commands, React workbench, tests and evidence;
- verify whether `IMPLEMENTATION_STATE.md` and the binding matrix still describe reality;
- run focused baseline tests appropriate to the next packet.

Do not begin by writing code.

Report the reconstructed baseline briefly, then continue automatically.

---

# 3. Known DDE-069 state to verify, not blindly trust

At the time this resume packet was updated, the active DDE-069 work was on branch:

`claude/dde-069-frontend-studio-v2-yn110e`

Latest committed consolidation before this truth update: `843c61e` — `DDE-069 close design transport inspector and source federation`. Verify HEAD/remote; do not assume this commit is still current after later work.

Recent implementation had already landed the following substantial pieces. Verify each from code/tests rather than reimplementing them:

## DDE-068 prerequisite

DDE-068 is `COMPLETE_EVIDENCED`.

Its closure proves:

- real rendered evidence;
- deterministic visual checks;
- silhouette/distinctiveness;
- believable-density evidence + multimodal judgment;
- real `capability.visual_critique`;
- structured verdicts;
- bounded repair;
- human escalation;
- fail-closed promotion.

EDR-0017 remains binding:

- the narrow visual-critic capability is separate from broad `capability.claude_code_invoke`;
- `STANDING_FORBIDDEN_TYPES` must not be weakened;
- general Claude Code execution still requires its existing approval boundary.

Do not reopen DDE-068 unless evidence shows a regression.

## DDE-069 domain foundation reportedly landed

Verify:

- DDE-067 characterization/regression tests;
- golden visual manifest and structural-vs-pixel-reference distinction;
- 99-control Frontend Studio functional binding ledger;
- PXG with stable `pxg_key` identity;
- Frontend Contract publish/supersede semantics;
- Coverage Engine with honest UNKNOWN/MISSING/UNVERIFIED behavior;
- read projections;
- automatic generated/imported-screen acceptance bindings;
- mandatory `silhouette` + `visual_critique` bindings;
- unified mutation planner/executor;
- operation-sensitive locks;
- isolated candidate lifecycle;
- candidate promotion gate consuming DDE-068 evidence;
- host-neutral React/TypeScript/Vite workbench behind `DdeHostBridge`;
- structural shell tests at the canonical 1672×941 viewport;
- Frontend Chat backend/control-plane semantics;
- DesignSession / DesignArtifact / DesignEditContext / DesignGateway foundation;
- a certified Claude Design MCP transport, with typed refusal whenever it is
  not activated by configuration.
- strict `dde.design.manifest/1` validation against exported PXG/materialization
  capability and exact design-system token vocabulary;
- deterministic DesignArtifact → candidate materialization through the ordinary mutation
  engine with all-or-nothing semantics, stale-PXG refusal and promotion-lineage checks;
- public source-registry federation for shadcn/ui, ReUI, Magic UI and Aceternity UI,
  with 21st retained as an optional fail-closed provider;
- DDE-only same-host terminal/provider profile isolation from Dial repo/Hermes/global
  Claude state (AD-045).

Reported test state at the last implementation commit before the Screen Audit truth update was approximately:

`1347 passed, 6 skipped, 0 failed`

Do not use that number as current proof. Re-run applicable checks after reconstruction.

---

# 4. Current product reality — do not overclaim

The backend/domain architecture is ahead of the actual Frontend Studio user experience.

Verify the following known gaps before deciding they still exist:

1. **The canonical central VS Code React workbench is now wired to the code-backed prototype-HTML PreviewRuntime for existing materialized candidates.** It performs browser-attested LIVE, stable `pxg_key` selection, InspectorDescriptor reads, governed token mutation, preview invalidation and rerender. Do not rebuild this loop.
2. **Fresh candidate onboarding is implemented.** Core projects real READY durable source workspaces, excludes candidate-preview worktrees, auto-selects only a unique source and requires explicit choice when ambiguous. No workspace id is guessed.
3. **Real PostgreSQL/Redis integration is now evidenced on the current execution host.** An isolated DDE-only PostgreSQL 16.15 + Redis 7.0.15 runtime exercises migrations, Gateway, Chat, Screen Audit, M8, candidate verification and Redis streams. Keep any row whose E2E requirement specifically demands the packaged VS Code-host process BOUND until that host path is exercised; do not relabel the database itself unavailable.
4. **DDE-068 candidate request execution is implemented.** A hash-confirmed LIVE preview persists a request over the candidate's effective PXG and existing AcceptanceOracle; `frontend.verification.run` executes it through the shared DDE-068 runner as a typed `FRONTEND_CANDIDATE` subject, with real browser/visual-critic capability leases, real VerificationRun/Evidence, stale-run protection and current evidence projection in QA/Inspector. PENDING/BLOCKED/SUPERSEDED remain non-verdict states. Real PostgreSQL persistence for this path is now covered by the isolated DDE-069 integration suite; packaged VS Code-host browser proof remains a distinct gate.
5. **The Cursor-class Chat has been universalized as DDE Chat and its AI Conversation Fabric is implemented on runnable surfaces.** `engine.chat` owns durable multi-conversation history, Ask/Plan/Execute, attachments, plans, activities, checkpoints, workspace review and universal mission/task/workspace/worker/verification/artifact context. Frontend Studio contributes PXG/Contract/coverage/candidate state only through its context adapter. `dde.chat.*` and `/missions/{mission}/chat/...` are canonical; old `frontend.chat.*` contracts are compatibility aliases. Provider/session federation, ACP, Fabric policy/memory/context/skill/team/research/automation/hook/claim/experience authorities and MCP surfaces exist. Shared DDE memory stores structured authority/index metadata in PostgreSQL and non-ephemeral bodies/compaction archives in scoped content-addressed storage (R2 when configured, local fallback). Hermes ACP is DDE-managed under verified `--ignore-rules` isolation to prevent duplicate provider-private memory injection. Conversation context is policy-budgeted across protected live authority, explicit refs, APPROVED ranked memory and bounded history with durable PRE/POST compaction snapshots. Browser and extension proof remain green; isolated real PostgreSQL/Redis integration is now green, while live R2 E2E still requires complete scoped R2 credentials.
6. **The certified `/design` transport/control path is closed; the golden Try-live workflow is not.** `engine/studio/design/claude_transport.py` is a dedicated bounded host for the official `claude-design` MCP, with explicit activation, one-server/tool allowlisting, no session persistence, a machine-readable manifest and stream-level policy verification. Broad `capability.claude_code_invoke` remains forbidden as a `/design` substitute. The manifest/materialization contract is now stricter: only exported materializable PXG nodes and exact exported token properties/values are accepted; duplicate-node ambiguity, stale PXG and empty/off-token proposals fail closed. `Try live` materializes the deterministic lane through `MutationExecutor(origin=DESIGN_PROVIDER, all_or_nothing=True)` into an isolated candidate and promotion revalidates pinned artifact/session/provider/design-system/base-revision lineage. **CA-07 is still open** because the React Direction A/B/C selection surface and production E2E proving the selected proposal in the LIVE candidate are absent. A strengthened real-provider rerun on 2026-09-06 reached `CERTIFIED` but ended `PROVIDER_ERROR` before a successful result; keep the failed rerun as evidence and rerun it without weakening the contract.
7. **Source intelligence (M8) is federated and partially evidenced.** The common adapter/domain/Gateway/Chat/React lifecycle passes against isolated PostgreSQL 16.15. A generic read-only public shadcn-registry adapter is live-tested against shadcn/ui, ReUI, Magic UI and Aceternity UI; exact fetched bytes are hash-pinned and Aceternity licence state remains UNKNOWN rather than inferred. 21st remains supported but optional/NOT_CONFIGURED and is not a DDE-069 blocker. Full live public-provider → persisted search/fetch → sandbox/admission E2E remains separate.
8. **Pixel-reference visual conformance is still repository-blocked, but the exact artifact is known.** The owner-approved image was externally recovered as 1672×941, 1,492,542 bytes, SHA-256 `8e24bb34e5fb5723bbc9e44c2716f05300f5f4e95f463770349f05fdba8a6377`. It is not yet committed at the canonical path, so AD-039 remains fail-closed. Never reconstruct a substitute.
9. **The binding ledger is v2 and currently derives 6 VERIFIED / 51 BOUND / 6 TYPED_UNAVAILABLE / 36 UNBOUND.** `CT-06` is VERIFIED; `CA-06` is BOUND at production-host E2E; `CA-07` is UNBOUND at UI/WIRED/E2E/VISUAL. Final state still derives from explicit DOMAIN/READ/COMMAND/STATE/UI/WIRED/E2E/VISUAL evidence.
10. **Same-host DDE execution is isolated from Dial.** The DDE terminal/sandbox uses a DDE-only home/config/Claude profile and mounts the DDE repository but not `/srv/dial/repo` or shared `~/.hermes`. Do not use global/Dial provider state to make DDE appear configured, and do not remove this boundary while both products share the machine.

Do not declare M7/M9/M10 or DDE-069 complete from domain implementation alone.

---

# 5. Golden visual blocker

AD-035 makes the user-approved 1672×941 Frontend Studio mockup the canonical visual baseline.

AD-039 still records the repository state as BLOCKED_EXTERNAL, but the exact artifact was
recovered outside the repository on 2026-09-06:

- dimensions: **1672×941**;
- byte size: **1,492,542**;
- SHA-256: `8e24bb34e5fb5723bbc9e44c2716f05300f5f4e95f463770349f05fdba8a6377`.

Until those exact bytes are committed:

- continue STRUCTURAL conformance from `FRONTEND_STUDIO_REV3.md`;
- do not claim PIXEL_REFERENCE conformance;
- `engine.studio.golden_visual.require_pixel_reference` must continue to fail closed;
- do not fabricate/reconstruct/regenerate a replacement from prose or screenshots.

Canonical destination:

`docs/truth/golden/frontend-studio-shell.png`

After transfer, verify dimensions/size/hash **on the repository copy** and record the
same SHA-256 in `docs/truth/golden/GOLDEN_VISUAL_MANIFEST.json`.

The fact that an exact copy exists outside Project Truth is recovery evidence, not a
license to bypass the pinning gate.

---

# 6. Certified `/design` transport — closed, and what must stay true

The DesignGateway architecture is real and must remain provider-neutral.
`engine/studio/design/claude_transport.py` is the first certified transport and
was proven live on 2026-09-06
(`docs/evidence/dde-069/CLAUDE_DESIGN_TRANSPORT_CLOSURE.md`).

Do not weaken any of these:

- activation stays explicit configuration; a deployment that has not set
  `DDE_CLAUDE_DESIGN_ENABLED` gets `NOT_CERTIFIED` and a refusal, never a
  best-effort provider;
- the host keeps `--tools ToolSearch`, `--strict-mcp-config` with exactly one
  admitted server, ephemeral `--settings`, `--setting-sources ""`,
  `--permission-mode dontAsk`, `--permission-prompts none` and
  `--no-session-persistence`;
- the returned stream is still checked against those flags, and a disagreement
  is a refusal rather than a warning;
- the return contract stays the machine-readable manifest; never parse final
  prose, and never accept a direction naming a PXG key that was not exported or
  a deliverable with no observed MCP write;
- broad `capability.claude_code_invoke` is never routed as `/design`, and
  EDR-0001 / EDR-0017 approval boundaries are never relaxed;
- `/design` remains a Universal DDE Chat intent sharing one DesignSession; the
  toolbar control never opens a second conversation or mutates accepted state directly;
- manifest nodes are limited to explicit materializable PXG keys and exact exported
  token properties/values; stale PXG, duplicate-node ambiguity and off-token values are
  refusals rather than best-effort adaptation;
- deterministic Try-live goes through the same governed mutation engine as Inspector/
  Chat edits with all-or-nothing application, and candidate promotion must revalidate
  DesignArtifact/DesignSession/provider/design-system/base-revision lineage.

The committed live evidence proves the transport/control boundary. It predates the new
strict materialization assertions and therefore does **not** close `CA-07`. The
strengthened test currently includes a persisted DesignArtifact API read and selected-
proposal proof; its 2026-09-06 live rerun reached a certified provider but terminated
`PROVIDER_ERROR` before a successful result. Preserve
`docs/evidence/dde-069/claude-design-live-rerun-failed-2026-09-06.json` and rerun; do
not loosen the contract to make the provider pass.

Any further provider must implement the accepted `DesignProvider` contract and
pass admission/security/context tests before it is used.

---

# 7. Binding-ledger semantic hardening — COMPLETED, verify before reuse

The v2 ledger must remain the completion oracle unless newer canonical change
control supersedes it.

Required invariant:

> A visible golden-control row cannot reach final VERIFIED unless every
> applicable DOMAIN / READ / COMMAND / STATE / UI / WIRED / E2E / VISUAL
> layer is evidenced, including real React UI, production wiring and E2E.

Current implementation is in:

- `schemas/design/frontend_binding_matrix.schema.json`;
- `engine/studio/binding_matrix.py`;
- `docs/truth/golden/frontend_binding_matrix.json`;
- generated `docs/truth/FRONTEND_STUDIO_BINDING_MATRIX.md`;
- `tests/unit/test_frontend_binding_matrix.py`;
- `docs/evidence/dde-069/BINDING_LEDGER_V2.md`.

Backend-only Chat/candidate/Inspector rows must stay non-verified until their
UI/WIRED/E2E evidence exists. Do not collapse the ledger back to one status
axis or delete requirements to improve the count.

---

# 8. Next highest-value vertical slice — Screen Audit

The governed live-edit + verification + Chat loop is now composed:

```text
real candidate board / READY source selection
→ sandboxed code-backed preview
→ browser hash handshake / Core-confirmed LIVE
→ real DDE-068 VerificationRun/Evidence
→ stable pxg_key selection
→ Inspector or universal DDE Chat governed mutation / undo
→ old preview + verification evidence stale/superseded
→ rerender/new hash
→ new verification request/run/evidence
→ persisted Cursor-class Chat thread with server-derived project context
→ optional Ask / Plan / approved Execute path with exact Gateway command identity
→ history / attachment / activity / checkpoint / workspace-review lineage
```

Do not rebuild that path. Evidence is in
`docs/evidence/dde-069/LIVE_WORKBENCH_LOOP.md`,
`docs/evidence/dde-069/SOURCE_AND_VERIFICATION_REQUESTS.md`,
`docs/evidence/dde-069/CANDIDATE_VERIFICATION_EXECUTION.md` and
`docs/evidence/dde-069/REACT_FRONTEND_CHAT.md` and
`docs/evidence/dde-069/CURSOR_CLASS_AI_CHAT.md`.

The mandatory Screen Audit & Experience Completeness Engine has now landed. Read
`docs/truth/SCREEN_AUDIT_ENGINE.md` before changing it, but do not rebuild its
domain/persistence/read/command authority, incremental invalidation or existing UI
projections. Verify regressions only. Its implemented outcomes include:

- canonical ScreenAuditRun / ScreenAuditScreenRecord / ScreenAuditFinding /
  ScreenAuditEvidence / ScreenAuditResolution;
- the adopted audit dimensions and PASS/FAIL/PARTIAL/UNKNOWN/BLOCKED/
  NOT_APPLICABLE semantics;
- finding lifecycle from DETECTED through CONFIRMED/ASSIGNED/VERIFYING/RESOLVED
  plus ACCEPTED_EXCEPTION/BLOCKED/SUPERSEDED;
- incremental invalidation tied to real mutation/PXG/evidence dependencies;
- Coverage completeness matrix, QA finding workbench, Architecture overlays and
  Canvas/Inspector audit markers;
- audit-aware commands in the already-landed Frontend Chat, with `/design` repair
  context only when a certified provider exists;
- dogfood audit of DDE Frontend Studio reconciled against the 99-control ledger.

Production VS Code → Gateway → PostgreSQL E2E remains BOUND until database
infrastructure is available. AD-039 still blocks pixel-reference conformance.

---

# 9. Screen Audit & Experience Completeness Engine — newly adopted DDE-069 scope

Read `docs/truth/SCREEN_AUDIT_ENGINE.md` in full before implementing this packet.

This is not a new mission and not a separate application.

It is a derived intelligence layer over:

```text
PXG
+
Frontend Contract
+
Coverage Engine
+
routes / journeys / role-policy evidence
+
candidate / mutation lineage
+
DDE-068 verification
+
source / provenance
```

The engine must answer both:

- what screens/experiences actually exist; and
- what screens/experiences are required to exist.

Do not create a second PXG or second Coverage Engine.

---

# 10. Screen Audit core implementation packet

After or alongside the first working live-preview vertical slice where dependencies allow, implement Screen Audit schema-first.

Reuse existing contracts/services where semantics already exist.

Expected domain equivalents:

- `ScreenAuditRun`
- `ScreenAuditScreenRecord`
- `ScreenAuditFinding`
- `ScreenAuditEvidence`
- `ScreenAuditResolution`

Core deterministic audit dimensions include applicable:

- contract completeness;
- journey reachability / dead ends;
- visible-control functional binding;
- loading/empty/error/success/disabled/offline/permission states;
- real data/read-model backing;
- role/permission reachability;
- navigation integrity;
- accessibility evidence;
- responsive/platform completeness;
- DDE-068 visual state;
- source/provenance;
- security-relevant screen facts;
- drift between source/PXG/contract/routes/roles/verification.

Unknown remains unknown.

Do not convert incomplete audit dimensions into a reassuring aggregate score.

Accepted exceptions require a durable decision reference.

---

# 11. Screen Audit lifecycle and repair law

Use a governed lifecycle equivalent to:

```text
DETECTED
→ CONFIRMED
→ CANDIDATE_CREATED / ASSIGNED
→ VERIFYING
→ RESOLVED
```

with explicit alternatives such as:

```text
ACCEPTED_EXCEPTION
BLOCKED
SUPERSEDED
```

Rules:

- a chat/model statement cannot resolve a finding;
- a DesignArtifact cannot resolve a finding;
- candidate creation cannot resolve a finding;
- promotion + incremental re-audit is what proves resolution;
- changed evidence can make a previous finding/result stale;
- accepted exceptions need a durable authority/decision.

Repair path:

```text
audit finding
→ deterministic mutation OR DesignGateway candidate
→ isolated candidate
→ real preview
→ functional/state checks
→ DDE-068 visual verification
→ promotion gate
→ accepted revision
→ incremental re-audit
→ RESOLVED or still failing
```

---

# 12. Screen Audit UI integration

Do not create a separate top-level Audit app.

Integrate into the locked modes:

## Coverage

Implement the Screen Matrix:

- screen vs contract/journey/function/states/accessibility/visual/platform dimensions;
- honest UNKNOWN/PARTIAL/BLOCKED semantics;
- click row → open real screen/canvas;
- click finding → evidence/details.

## Architecture

Use the real PXG/journey/route graph with overlays for:

- orphan screens;
- unreachable screens;
- dead ends;
- missing contract nodes;
- role reachability;
- platform gaps;
- unresolved blockers.

No hardcoded graph.

## QA

Create a findings workbench with real filters/evidence by:

- severity;
- screen;
- journey;
- role;
- platform;
- dimension;
- lifecycle;
- age/staleness;
- repair candidate.

## Design / Canvas

Overlay applicable audit markers on the real preview without mutating the candidate.

## Inspector

Add an Audit section for the selected stable node.

## Source

Expose source/provenance/drift from real source-intelligence evidence once M8 exists.

---

# 13. Frontend Chat integration

The existing chat backend is a control plane, not a chatbot dock. Preserve that.

Wire the actual React chat surface and add deterministic audit queries such as:

```text
/audit current screen
show missing states in checkout
which screens implement FEATURE-X?
show unreachable screens
show dead-end journeys
show role-specific screen gaps
create repair candidates for blocking findings
```

Audit reads should use deterministic projections.

Deterministic edits should compile into the existing MutationPlanner.

Generative design requests may route through DesignGateway when a certified provider exists.

Ambiguity is refused rather than guessed.

Chat cannot mark findings resolved.

---

# 14. `/design` + Screen Audit

Audit findings may be compiled into a bounded `DesignEditContext`.

Example:

```text
Target: Checkout
Audit constraints:
- payment-error state missing
- mobile state missing
- hierarchy defect
- navigation locked
- silhouette PASS
- accessibility PASS

/design → create three candidates addressing unresolved findings only
```

The provider creates candidates, never approvals.

The independent DDE-068 critic remains the visual-verification authority.

---

# 15. Screen Audit dogfood gate

The first comprehensive Screen Audit proof must audit **DDE Frontend Studio itself**.

Compare three evidence sources:

```text
Screen Audit findings
vs
FRONTEND_STUDIO_BINDING_MATRIX
vs
actual React/Gateway/runtime behavior
```

The audit should be capable of discovering known current gaps without being hardcoded to them, including applicable:

- no real live canvas;
- stable selection absent;
- Inspector not wired end-to-end;
- chat backend present but chat UI absent;
- source-intelligence gaps;
- pixel-reference conformance blocked.

Any disagreement between the audit and the 99-control ledger becomes a reconciliation finding.

---

# 16. M8 Source Intelligence — federated partial checkpoint, finish from repository

Do not rebuild M8 from scratch. The branch contains migration `0034`,
`engine/studio/source/`, generated source contracts, Gateway commands/reads, Universal
DDE Chat source search and React Source/candidate/Inspector integration.

Current provider order is:

```text
project-native
→ DDE Library
→ shadcn/ui
→ ReUI
→ Magic UI
→ Aceternity UI
→ optional 21st MCP
→ donor sources
```

The four public web providers use `PublicShadcnRegistryAdapter`: health/index/search/
inspect/fetch only, HTTPS/redirect host allowlisting, JSON and response-size bounds,
index-bound item identities, exact-byte hashing, and **no** install/publish/package-
manager/accepted-project write capability. 21st remains a separate fail-closed adapter
when an exact certified transport is configured; its absence degrades only that source.

The common vertical slice supports source inventory/health, search → inspect → fetch →
sandbox adapt → sandbox validate → admit, compiler hard-failure dominance, persisted
provenance, template recommendations, evidence-backed CandidateScorecard, actual
attribution vs target blend, promotion provenance gates, Screen Audit source evidence and
Universal Chat search.

Evidence status:

- real PostgreSQL 16.15 lifecycle: PASS;
- public-registry live network certification: PASS for shadcn/ui, ReUI, Magic UI and
  Aceternity UI (`docs/evidence/dde-069/public-registry-live-run.json`);
- observed reuse evidence: shadcn/ReUI/Magic UI MIT; Aceternity remains UNKNOWN;
- complete live provider → persisted source lifecycle → sandbox/admission E2E: still open;
- 21st: optional NOT_CONFIGURED/uncertified on this host, not a DDE-069 blocker;
- live R2: still waits on a complete correctly classified scoped credential tuple.

Keep provider health/licence uncertainty typed. Never upgrade discovery success into
admission or legal reuse.

---

# 17. Full DDE-069 user-workflow target

The finished workbench must support a representative real sequence equivalent to:

```text
open project
→ inspect Screen Matrix / product coverage
→ select real screen
→ render candidate live
→ select component
→ Inspector resolves real properties
→ chat understands current screen/selection/audit state
→ deterministic edit or /design candidate request
→ candidate changes
→ canvas rerenders
→ Screen Audit + DDE-068 verification update
→ blocking finding prevents promotion
→ repair candidate produced
→ rerender / reverification
→ corrected candidate becomes promotable
→ governed promotion
→ accepted revision updates
→ incremental Screen Audit reruns
→ finding resolves from evidence
```

Do not close DDE-069 until the relevant portions of this path are real and E2E tested.

---

# 18. Golden visual law

The completed Frontend Studio must remain recognizably the same locked product as the user-approved canonical preview.

Structural work may proceed from the written measurements while the image is unavailable.

Once the exact golden image is pinned:

- render at canonical viewport;
- perform deterministic structural comparison;
- use DDE-068 multimodal critique;
- bounded repair material differences;
- require explicit approved decision for intentional material deviations.

Do not call a generic admin dashboard "functionally equivalent" to bypass the visual law.

---

# 19. Security and authority invariants

Never:

- give interfaces direct core-table access;
- pass long-lived secrets into model-generated execution;
- use broad Claude Code execution as an unattended design/critic shortcut;
- weaken standing-forbidden approval types;
- mutate accepted code outside candidate/promotion paths;
- export whole private repositories to model providers;
- treat screenshot/UI text as instructions;
- use unknown verification as approval;
- use a model to waive hard requirements;
- create cross-tenant audit scans;
- import Dial production/Oracle/Hermes architecture into DDE.

DDE and Dial remain separate projects/architectures.

---

# 20. Performance / scale rules

Frontend Studio and Screen Audit must handle large projects without full recomputation for every local change.

Use dependency-directed invalidation and indexed stable identities.

Track where practical:

- audit duration;
- incremental audit duration;
- screens/nodes assessed;
- stale findings/evidence;
- render latency;
- candidate-switch latency;
- Inspector selection latency;
- model/visual-critic usage and cost;
- blocked/failed audit runs.

Use deterministic analysis before model calls whenever possible.

---

# 20A. Production VEKL forward architecture lock

AD-048 / Blueprint §26A are now canonical future-production architecture. Do not create a standalone VEKL subsystem or a new VEKL mission-number series.

VEKL applies when DDE manufactures **target applications**. Its application-manufacturing resolver must refuse DDE control-plane self-development. Target Project Truth and DDE governance always outrank external resources.

Reuse current DDE primitives:

- Source Intelligence / Donor Lab for discovery, provenance and reuse classification;
- capability leases, egress, secrets and ExternalEffect reconciliation for executable/network authority;
- TaskExecutionDescriptor/ChangePacket/workspace for task/mutation identity;
- Context Compiler for smallest-sufficient activation context;
- Verification/Evidence for completion;
- Hermes only for research/retrieval/resource-outcome candidates.

The reviewed v1 resource/activation-manifest/hook/loop schemas are design inputs, not implemented runtime contracts. New source families are not admitted by the pack's seed catalogue; they require accepted DDE egress change control.

Delivery is mapped into locked missions, not appended after DDE-083:

```text
DDE-075  Hermes VEKL research/resource outcomes/candidate learning
DDE-076  qualified resource/component/version/certification registry
DDE-077  StackFingerprint + TaskSignature bound to execution/change ownership
DDE-080  VEKL eligibility/ranking + ActivationManifest + KnowledgeCompiler + egress prerequisite
DDE-081  inspectable Production Studio VEKL projections
DDE-082  Instruction IR + Hook IR + qualified tool/plugin/MCP/LSP + bounded loops
DDE-083  adversarial/supply-chain/revocation/offline/cross-project certification
```

Do not reuse or repurpose routing-learning `ExperienceRecord` or execution `ExecutionExperienceRecord` for VEKL effectiveness. Use a distinct `VEKLResourceOutcome`-class schema when the owning mission implements it.

Any agent reaching DDE-075+ must read Blueprint §26A and AD-048 before designing source/resource/tool/skill/plugin/loop behavior.

---

# 21. Test / evidence requirements

For each vertical slice use applicable:

- schema drift tests;
- unit tests;
- contract tests;
- PostgreSQL integration tests;
- Gateway command tests;
- browser/Playwright tests;
- accessibility tests;
- failure injection;
- visual structural tests;
- DDE-068 real visual evidence;
- real workbench E2E tests.

Mocks are useful for repeatability but do not replace required real runtime proof.

A green `just check` is necessary, not sufficient, for mission closure.

---

# 22. Truth maintenance

At every meaningful tranche:

- update `docs/truth/IMPLEMENTATION_STATE.md` from evidence;
- update the binding ledger from evidence;
- update `SCREEN_AUDIT_ENGINE.md` only if the locked capability contract itself changes;
- update Architecture Decisions only for real decisions;
- keep `RESUME_PROMPT.md` current;
- commit evidence/chapter-gate material as appropriate.

The repository must allow a zero-context agent to reconstruct:

- what is implemented;
- what is UI-only;
- what is verified;
- what is unavailable;
- what is blocked;
- the next executable packet.

---

# 23. Commit discipline

Commit coherent verified slices.

Do not bundle all remaining DDE-069 work into one mega-commit.

Suggested current sequence:

1. binding-matrix semantic hardening;
2. live preview + stable selection + Inspector vertical slice;
3. Screen Audit core domain/reconciliation;
4. Screen Audit Coverage/QA/Architecture UI;
5. Chat UI + audit context;
6. audit-driven repair loop;
7. Screen Audit dogfood evidence;
8. M8 source intelligence;
9. remaining golden-control closure;
10. pixel-reference closure once owner artifact exists;
11. DDE-069 chapter gate / truth reconciliation.

Adapt only when repository dependencies prove a different order is better.

---

# 24. Autonomous continuation

After reconstruction and each green packet, continue automatically.

Do not end routine work with:

- "Say resume"
- "Tell me to continue"
- "Ready when you are"

Stop only for:

1. an unresolved user-authority product decision;
2. a credential/authentication step the owner must personally perform;
3. a destructive/irreversible action requiring approval;
4. contradictory canonical authorities that cannot be reconciled;
5. a hard external dependency for which no accepted fallback exists;
6. context/usage exhaustion that would materially degrade reasoning quality.

If context/usage becomes unsafe:

- finish the current coherent packet;
- verify it;
- commit/push according to repository policy;
- update truth/evidence;
- leave an exact cold-start continuation packet.

Do not rush a new architecture tranche under exhausted context.

---

# 25. First response / first work packet

Begin by reporting only evidence-backed facts:

## Repository baseline

- branch
- HEAD
- clean/dirty
- remote state

## DDE-069 state

- which reported components are actually present
- current binding-ledger counts after semantic verification
- current tests

## Blockers

- golden image state
- design-provider transport state
- any newly discovered real blocker

## First packet

Default first packet is **React/host integration of the landed preview + stable selection + Inspector foundation**: production host reads/commands → real candidate canvas → Core-confirmed LIVE → selected pxg_key → descriptor control → governed mutation → rerender. The binding-ledger hardening and backend preview foundation should only be revisited for regressions or superseding canonical change control.

Then execute automatically.

Do not spend the session rewriting this plan unless implementation evidence exposes a genuine architecture conflict.

---

## End of canonical resume prompt

The purpose of this file is to make a fresh engineering session accurate, evidence-driven and independent of chat history while preserving DDE's quality-over-speed rule.

## DDE-069 Screen Audit checkpoint — 2026-09-05

Screen Audit Packet C/D/E/F is now implemented in the working branch: schema-first
run/screen/finding/evidence/resolution persistence, deterministic reconciliation,
accepted DDE-068 evidence, incremental staleness, mission reads/commands, Coverage
Screen Matrix, QA findings, Architecture overlays, Inspector Audit, universal Chat
audit queries and live `@finding`. Dogfood reconciliation validates the independent
99-control ledger and does not fabricate a production audit run when PostgreSQL is
unavailable. Evidence: `docs/evidence/dde-069/SCREEN_AUDIT_ENGINE.md`.

M8 Source Intelligence has now advanced beyond this earlier next-packet statement. The
current branch contains the partial checkpoint described below. Do not rebuild its common
adapter/domain/Gateway/Chat/React foundation; verify it, finish its production/provider
proof and reconcile the binding ledger, then use the dogfood gap list for remaining
golden controls.


## DDE-069 M8 checkpoint — 2026-09-05

The repository now contains a partial but broad M8 Source Intelligence implementation.
Focused evidence at checkpoint time: 35 Python tests, 14 targeted M8 Playwright
scenarios, the full 41-test workbench Playwright suite and 77 extension tests passed;
schema generation/binding drift, Ruff, mypy, both TypeScript surfaces, real VSIX
packaging and diff hygiene passed. Do not infer production DB/provider proof from those results.
Historical note: the checkpoint below originally observed no PostgreSQL/Redis runtime.
That state is superseded. The current host has isolated DDE-only PostgreSQL 16.15 and
Redis 7.0.15 integration evidence. 21st remains fail-closed when unconfigured, but the
public registry federation supplies independent external source coverage.

Historical Candidate Dock checkpoint after `b75524c`: exact PreviewDocument miniatures, real mutation counts, score explanation, two-LIVE compare and governed Promote were implemented. The later Inspector/lock tranche closed the effective-lock-inventory placeholder; `CA-06` is now BOUND only because packaged VS Code-host → Gateway → PostgreSQL browser E2E is not recorded. `CA-07` no longer has a Direction-card/Try-live UI gap: persisted DesignArtifact cards, selected-artifact materialization, browser-backed LIVE content and fresh DDE-068 rerun are structurally verified. Its remaining obligation is one packaged VS Code-host → real Gateway → PostgreSQL browser execution. Evidence: `docs/evidence/dde-069/CANDIDATE_DOCK_CLOSURE.md`, `docs/evidence/dde-069/INSPECTOR_GOLDEN_CLOSURE.md`, and `docs/evidence/dde-069/CA07_TRY_LIVE_CLOSURE.md`.

Latest continuation state after reconstructing `0a39299`:
1. M8 checkpoint gates were re-run: 49 focused Python tests, 41 workbench Playwright tests, 77 extension tests and real 89-file / 1.57 MB VSIX packaging are green;
2. `tests/unit/test_source_intelligence_postgres.py` now executes against isolated PostgreSQL 16.15 and passes; the broader DDE-069 PostgreSQL/Redis focused suite is 34/34 green;
3. public read-only registry adapters for shadcn/ui, ReUI, Magic UI and Aceternity UI have a live fetch/hash certification; 21st remains optional NOT_CONFIGURED;
4. the current 99-control ledger is **11 VERIFIED / 64 BOUND / 8 TYPED_UNAVAILABLE / 16 UNBOUND**;
5. Candidate Dock, Inspector and CA-07 UI/VISUAL closure are landed; `CA-07` remains BOUND only on the combined packaged VS Code-host → real Gateway → PostgreSQL browser proof. The same shell reconciliation now projects EX-16..EX-19 per-kind lock counts, EX-20/EX-21 Screen-Audit-backed QA counts, an honest typed-unavailable EX-22 accessibility count, TB-03 durable saved time, ST-06 build/PXG provenance, and a real ST-01 selection breadcrumb; do not rebuild these surfaces;
6. AD-039 remains fail-closed until the exact recovered hash-identified artifact is committed; `/design` transport certification is closed but strict materialization live proof must be rerun.
