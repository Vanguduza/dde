# DDE Implementation State — Rev 3

**Status:** CANONICAL CURRENT-STATE SNAPSHOT  
**Snapshot date:** 2026-09-02  
**Architecture:** `docs/truth/BLUEPRINT_REV3.md`  
**Plan:** `docs/truth/DEV_PLAN_REV3.md`

---

## 0. How to use this file

This document answers: **what is actually implemented now?**

It must remain evidence-based. Do not mark a feature complete because it appears in the blueprint, a schema exists, a test fixture exists, or an agent reported success.

Allowed state labels:

- `COMPLETE_EVIDENCED`
- `IMPLEMENTED_PARTIAL`
- `IN_PROGRESS`
- `PLANNED`
- `BLOCKED_DECISION`
- `BLOCKED_EXTERNAL`
- `DEFERRED`
- `HISTORICAL`

Every state transition should cite concrete repository evidence: commit, chapter gate, code paths, tests or verification artifacts.

---

## 1. Repository heads observed during Rev 3 bootstrap

### Last observed product implementation head before Rev 3 truth-doc commits

`c30d2969e3205d1a277dd128e8b182137a8892e0` — **DDE-067 Frontend Studio surface** — 2026-08-27.

The preceding implementation sequence visible in recent commits includes:

- `9a8bb86f6b9c8791e2db4030680abb32d29d475a` — DDE-065 generation-prompt compiler;
- `32ae479cd133ddab86431250fe7888623bf8453a` — DDE-066 donor discovery and feature-function taxonomy;
- `c30d2969e3205d1a277dd128e8b182137a8892e0` — DDE-067 Frontend Studio surface.

### Rev 3 source-of-truth bootstrap commits

These commits establish documentation/control-plane memory only; they do **not** advance product implementation beyond DDE-067:

- `98110744c175f5d8c83c2248962f670fa7b00748` — Blueprint Rev 3 created;
- `45624dc6a009c0eecc4bae6009d8621ff39ec09e` — Development Plan Rev 3 created;
- `fc12925ebcaa32eae880f173ea6a8e746d6bf406` — Architecture Decision index created;
- `8e460bf2a7a74bdec226ef5fbce43f8be5e65116` — initial Implementation State created;
- `1b21a195563a4c55426fd6090ed66941524d853c` — canonical Resume Prompt created;
- `fe45ba54299343ae3d70def59b439900fe85a7cc` — `AGENTS.md` switched to Rev 3 bootstrap/authority;
- `a3bfbd240820648892d11d951fe542593ad1d8b2` — `README.md` switched to Rev 3 SOT links.

This file's current commit is the close-out of the R3-0 source-of-truth migration.

---

## 2. Overall program state

| Area | State | Evidence / current reality |
|---|---|---|
| DDE Core control-plane foundation | `IMPLEMENTED_PARTIAL` | Repository contains truth, mission/planning, routing, capability, verification, adapters, interfaces, migrations and tests; several historical EDRs explicitly describe partial implementation and remaining production-call-site gaps. |
| Rev 3 repository-memory/SOT model | `COMPLETE_EVIDENCED` | All five canonical files exist under `docs/truth`; `AGENTS.md` and `README.md` now boot new work from Rev 3 and demote Rev 2 to historical/reference depth. |
| DDE-065 Generation-Prompt Compiler | `COMPLETE_EVIDENCED` | Landed in commit `9a8bb86...`; chapter-gate document exists. Treat later regressions separately. |
| DDE-066 Donor Discovery + taxonomy | `COMPLETE_EVIDENCED` | Landed in commit `32ae479...`; accepted EDR-0015 admits the bounded egress surface; chapter-gate exists. |
| DDE-067 Frontend Studio Surface | `COMPLETE_EVIDENCED` | Landed in commit `c30d296...`; chapter gate says production call sites are wired for its scope and explicitly hands the next sequential mission to DDE-068. |
| DDE-068 Visual Verification & Critique Loop | `COMPLETE_EVIDENCED` | All ten required elements implemented and evidenced, including a **live end-to-end run on real pixels** (`docs/evidence/dde-068/`): a poor candidate was rejected (believable_density=1), a good candidate was blocked on accessibility=3, its own repair instructions were applied, and cycle 1 passed and became promotion-eligible. `EDR-0017` accepted as Option C: a new narrow `capability.visual_critique`; the broad `capability.claude_code_invoke` is unchanged and `STANDING_FORBIDDEN_TYPES` was neither bypassed nor weakened. GUI-spec item D2 closed (`prototype_pixel_signoff` admitted, standing-forbidden). 1277 tests pass (unit, contract, recovery, integration), full suite green. |
| DDE-069 DDE Code / Frontend Studio V2 + Live Design Foundation | `IN_PROGRESS` | Adopted domain architecture: `docs/truth/FRONTEND_STUDIO_REV3.md` (AD-036). Supersedes the earlier "Mobile/Multi-target" framing that was never updated after `DEV_PLAN_REV3.md`'s Rev 3.3 edit (commit `b5753db`) redefined DDE-069; see AD-030. Mobile/multi-target is not deferred work of its own — it is a governed sub-capability (platform-specific design-source adapters + Expo/device runtime verification) inside this mission. Entry gate opened 2026-09-04 on DDE-068's evidenced closure. Backend domain foundation, M7 mutation/candidate/lock runtime, host-neutral React shell, Frontend Chat backend, DesignGateway, code-backed prototype preview foundation and descriptor-driven Inspector reads are landed; the inherited DDE-068 binding carry-over is closed. The central React live-canvas/selection/edit loop, candidate DDE-068 re-verification and universal Cursor-class DDE AI Chat surface are browser-proven and production-wired. AI Conversation Fabric persistence/ACP/MCP/provider-session primitives, DDE-owned shared memory, R2-capable durable object storage and policy-bounded context/compaction are implemented on runnable surfaces; production PostgreSQL/Redis and live R2 E2E remain unavailable on this host. Screen Audit and M8 Source Intelligence remain incomplete. Per-control state is the multidimensional `docs/truth/FRONTEND_STUDIO_BINDING_MATRIX.md`. One blocker: the AD-035 golden image is absent from the repository, so pixel-reference conformance fails closed — see the DDE-069 section. |
| Fable 5 strategic orchestration profile | `BLOCKED_EXTERNAL` | Rev 3 role is defined, but no actual Fable 5 adapter/runtime integration was found in the observed repository state. Implement only when a supported interface is available and testable. |
| Hermes persistent research/coordination role | `IMPLEMENTED_PARTIAL` | AI Conversation Fabric now discovers the installed Hermes runtime, requires evidence-backed endpoint certification, and has a fail-closed ACP client. DDE-managed Hermes ACP context isolation is proven with `--ignore-rules`; shared approved DDE memory is object-backed (R2 when configured) and replaces duplicate provider-private memory injection. Full downstream Hermes experience/fleet acceptance gates remain in DDE-075/076. |
| Claude Code worker integration | `IMPLEMENTED_PARTIAL` | DDE Code/packaging references Claude Code worker setup; Rev 3 quota-aware specialization and independent-review routing still require explicit implementation/evaluation. |
| DeepSeek worker integration | `IMPLEMENTED_PARTIAL` | Harness/profile references exist; Rev 3 lower-cost delegation policy and measured routing specialization remain to be proven end-to-end. |
| Frontend Studio professional Rev 3 redesign | `IMPLEMENTED_PARTIAL` | The host-neutral React shell, canonical composition, code-backed live preview, stable selected-node Inspector editing, DDE-068 candidate re-verification and Cursor-class DDE AI Chat control plane exist and are browser-proven. Production PostgreSQL E2E, Screen Audit and source intelligence remain incomplete under DDE-069. |
| Routing intelligence / learned policy promotion | `IMPLEMENTED_PARTIAL` | Existing routing registry/telemetry/learning planning exists; open EDR/partial implementation records require careful production-call-site audit before claiming full adaptive routing. |
| Context optimization / repository memory | `IMPLEMENTED_PARTIAL` | Universal DDE Chat now uses policy-bounded managed context: protected live authority, explicit refs, APPROVED ranked memory, warm/cold history budgets, deterministic compaction and durable ContextSnapshots. Memory/context bodies use scoped content-addressed storage with R2 production support and local fallback. Task-level Context Intelligence remains separately authoritative for Task ContextPackages, and live R2/PostgreSQL deployment proof is environment-dependent. |
| Windows complete installer / DDE Code distribution | `IMPLEMENTED_PARTIAL` | README and packaging describe DDE Code + Core/Postgres/Redis/migrations/wizard paths; release/recovery/signing/operational hardening remains a Rev 3 phase. |

---

## 3. Frontend Studio detailed state

### DDE-065 — Generation-Prompt Compiler

**State:** `COMPLETE_EVIDENCED`

Observed evidence:

- implementation commit exists;
- signed Frontend Studio charter defines deterministic/fail-closed inputs;
- DDE-065 chapter gate exists;
- compiler is intended to avoid model/network calls at compile time and embed design constraints/provenance.

**Do not reopen unless:** current tests/code show regression or DDE-068/Rev 3 requires a contract amendment.

### DDE-066 — Donor Discovery & Feature-Function Taxonomy

**State:** `COMPLETE_EVIDENCED`

Observed evidence:

- implementation commit exists;
- accepted EDR-0015 authorizes brokered allowlisted donor search;
- chapter gate exists;
- search path is control-plane capability, not a worker egress bypass.

**Known operational caution:** live provider behavior still depends on correctly captured credentials/provider setup; do not confuse code-path completion with every deployment having credentials configured.

### DDE-067 — Frontend Studio Surface & Consumption Wiring

**State:** `COMPLETE_EVIDENCED` for signed DDE-067 scope.

Observed evidence:

- latest product implementation commit before Rev 3 bootstrap is named `DDE-067 Frontend Studio surface`;
- DDE Code includes Mission Overview and Hermes/Claude Code/DeepSeek views;
- Frontend Studio commands are wired through Gateway-oriented surfaces;
- chapter gate records remaining list/read gaps honestly rather than fabricating rows;
- chapter gate explicitly states DDE-068 is next.

**Residuals intentionally not charged to DDE-067:**

- DD207+ combination lints;
- silhouette distinctiveness;
- density enforcement;
- reduced-motion semantics beyond current baseline;
- rendered verification evidence as a first-class DDE verification path;
- bounded VLM critique/revision;
- D3 list endpoints / richer live read surfaces where contracts are absent.

### DDE-068 — Visual Verification & Critique Loop

**State:** `COMPLETE_EVIDENCED`.

**Unblocked by:** accepted EDR-0016.

**Required before completion, evidence-checked 2026-09-04:**

1. real visual executor behind DDE verification capability — `LANDED`.
   `engine/verification/checks.py::run_check` dispatches `api_probe` and
   `visual_diff` through the brokered `BrowserCapability`
   (`engine/capabilities/browser.py`); `oracle.py`'s `EXECUTABLE_KINDS`
   includes both. Predates this tranche (DDE-043/044); verified still real
   by reading the current call sites, not assumed from the plan.
2. persisted screenshot/render evidence — `LANDED`. `_run_visual_diff`
   writes `actual_path`/`diff_path` PNGs under the workspace and returns
   `actual_sha256`/`golden_sha256`/`diff_ratio` as `CheckResult` evidence.
3. DD207+ combination lints — `LANDED`. `scripts/design_lints.py`'s
   `DD207`/`generic-tell-combination` detector (Inter-only + indigo accent
   + centered-hero-3-card, emoji-icon + pill-spam) runs inside `just check`
   (`design-lints` recipe) with a committed shrink-only baseline
   (`docs/design/lint-baseline.json`).
4. silhouette/fingerprint gate — `LANDED` (this tranche, commit
   `582e06a`'s follow-up). `engine/verification/silhouette.py`:
   `compute_fingerprint()` reduces a rendered PNG to a coarse
   `GRID_COLS`x`GRID_ROWS` content/empty occupancy grid (variance +
   background-luminance-delta classifier per cell, deterministic and
   hash-recorded per playbook §10.3's acceptance criterion);
   `evaluate_silhouette()` Jaccard-matches it against
   `GENERIC_LAYOUT_CORPUS` -- two self-generated templates
   (`centered-hero-3-card`, `centered-hero-plus-badge`) traced verbatim to
   the tells already named in `dde-frontend-ux-playbook.md` §1/§10.2
   (EDR-0016 decision 6: self-generated corpus, no scraping). New oracle
   kind `"silhouette"` added to `schemas/objects/acceptance_oracle.json`
   (regenerated into `engine/contracts/acceptance_oracle.py` via
   `scripts/generate_contracts`), `EXECUTABLE_KINDS`, and a real executor
   `_run_silhouette()` in `checks.py` that renders through the same
   brokered `BrowserCapability` as `visual_diff`, fails closed without a
   browser capability, and returns `FAILED`/`exit_code=1` on a near-match
   (`NEAR_MATCH_THRESHOLD=0.85`) -- "near-match = review blocker
   regardless of palette" per playbook §10.3.
   **Test evidence:** `tests/unit/test_silhouette.py` (9 tests: fingerprint
   determinism, corpus match/no-match on synthetic self-drawn PNGs, the
   `_run_silhouette` executor pass/fail/fail-closed paths, and the
   `EXECUTABLE_KINDS`/`validate_definition` contract) — **passed 9/9**
   with the optional `pillow` extra installed (`uv sync --extra browser`).
   Pillow is not in the default `uv sync --group dev` CI environment (same
   as the pre-existing `visual_diff`/`api_probe` browser-capability tests,
   e.g. `test_real_playwright_file_url_when_installed`), so the file
   `pytest.importorskip("PIL")`-skips there rather than silently
   fabricating a pass; `ruff`/`mypy` are clean in the default (no-extra)
   environment, matching what CI actually runs.
5. believable-density enforcement — `VERIFIED`. Now a scored dimension of the real rubric
   (`schemas/design/visual_critique_rubric.json`, `believable_density`,
   transcribed from playbook §8.3's P4 line) judged by the item-7 critic,
   with `evaluate_verdict` applying §8's own "any dimension <4 blocks"
   rule. Kept strictly distinct from **deterministic density evidence**
   (`compute_density_evidence`, `engine/verification/silhouette.py`:
   occupancy ratio, row/column spread, largest empty run, top/bottom
   balance), which is supplied to the critic as context only. Neither
   layer impersonates the other, per EDR-0017's guardrail. The earlier
   rejected filler-string proxy stays rejected.
6. reduced-motion semantic assertions — `LANDED` (recovered this session,
   commit `582e06a`'s parent `b35fb41`). `screens.spec.ts`'s
   reduced-motion-semantics test reads real computed
   `animation-duration`/`animation-name` under
   `prefers-reduced-motion: reduce`, distinct from the pre-existing
   snapshot-only reduced-motion golden.
7. VLM screenshot critique as rank-9 evidence — `VERIFIED`, unblocked by **EDR-0017 accepted as Option C**
   (2026-09-04). History, kept rather than erased: this requirement was
   `BLOCKED_EXTERNAL` across two prior tranches. The first reading ("no
   API key exists, therefore no route") was too shallow; the audit that
   followed found a real local multimodal route
   (`capability.claude_code_invoke`, EDR-0001 Path A) but correctly
   refused to reuse it, because `external_model_invocation` is
   `STANDING_FORBIDDEN_TYPES` (enforced at
   `engine/governance/service.py:1292`) and relaxing that to serve one
   unattended loop would have weakened the boundary protecting every other
   privileged use. EDR-0017 resolved this by creating a **new, narrower
   capability** instead.
   - **`capability.visual_critique`** (`engine/capabilities/seed.py`):
     `PURE_READ`, T1, ordinary Chapter 9 lease path. Distinct
     `capability_id`, side-effect class, adapter and schemas from the broad
     `capability.claude_code_invoke`, which is **unchanged** — no approval
     type was added, and nothing was removed from
     `STANDING_FORBIDDEN_TYPES`.
   - **Seam:** `engine/capabilities/visual_critic.py`
     (`VisualCriticCapability`). The request type carries no
     prompt/instruction field at all, so instructions structurally cannot
     be smuggled through it.
   - **Adapter:** `adapters/visual_critic/adapter.py` — per-invocation
     scratch directory containing only the screenshot; `--restricted`;
     `--allowed-tools Read` plus an explicit deny list;
     `--permission-prompts none`; `--json-schema` + `--output-format
     json`; hard spend ceiling and timeout; no `--add-dir`/`--mcp-config`/
     `--agents`. Provider-specific execution stays behind this adapter so
     another qualified critic can replace it.
   - **Verdict contract:** `engine/verification/visual_critique.py` —
     fail-closed `parse_verdict` (malformed JSON, missing/extra fields and
     out-of-range scores all raise) and `evaluate_verdict`, which applies
     the numeric rule to validated fields. A model claiming PASS while
     scoring a dimension below threshold is still blocked;
     `rubric_version`/`model`/`cost_usd` come from transport metadata, not
     from the model's own words.
   - **Test evidence:** `tests/unit/test_visual_critique.py`, 25 tests
     passing, covering all six EDR-0017 boundaries — happy path, visual
     rejection, bounded repair, critic failure (unavailable / errored /
     malformed / out-of-range), prompt-injection resistance (the fixed
     system contract names rendered UI text as data-not-instructions, and
     an adversarial candidate is reported as a defect rather than obeyed),
     and the capability boundary (the built command carries every
     containment flag; the only user-turn text is the adapter's own fixed
     instruction; a fake runtime records that its working directory held
     exactly `screenshot.png` and nothing else).
8. bounded revision <= 3 cycles — `VERIFIED`.
   `decide_revision_action` (`engine/verification/visual_critique.py`) is
   the whole bound: pure, so it cannot be bypassed by a caller losing
   count. `PROMOTE` on a passing assessment, `REVISE` while budget
   remains, `ESCALATE_HUMAN` at or past `MAX_REVISION_CYCLES = 3` — never
   a fourth cycle and never a silent promotion. Covered by four tests
   including the at-and-past-the-bound sweep.
   **Scope boundary, stated honestly:** this is the bounded *policy* and
   the critique/re-critique path. Automatically re-running a worker to
   *apply* repair instructions and re-render is a replan-path integration
   that this tranche did not build and did not fake; the caller drives
   re-render between cycles.
9. human escalation after bound — `VERIFIED`. `ESCALATE_HUMAN` is the
   terminal state of the bounded policy, and **GUI-spec open item D2 is
   now closed**: `prototype_pixel_signoff` is an admitted
   `APPROVAL_TYPES` member and is in `STANDING_FORBIDDEN_TYPES` (a
   blanket "approve all future pixel sign-offs" would defeat the bound).
   `StudioFrontendService.request_pixel_signoff` no longer refuses: it
   creates a real `Approval` whose scope hash binds the screen ref,
   rubric version and failing dimensions, so approving one screen's
   pixels cannot authorise another's. Covered by the frontend-studio
   gateway test and a standing-forbidden assertion.
10. real production promotion/merge gate consuming visual verdicts —
    `LANDED`. The gate is generic across every `EXECUTABLE_KINDS` member:
    `VerificationRunnerService.run()` -> `_execute_outcome()` ->
    `_evaluate()` (`runner.py:1130`, reads only `CheckResult.status`) ->
    `_finalise_passed_attempt()` / `_fail_unverified_attempt()` ->
    `TaskAttemptService.finalize()` / `.fail()`. An earlier snapshot wrongly
    called this "NOT STARTED" after searching for a module by name instead
    of tracing the call graph.
    **Test evidence, real Postgres, not a mock of the gate:**
    `tests/unit/test_silhouette_promotion_gate_postgres.py` (2 tests) and
    `tests/unit/test_visual_critique_promotion_gate_postgres.py` (3 tests):
    a rubric-blocked screen produces a FAILED `VerificationRun` AND a
    FAILED `TaskAttempt` (never `COMPLETED`); a passing screen reaches
    `COMPLETED`; and an unusable critic response yields `ERRORED` with the
    attempt still not `COMPLETED` — infrastructure failure is never
    approval.
    **Residual:** nothing yet *authors* a `silhouette`/`visual_diff`/
    `visual_critique` binding onto a generated screen's `AcceptanceOracle`
    by default. The gate refuses correctly whenever such a check is bound;
    binding one automatically for every generated-screen task is
    DDE-065/067 authoring-surface territory.

**Live end-to-end evidence (2026-09-04):** `docs/evidence/dde-068/`
records a real run with no stand-ins in the chain — real Playwright render,
real screenshot, real deterministic analysis, real multimodal critique, real
verdict, real promotion decision:

- `poor-candidate` (the playbook's own generic tells plus lorem/"Item 1"
  filler): BLOCK at confidence 0.92, `believable_density`/`token_discipline`/
  `data_presentation`/`copy_voice`/`states_completeness` all scored 1 —
  promotion **DENIED**.
- `good-candidate` cycle 0: not written to fail, and the deterministic layer
  passed it (silhouette similarity 0.47, no near-match). The live critic
  nonetheless blocked it on `accessibility = 3`, correctly spotting
  low-contrast secondary text below the AA bar — promotion **DENIED**.
- `good-candidate` cycle 1: that critique's own `repair_instructions` were
  applied, the screen re-rendered and re-critiqued with the prior critique
  fed back; `accessibility` 3 -> 4, every dimension >= 4, policy PASS,
  `decide_revision_action` -> `PROMOTE` — promotion **ELIGIBLE**.

The critic's non-blocking `hierarchy_and_rhythm` finding quoted the
deterministic density evidence back verbatim (top_half_ratio 0.67 vs
bottom_half_ratio 0.40): the deterministic layer measured, the rubric layer
judged, neither impersonated the other. Measured cost across the three live
invocations: **$0.3631** (`claude-sonnet-5`), reported by the runtime, not
estimated.

**Remaining residual (not a DDE-068 gate):** nothing yet *authors* a
`silhouette`/`visual_diff`/`visual_critique` binding onto a generated
screen's `AcceptanceOracle` by default. The gate refuses correctly whenever
such a check is bound; binding one automatically for every generated-screen
task is DDE-065/067 authoring-surface territory and is carried into DDE-069.

**Durable ratification (done):** `EDR-0017` is persisted as an accepted
Project Truth row, not just a markdown pre-image. It was added to
`scripts/accept_owner_edrs.py` — the repository's authoritative versioned
representation of accepted owner decisions, from which any environment's
`edrs` table is provisioned — and the propose+accept path was run and the
row read back through `TruthRepository.get_edr_by_slug` (status `accepted`,
decided by the owner principal, four alternatives recorded, decision text
covering the rejection of the broad capability, the refusal to weaken
`STANDING_FORBIDDEN_TYPES`, the narrow capability's authority boundary, its
relationship to EDR-0016, its fail-closed classes and its bounded
unattended-use semantics). `tests/integration/test_accepted_edr_rows.py`
covers it automatically.

### DDE-069 — DDE Code / Frontend Studio V2 + Live Design Foundation

**State:** `IN_PROGRESS` (reconstructed 2026-09-05). Backend domain, M7
mutation/candidate/lock runtime, the host-neutral React shell, Frontend Chat
backend and DesignGateway are implemented. A code-backed prototype preview
runtime, stable PXG instrumentation, InspectorDescriptor projection and
mission-scoped Frontend Gateway reads are implemented. The canonical central
VS Code React workbench is now bound to that foundation for existing
code-backed candidates: browser-attested LIVE, stable `pxg_key` selection,
descriptor-driven token edit, preview invalidation and rerender are proven in
React/Playwright. Fresh candidate source-workspace onboarding, durable
DDE-068 verification requests, candidate-origin VerificationRun execution,
current request/run/check evidence in QA/Inspector, and the Cursor-class DDE AI
Chat control plane are implemented. Chat now owns durable multi-conversation
history/search/rename/archive/branching, Ask/Plan/Execute modes, honest model
selection, native opaque-token file attachments, governed plans, activity/tool
timeline, checkpoints, pinned context budgets and isolated-workspace diff review.
Deterministic execution still uses the same governed mutation seam and browser-
proves rerender + fresh DDE-068 re-verification. Production PostgreSQL-backed
workbench E2E, Screen Audit and M8 Source Intelligence are not complete.

**Current progress ledger.** `docs/truth/FRONTEND_STUDIO_BINDING_MATRIX.md` is
the authoritative per-control projection of
`docs/truth/golden/frontend_binding_matrix.json` v2. Final status is derived
from explicit `DOMAIN / READ / COMMAND / STATE / UI / WIRED / E2E / VISUAL`
evidence; backend files/tests cannot certify a missing React control or
production binding. At this tranche: **5 VERIFIED, 23 BOUND, 5
TYPED_UNAVAILABLE, 66 UNBOUND** of 99 rows. `tests/unit/test_frontend_binding_matrix.py`
validates the schema, evidence references, applicability and generated-doc
drift.

**Historical ledger snapshots (not current):** this file previously recorded
**9 VERIFIED / 14 TYPED_UNAVAILABLE / 76 UNBOUND** before later DDE-069
implementation landed. The v1 JSON reconstructed at HEAD `5f8c0c7` contained
**44 VERIFIED / 24 TYPED_UNAVAILABLE / 31 UNBOUND**, but its single status
axis allowed backend implementation/tests to mark a golden control VERIFIED
without a React UI. Both figures are retained here only to explain the drift;
neither is a completion claim under v2.

**Landed so far:**

- **M1 characterization** — `tests/unit/test_frontend_studio_characterization_postgres.py`
  freezes the DDE-067 refusals through the real command boundary: unknown
  `frontend.*` types refused rather than prefix-forwarded, `screen_file`
  traversal refused, foreign workspace = scope violation, token discipline
  on every writable style property, and replay-leaves-one-element.
- **M2 golden authority + ledger** — `engine/studio/golden_visual.py`,
  `engine/studio/binding_matrix.py`, `scripts/render_binding_matrix.py`
  (`--check` in `just contract-test`).
- **M5/M6 domain** — `engine/studio/pxg/`, `engine/studio/contract/`,
  `engine/studio/coverage/`, `engine/studio/reads.py`, migration `0024`.
  Commands `frontend.contract.publish`, `frontend.pxg.apply`,
  `frontend.coverage.recompute` on `mission.control`.
- **M7 mutation/lock/candidate runtime** — `engine/studio/locks/`,
  `engine/studio/candidates/`, `engine/studio/mutations/`, migration
  `0025`. One governed write path: inspector, chat, drag/drop, `/design`,
  template, source-import, agent and keyboard edits are the same
  `MutationRequest` and get the same answer. Candidate isolation is
  structural — the executor writes no accepted PXG nodes at all; a
  candidate's changes live in its append-only mutation log and its
  effective graph is that log projected over the accepted one
  (`mutations/projection.py`), so promotion is the only writer of accepted
  state. Commands: `frontend.candidate.create|transition|promote`,
  `frontend.mutation.apply|revert`, `frontend.lock.create|release`.
- **M3/M4 host-neutral workbench and golden shell** —
  `interfaces/dde-studio/ui/` (React 19 / TS / Vite, admitted in
  `docs/planning/dde-069-dependency-admission.md`). `DdeHostBridge` with
  VS Code and test implementations; `acquireVsCodeApi()` appears in exactly
  one file. Canonical tokens transcribed verbatim from
  `FRONTEND_STUDIO_REV3.md` Part I section 3, and the four-zone shell built
  on the section 2 measurements. 16 Playwright assertions at 1672x941 cover
  panel geometry, zone tiling, canvas dominance, the applied token values,
  responsive degradation, and the honest-state rules (an unknown count
  renders an em-dash with its reason; a partially assessed project shows no
  percentage; serving identity reads UNATTESTED; `Claude /design` is
  visible but disabled; the candidate strip carries no invented cards).
  Run with `just studio-visual`. Screenshot:
  `docs/evidence/dde-069/frontend-studio-shell-actual.png`.
- **M9/M10 Cursor-class DDE AI Chat + DesignGateway control plane** —
  `engine/studio/chat/`, `engine/studio/design/`, migrations `0026`, `0030` and
  `0031`, plus `FrontendChatComposer.tsx`. Chat is the AI-first control surface,
  not an authority bypass: it now supports durable multiple conversations,
  history/search/rename/archive/branching, Ask/Plan/Execute modes, honest model
  availability, managed file attachments, governed plans, activity/tool timeline,
  checkpoints, pinned context budgets and isolated-workspace changed-file review.
  Plan execution binds the exact future Gateway command, idempotency key and
  request hash before execution, then reconciles the real CommandLedger row; a
  retry gets a new attempt identity without changing the logical approved action.
  Native VS Code uploads use opaque picker tokens and extension-host byte upload,
  so the webview never acquires arbitrary local filesystem paths. Deterministic
  edits and undo still use `GovernedMutationService`; executed plan mutations also
  rerender and require fresh DDE-068 verification. `capability.claude_code_invoke`
  remains per-invocation human-approved and is not treated as an always-on model
  or a substitute `/design` transport. Source search remains typed unavailable
  until M8 and `@finding` remains fail-closed until Screen Audit. Evidence:
  `docs/evidence/dde-069/REACT_FRONTEND_CHAT.md` and
  `docs/evidence/dde-069/CURSOR_CLASS_AI_CHAT.md`.
- **Code-backed preview + Inspector foundation** — `engine/studio/preview_runtime/`,
  `engine/studio/inspector.py`, migration `0027`, and mission-scoped Frontend
  Gateway reads. `PrototypeHtmlPreviewAdapter` materializes actual candidate
  workspace code, applies the governed mutation log, instruments stable
  `pxg_key` anchors, and requires a content-hash/browser handshake before a
  preview session can become `LIVE`. Unsupported React/Vite source remains
  typed unavailable rather than being substituted with `srcDoc` demo HTML.
  `InspectorDescriptor` derives legal token values, source mapping, lock/stale
  writability and verification invalidation from real project state. The
  mutation planner now also refuses stale candidate bases and rechecks accepted
  PXG revision inside apply-time write authority. Evidence:
  `docs/evidence/dde-069/PREVIEW_RUNTIME_FOUNDATION.md`.
- **Central live React workbench loop** —
  `interfaces/dde-studio/src/webviews/frontendStudioWorkbenchPanel.ts` now
  implements the canonical section 5.3 central `WebviewPanel`; the six older
  Frontend Studio sidebar views are compatibility shims with an explicit open
  action. `VsCodeHostBridge` requests are translated by the panel onto
  `StudioGatewayService` / `GatewayApiClient` and the mission-scoped Core
  Frontend reads and `/v1/commands`, preserving the UI's idempotency key. The
  React workbench renders real candidate cards and PXG screens, loads the
  materialized candidate document in an `allow-scripts` sandbox, requires this
  browser to re-attest the content hash before displaying LIVE, resolves
  selection by stable `pxg_key`, reads `InspectorDescriptor`, applies token
  edits through `frontend.mutation.apply`, marks old preview sessions STALE,
  clears stale candidate verification attachment, rerenders and requires a new
  LIVE handshake. `npm run package` now builds and ships the React assets in
  the VSIX. Evidence: `docs/evidence/dde-069/LIVE_WORKBENCH_LOOP.md`.
- **Fresh candidate onboarding + verification requests** — project workspace
  inventory is now read from the real workspace owner and admits only READY,
  durable, non-candidate-preview workspaces. A unique source is auto-selected;
  multiple sources require explicit user selection and no source remains an
  honest EMPTY state. After hash-confirmed LIVE,
  `CandidateVerificationRequestService` resolves the candidate's effective PXG,
  existing screen AcceptanceOracle/version and bound verification kinds, then
  persists PENDING or BLOCKED without manufacturing a verdict. A later mutation
  supersedes outstanding requests before rerender. Schema/migration `0028`.
  Evidence: `docs/evidence/dde-069/SOURCE_AND_VERIFICATION_REQUESTS.md`.
- **Candidate DDE-068 execution + visible evidence** — schema/migration `0029`
  widens `VerificationRun` lineage to the Blueprint §17.1 subject model without
  fabricating WorkerRuns: worker-origin runs retain their WorkerRun/TaskAttempt
  lineage, while Frontend candidate runs use `subject_kind=FRONTEND_CANDIDATE`.
  `CandidateVerificationExecutionService` validates the exact latest LIVE
  preview/hash, rebinds only the runtime render URL while preserving immutable
  AcceptanceOracle/golden definitions, leases `capability.browser` and the
  narrow EDR-0017 `capability.visual_critique` through a non-worker checkout
  path that explicitly refuses WorkerRun-bound leases, and executes the shared
  DDE-068 runner/evidence writer. `frontend.verification.run` is mission-scoped.
  Promotion now consumes only the VerificationRun currently attached to that
  candidate, so historical task passes cannot approve edited code. React
  automatically executes a new PENDING request once per LIVE hash; Candidate
  cards, QA and Inspector expose current request/run/check/evidence state and
  never turn PENDING/BLOCKED/SUPERSEDED into VERIFIED. Evidence:
  `docs/evidence/dde-069/CANDIDATE_VERIFICATION_EXECUTION.md`.
- **DDE-068 carry-over CLOSED** — see the dedicated subsection below.

**Still incomplete / not started:** M8 source adapters, provenance and candidate
scoring; general React/Vite/Expo PreviewRuntimeAdapters beyond admitted
prototype HTML; production VS Code → Gateway → PostgreSQL live-loop evidence
(current host has no database/Redis runtime; the new PostgreSQL candidate-run
persistence test is therefore present but UNAVAILABLE locally); exact viewport
`set_state`, resize handles and Inspector tab-specific golden contracts not yet
matched by the current generic controls; mandatory Screen Audit
domain/projections/Coverage-QA-Architecture integration and dogfood; cross-DDE
migration (M12); mobile adapters (M13).

#### `Claude /design` — BLOCKED_EXTERNAL on a certified transport

The DesignGateway, `DesignEditContext` compiler, provider registry,
artifact lifecycle and Try-live path are implemented and tested. What does
not exist is a **certified design transport**. `FRONTEND_STUDIO_REV3.md`
section 23 requires a structured one — a direct Claude Design MCP/OAuth
transport preferred, a certified Claude Code `/design` WorkerSession
transport allowed — and forbids by name substituting a generic
code-generation prompt.

`ClaudeDesignProvider` therefore reports `NOT_CERTIFIED` with that reason,
and `DesignProviderRegistry.resolve` refuses with no fallback path in the
code at all. Deliberately **not** routed through
`capability.claude_code_invoke`: that capability grants arbitrary
development execution against a human's own rate-limited seat and keeps
its mandatory per-invocation approval for that reason (EDR-0001 Path A,
EDR-0017), and using it here would be exactly the substitution section 23
forbids.

**To unblock:** register a certified transport implementing the
`DesignProvider` protocol (`engine/studio/design/providers.py`). Everything
downstream — session, context allowlist, artifacts, quarantine, Try live,
candidate isolation, DDE-068 verification, promotion — is already wired and
proven against a stub transport in
`tests/unit/test_design_gateway_postgres.py`.

**Deliberately honest gaps at this snapshot.** Candidate thumbnails, scores,
Try-live and compare do not exist as functional React controls. The current
candidate strip renders an explicit `NOT_IMPLEMENTED` state and deliberately
shows no Direction A/B/C cards at all. A real prototype-HTML preview runtime
now exists behind Core/Gateway, but the React candidate strip does not consume
it and `CandidateScorecard` still does not exist. Backend candidate/Try-live operations are real,
but they are not counted as UI completion (FRONTEND_STUDIO_REV3 section 17.2
forbids fabricated scores).

#### Golden visual artifact — BLOCKED_EXTERNAL

AD-035 names a user-approved 1672x941 Frontend Studio mockup as the
canonical visual baseline. **The image has never existed in this
repository** — verified 2026-09-04 by `git log --all --name-only` across
every ref and path; the only committed mockup is
`interfaces/dde-studio/docs/dde-mission-overview-mockup.png` at 1536x1024,
a different and earlier artifact.

Prose describing an image is not the image, so DDE distinguishes two
claims and refuses to conflate them (`engine/studio/golden_visual.py`):

- `STRUCTURAL` conformance to the normative measurements in
  `FRONTEND_STUDIO_REV3.md` Part I sections 2-5 (58px top bar, 44-48px
  rail, 215-225px explorer, 310-325px inspector, 32-36px status bar, and
  the palette/type/radius/shadow tokens) — checkable now, and what M4 will
  be held to;
- `PIXEL_REFERENCE` conformance to the approved image —
  `require_pixel_reference()` raises `CONTEXT_INCOMPLETE` while the
  artifact is absent, and no visual signoff may claim it.

**To unblock:** commit the approved image at
`docs/truth/golden/frontend-studio-shell.png` and record its sha256 in
`docs/truth/golden/GOLDEN_VISUAL_MANIFEST.json`. The state machine then
reports `PINNED` with no code change.

#### Inherited dependency #1 — visual bindings on generated screens: CLOSED

DDE-068 recorded this as deliberately carried into DDE-069. It is now
closed.

`schemas/design/screen_acceptance_defaults.json` is the versioned,
inspectable policy (FRONTEND_STUDIO_REV3 section 42) naming `silhouette`
and `visual_critique` mandatory for both `generated_screen` and
`imported_screen` profiles, each with a stated rationale. `visual_diff` is
optional by design: binding it with no approved golden would fail closed
on every run for the wrong reason.

`engine/studio/acceptance/defaults.py` builds the bindings and
`assert_mandatory_bindings` refuses an oracle missing one, so an authoring
path that assembles its own spec list cannot quietly drop
`visual_critique`. `ScreenAcceptanceService.register_screen` registers the
screen in the PXG and authors its `AcceptanceOracle` in one step, failing
closed before any write — a refused binding leaves no screen in the graph.

The production call site is the Gateway command
`frontend.screen.register`, proven end to end in
`tests/unit/test_screen_acceptance_binding_postgres.py` (the oracle is read
back from PostgreSQL carrying both visual bindings).

Because the promotion gate DDE-068 built is kind-agnostic and already
refuses on any bound visual check, authoring the binding by default
converts that mission's conditional guarantee — *"a bound check refuses"* —
into the universal one — *"every generated screen is checked"* — without
modifying the gate.

**Domain authority:** `docs/truth/FRONTEND_STUDIO_REV3.md` (adopted 2026-09-03, AD-036), reconciling and superseding `docs/planning/frontend-studio-gui-spec.md`'s never-formally-adopted mission definition. Golden visual authority (light-first) is recorded separately as AD-035.

**Naming-drift note (resolved 2026-09-03):** earlier snapshots of this file described DDE-069 as "Mobile/Multi-target Profiles, `DEFERRED`." That description was accurate to `ARCHITECTURE_DECISIONS.md`/`RESUME_PROMPT.md` at the time but went stale the moment `DEV_PLAN_REV3.md` §6 was rewritten same-day (commit `b5753db`, "docs: adopt Rev 3.3 orchestrator attestation truth") to define DDE-069 as the Frontend Studio V2/live-design mission — a rewrite this file, `ARCHITECTURE_DECISIONS.md`, and `RESUME_PROMPT.md` were never updated to match. AD-030 now records the resolution. Mobile is not dropped: `FRONTEND_STUDIO_REV3.md` folds it in as a governed sub-capability (§11.6 mobile source adapters, §26 Expo/device runtime verification, migration phase M13) rather than a separately numbered deferred mission.

**Required before completion** (from `FRONTEND_STUDIO_REV3.md` Part XVIII "Definition of Done," summarized): host-neutral React/TS/Vite workbench behind `DdeHostBridge`; production PXG/Frontend Contract/Coverage Engine; one unified mutation/lock/candidate-isolation path across chat, direct edit, templates and agents; governed source adapters (internal, 21st, donor, mobile) through the Design System Compiler; `Claude /design` as a first-class control sharing one DesignSession with Frontend Chat; DDE-068 visual verification gating promotion (not optional — see FRONTEND_STUDIO_REV3.md's own "DDE-068 DEPENDENCY" clause); every visible golden-mockup control bound to a real capability or an explicit honest unavailable state; cross-DDE shell migration for all other DDE windows.

Do not expand targets, and do not begin DDE-069 implementation proper, before the DDE-068 quality loop is stable enough to avoid multiplying an immature pipeline.

**Entry gate: OPEN (2026-09-04).** DDE-068 is `COMPLETE_EVIDENCED` with a
live end-to-end run, and `EDR-0017` is an accepted Project Truth row. The
"do not begin before the quality loop is stable" condition above is
satisfied: the loop is built, enforced, and exercised on real pixels.

**Cold-start entry packet for DDE-069.** A fresh session needs no
conversation history; everything below is reconstructable from the
repository.

- **Base commit:** DDE-068 closure lands on `main`; read
  `docs/evidence/dde-068/README.md` plus this file's DDE-068 section for
  what was proven and how.
- **Governing decisions:** `EDR-0016` (what visual verification requires)
  and `EDR-0017` (how DDE safely obtains machine multimodal critique —
  accepted Option C). Both are accepted rows; `EDR-0017`'s guardrails are
  binding on any further critic work: `capability.claude_code_invoke` is
  never weakened, `STANDING_FORBIDDEN_TYPES` is never bypassed, no generic
  "narrowness" exemption is created, provider abstraction stays behind
  `adapters/**`, and `Claude /design` stays architecturally distinct from
  the independent visual critic even where one model family serves both.
- **Inherited dependency #1 — visual bindings on generated screens.**
  **RESOLVED 2026-09-04** — see the DDE-069 section above; retained here as
  the historical statement of the gap.
  DDE-068 delivered the capability *and* its enforcement: any oracle
  carrying a `visual_diff`/`silhouette`/`visual_critique` binding is
  machine-gated at promotion (proven in
  `tests/unit/test_silhouette_promotion_gate_postgres.py` and
  `tests/unit/test_visual_critique_promotion_gate_postgres.py`). What does
  not yet exist is anything that *authors* such a binding onto a generated
  screen's `AcceptanceOracle` by default. This is deliberately DDE-069's,
  not a reopened DDE-068 item: `FRONTEND_STUDIO_REV3.md`'s "DDE-068
  DEPENDENCY" clause assigns "the final DDE-069/Frontend Studio V2
  promotion must consume real rendered visual verification" to this
  mission, and its implementation order step 3 is "close/consume DDE-068
  prerequisites needed by V2". Until it is done, the guarantee is
  conditional ("a bound check refuses") rather than universal ("every
  generated screen is checked") — DDE-069 is what closes that gap. The
  authoring surfaces to wire it through are DDE-065's generation-prompt
  compiler and DDE-067's Frontend Studio authoring path.
- **Inherited dependency #2 — approvals surface for escalation.**
  `prototype_pixel_signoff` exists, is standing-forbidden, and
  `StudioFrontendService.request_pixel_signoff` creates a real scope-bound
  `Approval`. DDE-069 should surface that request and its decision in the
  Frontend Studio UI rather than leaving it API-only.
- **First executable packet** (per `FRONTEND_STUDIO_REV3.md` implementation
  order steps 0–2, which precede any new runtime): preflight branch/HEAD
  and focused baseline tests; reconcile any truth drift without creating
  duplicate authority; preserve DDE-067 contract tests and add
  characterization tests around the current Gateway/frontend mutation path.
  Only then step 4's host-neutral React/TS/Vite runtime, behind dependency
  admission.
- **Verification gates for DDE-069 work:** the repo's full check suite
  (`just check`: lint, format, typecheck, unit, contract, design-lints,
  studio-check) plus `tests/integration/test_accepted_edr_rows.py` where
  Project Truth changes, plus a live evidence run for anything claiming
  visual verification of a real screen. `just check` green is necessary but
  is not chapter sign-off.

---

## 4. Worker/orchestration state

### Fable 5

**State:** `BLOCKED_EXTERNAL`.

Rev 3 defines Fable 5 as the preferred strategic orchestration worker **when a supported interface exists**. No repository evidence currently proves a functioning Fable adapter.

Next actions when available:

- define/extend generic worker profile capabilities;
- implement adapter only behind that contract;
- benchmark against alternative planner profiles;
- route outputs through draft -> validate -> promote;
- never persist authoritative state in Fable memory.

### Hermes

**State:** `IMPLEMENTED_PARTIAL`.

Current repository evidence:

- `engine/routing/registry.py` includes `HARNESS_HERMES`;
- DDE Code includes Hermes Mission Control/harness UI surfaces;
- packaging/README describes Hermes alongside other worker dashboards.

Rev 3 gap:

- make its persistent research/context/recovery responsibilities explicit in profile policy and production workflows;
- prove capability/credential containment;
- ensure Hermes working memory always rehydrates authoritative facts from DDE;
- collect routing quality/cost telemetry for Hermes task classes.

### Claude Code

**State:** `IMPLEMENTED_PARTIAL`.

Rev 3 gap:

- explicit high-complexity/high-risk task eligibility;
- quota-aware routing rather than default premium absorption;
- independent review policy;
- measured quality/cost comparison.

### DeepSeek

**State:** `IMPLEMENTED_PARTIAL`.

Rev 3 gap:

- explicit bounded/mechanical task eligibility;
- deterministic arbitration of parallel candidates;
- quota/health telemetry and fallback behavior.

---

## 5. Known open/partial governance items at DDE-067 handoff

The DDE-067 chapter gate records the following as unchanged/open at that point:

- EDR-0002;
- EDR-0003;
- EDR-0005;
- EDR-0027;
- EDR-0033.

Do **not** infer their final status from this summary. Read the corresponding Project Truth/EDR record before changing affected behavior.

The gate also records missing D3 list/read endpoints for some Studio surfaces. Until contracts exist, UI must remain honest rather than synthesizing rows.

---

## 6. Current risks

### RISK-01 — Documentation/code authority drift

**Current status:** mitigated for bootstrap. `AGENTS.md` and `README.md` now point to the Rev 3 truth set.

**Residual:** future architecture changes must keep all five truth files synchronized through change control.

### RISK-02 — DDE-068 evidence becomes disconnected from DDE-069

DDE-068 is complete and evidenced, but a Frontend Studio preview/promotion loop that does not actually invoke those gates would recreate a quality-theatre path.

**Mitigation:** every code-backed candidate promotion path in DDE-069 must consume the real DDE-068 verification verdicts and preserve their fail-closed classes.

### RISK-03 — Premium-model quota transfer

If Fable is unavailable, there is a temptation to make Claude Code absorb orchestration plus implementation plus review.

**Mitigation:** deterministic planning/validation + Hermes research + lower-cost bounded workers + premium escalation only for high-value reasoning.

### RISK-04 — Hermes UI presence mistaken for complete Hermes orchestration

A harness card/room is not proof of the full runtime role.

**Mitigation:** keep state `IMPLEMENTED_PARTIAL` until routing, capabilities, recovery and telemetry prove the Rev 3 role.

### RISK-05 — Frontend quality overclaim

DDE-068 is `COMPLETE_EVIDENCED`, but DDE-069 can still overclaim frontend quality if its real workbench does not consume those gates.

**Mitigation:** no `Definition of Polished`, LIVE, VERIFIED or promotion claim from shell/backend evidence alone; DDE-069 must execute the DDE-068 gates on code-backed candidate renders.

---

## 7. Immediate next work packet

Unless newer implementation evidence exists:

**Mission:** DDE-069 — Screen Audit & Experience Completeness Engine.

The live candidate/verification loop and permanent React Frontend Chat control
plane are now composed and browser-proven. Do not rebuild them. Production
PostgreSQL E2E is still unavailable on this host and remains BOUND.

Next:

1. read `docs/truth/SCREEN_AUDIT_ENGINE.md` in full and implement the canonical
   ScreenAuditRun/ScreenRecord/Finding/Evidence/Resolution persistence model;
2. derive findings from existing Frontend Contract, PXG, journeys/routes, roles,
   locks, DDE-068 verification and source/runtime evidence without fabricating
   unavailable dimensions;
3. implement incremental audit invalidation keyed to affected PXG/screen/
   candidate evidence rather than recomputing or silently preserving stale facts;
4. project audit truth into Coverage/QA/Architecture plus Canvas/Inspector markers
   and extend the landed Chat control plane with audit queries/repair context;
5. dogfood Screen Audit against DDE Frontend Studio and reconcile its findings
   with the 99-control binding ledger instead of forcing either system to agree.

After Screen Audit is green, implement M8 Source Intelligence. Pixel-reference
conformance remains fail-closed under AD-039 and does not block functional work.

---

## 8. Update protocol

At the end of every meaningful implementation tranche:

1. record new head/commit;
2. change only states supported by evidence;
3. list production call sites added;
4. list tests/verification evidence;
5. record residuals/blocks;
6. update immediate next work packet;
7. if architecture changed, update Blueprint/Decisions through the proper EDR/change-control path.

Never erase an earlier limitation simply because later intent says it should be fixed.