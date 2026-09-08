# DDE Implementation State — Rev 3

**Status:** CANONICAL CURRENT-STATE SNAPSHOT
**Snapshot date:** 2026-09-08
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

This file originated as the close-out of the R3-0 source-of-truth migration.

### Latest observed DDE-069 implementation baseline

The latest committed DDE-069 baseline is `e4347df` — **DDE-069 close unbound frontend controls** — on `main`. Its parent `09c4249` lands governed review comments, preview scenarios, editor-assist policy, attention acknowledgements and migration `0036`. The earlier consolidated design/source baseline was `843c61e`; host integration commits include `0f9a236` (PostgreSQL/Redis closure) and `645a6f2` (Candidate Dock functional loop).

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
| DDE-069 DDE Code / Frontend Studio V2 + Live Design Foundation | `IN_PROGRESS` | Canonical domain: `docs/truth/FRONTEND_STUDIO_REV3.md` (AD-036). Real PostgreSQL 16.15/Redis 7.0.15 integration, M7 candidate/mutation/lock runtime, host-neutral React workbench, code-backed preview, DDE-068 candidate re-verification, Screen Audit, Universal DDE Chat/AI Conversation Fabric, functional Candidate Dock and six-tab semantic Inspector are landed. `CT-06` Claude `/design` transport/control is live-certified against the official Claude Design MCP; deterministic DesignArtifact token proposals materialize atomically through the ordinary mutation engine with stale-PXG and promotion-lineage checks. The installed-VSIX VS Code → React webview → Gateway → PostgreSQL path now proves project switching, deterministic Chat, READY candidate projection, browser-attested LIVE preview, stable PXG selection, lock creation/chips, responsive restart, and reviewed Inspector/source/accessibility reads. Production-only preview CSP/handshake defects found by that gate are repaired without weakening target-app CSP. `CA-07` Direction cards and selected-artifact Try Live remain UI/VISUAL verified but its exact `frontend.design.try_live` command still needs the packaged-host action before WIRED/E2E promotion. Source Intelligence has real PostgreSQL lifecycle proof plus live read/fetch/hash certification for shadcn/ui, ReUI, Magic UI and Aceternity UI through a generic public-registry adapter; 21st is optional/NOT_CONFIGURED rather than a DDE-069 blocker. Current 99-control ledger derives **42 VERIFIED / 48 BOUND / 9 TYPED_UNAVAILABLE / 0 UNBOUND**. AD-039 remains repository-blocked even though the exact 1672×941 artifact was externally recovered and hash-identified; live R2 certification still requires complete correctly classified scoped credentials. |
| Production VEKL for target-application manufacturing | `IMPLEMENTED_PARTIAL` | Blueprint §26A / AD-048 remain canonical and DDE-075/076/077/080/081/082/083 remain the locked owning missions. The common runtime foundation plus the DDE engineering-playbook/OpenAI discovery tranche are implemented: schema-generated resource/stack/signature/activation/outcome contracts, migration `0038` + RLS, target-app-only scope, Source Intelligence admission with no new egress, Workspace-derived stack facts, hard eligibility, immutable failover with task-signature-drift invalidation, ContextPackage integration, capability/effect-bound executable and hook runtime, bounded loops, Gateway projection/commands, 16 DDE Skills, 14 explicit task archetypes, 12 evidence gates, 7 hook policies, three-Skill activation ceiling, Claude delivery materializers with no tool/completion authority, and a pinned metadata-only OpenAI/ChatGPT/Codex catalogue (10 selected plugin families / 98 Skills plus component-surface presence). Local non-service proof remains green at 54 focused tests, 731 pure unit (5 skipped; 562 integration deselected), 223 contract, MyPy 581, extension/shared 77/77 and Frontend Studio 79/79. Service-capable CI run `34234702640` now additionally proves **6/6 VEKL PostgreSQL tests**, **1550 passed / 7 skipped** across database-backed unit+contract+recovery, **5/5 integration**, generated drift clean, and a live reversible Alembic `head -> base -> head` cycle including `0038 -> 0037 -> ... -> 0038`; Windows is green in the same run. This remains `IMPLEMENTED_PARTIAL` because the complete DDE-081 VEKL workbench, DDE-082 qualified executable adapter/authoring fleet and DDE-083 integrated adversarial/release certification are not claimed complete. |
| Same-host DDE/Dial isolation | `IMPLEMENTED_PARTIAL` | On the current authorized host, DDE uses a dedicated Bubblewrap-backed terminal/home/Claude profile and DDE-only console entrypoint. The DDE repo is mounted; `/srv/dial/repo` and shared `~/.hermes` are not. DDE provider login/MCP configuration is therefore separate from global/Dial state. This is host-specific implementation evidence for AD-045, not a claim that every future installer/runtime already enforces equivalent isolation. |
| Fable 5 strategic orchestration profile | `BLOCKED_EXTERNAL` | Rev 3 role is defined, but no actual Fable 5 adapter/runtime integration was found in the observed repository state. Implement only when a supported interface is available and testable. |
| Hermes persistent research/coordination role | `IMPLEMENTED_PARTIAL` | AI Conversation Fabric now discovers the installed Hermes runtime, requires evidence-backed endpoint certification, and has a fail-closed ACP client. DDE-managed Hermes ACP context isolation is proven with `--ignore-rules`; shared approved DDE memory is object-backed (R2 when configured) and replaces duplicate provider-private memory injection. Full downstream Hermes experience/fleet acceptance gates remain in DDE-075/076. |
| Claude Code worker integration | `IMPLEMENTED_PARTIAL` | DDE Code/packaging references Claude Code worker setup; Rev 3 quota-aware specialization and independent-review routing still require explicit implementation/evaluation. |
| DeepSeek worker integration | `IMPLEMENTED_PARTIAL` | Harness/profile references exist; Rev 3 lower-cost delegation policy and measured routing specialization remain to be proven end-to-end. |
| Frontend Studio professional Rev 3 redesign | `IMPLEMENTED_PARTIAL` | Host-neutral React shell/canonical composition, code-backed live preview, functional Candidate Dock, six-tab semantic Inspector, DDE-068 candidate re-verification, Screen Audit, Universal DDE Chat and Source Intelligence vertical slices exist. Isolated PostgreSQL/Redis integration is proven; public registry transports are live-tested. Remaining partials include packaged production-host E2E for CA-07 and other applicable rows, remaining binding-ledger controls, AD-039 pixel pinning, design-system sync/structural implementation handoff and later migration/hardening. |
| Routing intelligence / learned policy promotion | `IMPLEMENTED_PARTIAL` | Existing routing registry/telemetry/learning planning exists; open EDR/partial implementation records require careful production-call-site audit before claiming full adaptive routing. |
| Context optimization / repository memory | `IMPLEMENTED_PARTIAL` | Universal DDE Chat now uses policy-bounded managed context: protected live authority, explicit refs, APPROVED ranked memory, warm/cold history budgets, deterministic compaction and durable ContextSnapshots. Memory/context bodies use scoped content-addressed storage with R2 production support and local fallback. Task-level Context Intelligence remains separately authoritative for Task ContextPackages, and live R2/PostgreSQL deployment proof is environment-dependent. |
| Windows complete installer / DDE Code distribution | `IMPLEMENTED_PARTIAL` | README and packaging describe DDE Code + Core/Postgres/Redis/migrations/wizard paths; release/recovery/signing/operational hardening remains a Rev 3 phase. |

---

## 2A. Production VEKL runtime foundation — implemented partial (2026-09-08)

The reviewed VEKL v1 pack is no longer only a future architecture input. The current
working tree implements the common runtime substrate needed by its locked owning
missions without creating a parallel mission series or control plane.

**Implemented now:**

- schema-first, generated and tenant/project-scoped VEKL resource, stack, task-signature,
  activation-manifest/invalidation and resource-outcome authorities with migration `0038`
  and RLS; activation continuity now also invalidates rather than reusing a prior manifest
  when the bound `TaskSignature` changes;
- explicit `projects.kind` classification and typed `VEKL_SCOPE_VIOLATION` for
  application-manufacturing VEKL against the DDE control plane;
- Source Intelligence admission/provenance reuse. External `source_uri` records must bind
  current admitted Source Intelligence state and the existing EDR-0015 allowlist before
  qualification; this tranche adds **no** network source or worker open-web path;
- production Gateway fingerprint construction from an existing scoped DDE `Workspace`.
  The Gateway does not accept caller/model `observed_facts`; bounded manifest/lock/runtime
  files are mechanically read and content-hash evidenced;
- deterministic TaskSignature, hard eligibility before ranking, exact-version/stack/truth
  compatibility, prompt-injection/stale-security/offline/budget/scope gates and immutable
  `VEKLActivationManifest` failover. Project Truth, policy, stack, resource pin, source
  admission or revocation drift appends invalidation and refuses silent reselection;
- `VEKLKnowledgeCompiler` plus `ContextExtension` binding into the ordinary
  `ContextService` budget/hash/`ContextPackage`, preserving one context authority;
- narrow read/planning VEKL capabilities and a generic executable-component seam that
  re-checks TaskSignature scopes, requires the existing `CapabilityLease`, journals
  non-read effects through `ExternalEffectService` before invocation and leaves uncertain
  non-idempotent/irreversible outcomes `UNKNOWN` rather than retrying;
- hash-bound Instruction IR, scope-bound Hook IR and verifier-terminated bounded loops
  whose declared measured budgets are reserved before a step, required checkpoints must
  have a writer, and declared rollback runs on exhaustion;
- verifier/evidence-backed `VEKLResourceOutcome`, candidate-only Hermes integration and a
  mission-scoped Gateway/Studio read projection for Stack Map, Knowledge, Tools/Plugins/
  MCP, Rules/Hooks, Loops, Community Evidence, Security and Learning;
- DDE-owned engineering playbook distilled from the internal VEKL/DIAL knowledge-layer
  material and current first-party Anthropic engineering guidance: 16 content-addressed
  DDE Skills, 14 explicit task archetypes, 12 evidence gates and 7 hook policies;
  archetype policy is bound into the existing `TaskSignature`, exact Skills are resolved
  through the ordinary ActivationManifest, minimal activation is capped at three Skills,
  and `vekl.playbook.install_candidates` registers candidate-only resources without egress;
- pinned OpenAI ChatGPT/Codex plugin discovery catalogue at `openai/plugins` commit
  `1e285826e604f66f7208f7ac4dba0fe8341d1f57`: 10 high-value engineering bundles and
  98 direct Skill paths are represented as DDE-authored `PACKAGE_METADATA` /
  `S7_DISCOVERY_ONLY` candidates. The snapshot also records component-surface presence
  (10 Skill/agent, 7 script, 4 MCP, 3 app and 1 command bundle occurrence) without
  materializing those components. `vekl.openai.install_catalog_candidates` persists this
  metadata without fetching Skill bodies, installing plugins, connecting apps/MCP servers,
  or granting network/filesystem/secret/execution authority. Personal/community Skill names
  such as `AppCreator` are deliberately not classified as OpenAI first-party without exact
  provenance and must enter the normal Source Intelligence/qualification path;
- Claude adapter materialization for generated `SKILL.md`/`CLAUDE.md`/command hooks.
  Generated Skills disable model auto-invocation and grant no tools; provider hook settings
  are defense in depth and never replace DDE's hard capability/effect/completion controls.

**Verification in the current bare host:** 54 focused VEKL/playbook/contract tests pass;
the pure unit suite passes 731 with 5 skipped and 562 integration tests deselected; all
223 contract tests pass; extension/shared tests pass 77/77; strict MyPy passes over 581
source files; desktop/UI TypeScript checks and the React/Vite production build pass; the
full Frontend Studio Playwright suite passes 79/79, including the canonical 1672×941
Chat/Source Apply hit-test. Ruff, generated-contract/design-token/binding drift checks and
the committed design-lint ratchet are green. The recovery suite was also invoked: its three
non-service checks pass and 33 database-backed checks fail immediately because this host
has no configured `DDE_DATABASE_URL`/`DDE_REDIS_URL`; those are environment-unavailable,
not accepted PASS evidence.

**Service-capable closure:** this particular shell still has no PostgreSQL/Redis service,
but CI run `34234702640` now supplies the missing runtime evidence: all **6/6** VEKL
PostgreSQL tests pass; the database-backed unit+contract+recovery gate is **1550 passed /
7 skipped**; integration is **5/5**; and Alembic completes `head -> base -> head`, including
a real `0038 -> 0037` rollback and final `0037 -> 0038` upgrade. The common runtime
foundation still does not by itself mark DDE-075/076/077/080/081/082/083 complete;
harness-specific executable adapters, the complete Production Studio VEKL authoring/
inspection experience, eval/shadow/canary learning promotion and DDE-083 adversarial
release certification retain their existing mission ownership. Evidence:
`docs/evidence/vekl/VEKL_RUNTIME_FOUNDATION_2026-09-08.md`.

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

**State:** `IN_PROGRESS` (consolidated 2026-09-06). The DDE-069 foundation is
now materially beyond the earlier reconstruction snapshot. Real PostgreSQL 16.15 and
Redis 7.0.15 are proven on an isolated DDE-only host runtime. The host-neutral React
workbench, code-backed preview handshake, stable PXG selection, candidate mutation
projection, DDE-068 candidate verification, Screen Audit and Universal DDE Chat / AI
Conversation Fabric are implemented on runnable surfaces. Candidate Dock actions are
functional for existing candidates, and the Inspector now exposes the six canonical
tabs with semantic layout/token controls, real lock inventory/create/release,
responsive preview, source/provenance and accessibility evidence.

**Recovery checkpoint (2026-09-07):** a cross-mission contract collision introduced during DDE-069 had reused the DDE-057/058 routing-learning `ExperienceRecord` / `experience_records` authority for Blueprint §6.3 execution experience. The recovery preserves both capabilities: routing learning again owns `ExperienceRecord` / `experience_records`, while AI Conversation Fabric uses `ExecutionExperienceRecord` / `execution_experience_records`. Migration `0035` preserves collided deployed data and the current canonical split; a throwaway PostgreSQL proof completes `upgrade head -> downgrade base -> upgrade head` without `CASCADE`. Fresh CI now provisions accepted EDR-0001..EDR-0017 through the existing `scripts.accept_owner_edrs` / `TruthService` sole-writer path before integration. The final uninterrupted recovery G1 is GREEN: Ruff/format/mypy, 1489 Python tests passed with 6 skipped, 220 contract tests passed, extension 77/77, desktop and React TypeScript checks, Vite production build, exact migration cycle, and fresh integration 5/5. This is a recovery checkpoint only; it does not close DDE-069 or any remaining golden binding. Evidence: `docs/evidence/dde-069/RECOVERY_FEATURE_PRESERVATION.md`.

**Desktop dependency security checkpoint (2026-09-07):** the DDE Code desktop dependency graph was upgraded from Electron 33 / electron-builder 25 to Electron 44.2.0 / electron-builder 26.15.3. The previously observed 15 npm advisories (1 moderate, 13 high, 1 critical) are now **0**. Electron 44's asynchronous clipboard API is awaited at both local secret-ingress boundaries without changing safeStorage/session-token custody. The uninterrupted validation is GREEN: Ruff/format/mypy, **1491 Python tests passed with 6 skipped**, 220 contract tests, extension 77/77, desktop TypeScript, Windows x64 unpacked packaging, React TypeScript and Vite production build. This closes desktop dependency security debt only; row-specific packaged-host browser actions, AD-039 and live R2 remain independent gates. Evidence: `docs/evidence/dde-069/DESKTOP_DEPENDENCY_SECURITY.md`.

**Packaged VS Code host baseline (2026-09-07):** `npm --prefix interfaces/dde-studio run test:host-e2e` now builds and installs the real VSIX into isolated VS Code 1.95.3, opens the contributed Frontend Studio command from the real command palette, and proves the React webview reads the freshly persisted project and `screens/checkout` through the production host bridge, real Gateway and throwaway PostgreSQL database at Alembic head. The first database-backed run exposed and repaired a real `frontend_templates` object-store schema drift; canonical schema plus migration `0037` now pass fresh-head, affected-0036 repair and `head -> base -> head`. This closes the environment-level packaged-host gap only; each BOUND control still requires its own read/action/state to be asserted through that path before promotion. Evidence: `docs/evidence/dde-069/PACKAGED_VSCODE_HOST_E2E.md`.

`CT-06` Claude `/design` is live-certified at the transport/control boundary. The
first certified transport uses the official Claude Design MCP through a dedicated,
non-interactive, fail-closed DDE transport and never substitutes broad
`capability.claude_code_invoke`. DesignArtifact proposals are now additionally
validated against exact exported token/materialization vocabulary and can materialize
atomically into isolated candidate mutations with stale-PXG refusal and pinned
promotion lineage. The previously recorded `CA-07` UI gap is now reconciled from repository evidence: persisted Direction A/B/C cards, selected-artifact Try Live, browser-backed LIVE content and the fresh DDE-068 rerun are implemented and Playwright-proven. `CA-07` is still **BOUND**, not VERIFIED: the packaged VS Code/Gateway/PostgreSQL baseline is recorded, but the selected-artifact Try Live action and its durable candidate/LIVE/verification result have not yet been exercised in that packaged run. A strengthened real-provider rerun after the manifest hardening reached a
CERTIFIED provider but ended `PROVIDER_ERROR` before a successful result; its failed
run is preserved separately and must not overwrite the earlier passing transport
certificate.

M8 Source Intelligence now includes project-native/DDE-library/donor/21st support plus
a generic read-only public shadcn-compatible registry federation. Live network evidence
exists for shadcn/ui, ReUI, Magic UI and Aceternity UI, while the persisted M8 lifecycle
has separately passed on real PostgreSQL. 21st remains supported but optional; its
absence degrades one provider instead of blocking Source Intelligence. External-source
full lifecycle E2E with the live public adapters is still a separate proof obligation.

The exact AD-039 golden artifact has been recovered outside the repository (1672×941,
1,492,542 bytes, SHA-256
`8e24bb34e5fb5723bbc9e44c2716f05300f5f4e95f463770349f05fdba8a6377`) but is not yet
committed/pinned, so PIXEL_REFERENCE conformance remains fail-closed. Live R2 also
remains uncertified until the private host has a complete, correctly classified scoped
credential set and a live put/read/hash probe passes.

**Current progress ledger.** `docs/truth/FRONTEND_STUDIO_BINDING_MATRIX.md` is
the authoritative per-control projection of
`docs/truth/golden/frontend_binding_matrix.json` v2. Final status derives from explicit
`DOMAIN / READ / COMMAND / STATE / UI / WIRED / E2E / VISUAL` evidence; backend files
cannot certify a missing React control or production binding. The current derived
snapshot is **42 VERIFIED / 48 BOUND / 9 TYPED_UNAVAILABLE / 0 UNBOUND** of 99 rows.
The installed-VSIX proof now closes `CT-01`, `CV-01`, `CV-02`, `CV-04`, `CV-06`,
`CV-07`, `CA-01`..`CA-06`, `IN-01`, `IN-06`, `IN-07`, `IN-13`, `IN-15`,
`IN-16`, and `ST-01` in addition to the earlier project/Explorer/status/Chat rows.
That run uses fresh PostgreSQL at migration head, a real packaged extension, a DDE-owned
READY candidate workspace, browser hash attestation, real lock commands and a replacement
390px preview session. The headless VS Code CDP target cannot inject a physical click into
the doubly nested `srcdoc`; host-neutral Playwright remains the physical-click proof while
the installed-host leg dispatches the same production click event and proves runtime →
postMessage → React/Inspector. This limitation is evidence-scoped, not a product bypass.
`CA-07` remains BOUND specifically because its contract is `frontend.design.try_live`
from a persisted DesignArtifact, which this candidate-preview batch does not execute.
Inspector write controls (`IN-02`, `IN-03`, `IN-08`, `IN-09`, `IN-10`, `IN-11`),
comments (`CT-04`), resize (`CV-05`), scenario simulation (`CV-08`), assist/status and
other unexercised packaged-host actions remain BOUND until their exact command/result path
is run. `EX-22` remains honestly TYPED_UNAVAILABLE whenever accessibility is not evaluated
for every current audited screen. AD-039 and live R2 remain separate external closure gates.

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
  percentage; serving identity reads UNATTESTED; `Claude /design` renders
  its real provider state and enables only on `CERTIFIED`; the candidate
  strip carries no invented cards).
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
  or a substitute `/design` transport. Governed source search now routes through the
  M8 Source Intelligence adapters and reports per-provider degradation. `@finding` now resolves current Screen Audit evidence and rejects stale
  findings. Evidence:
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
- **Screen Audit & Experience Completeness Engine** — migration `0033` and
  `engine/studio/audit/` implement exact-input full/incremental audit runs, durable
  screen records/findings/evidence/resolutions, deterministic Contract/PXG/Coverage
  reconciliation, accepted DDE-068 evidence binding, dependency-directed staleness,
  accepted-change refresh and durable exception authority. Coverage renders the
  Screen Matrix; QA renders findings plus DDE-068 evidence; Architecture renders
  real audit overlays; Inspector renders selected-screen audit dimensions; universal
  DDE Chat answers audit queries and resolves `@finding`. Candidate-local edits do
  not stale accepted-product audits; promotion does. The dogfood reconciler keeps
  the independent 99-control ledger and records disagreement rather than forcing
  agreement. At that historical Screen Audit checkpoint, after its then-current
  Inspector/design/source reconciliation, the ledger snapshot was
  **6 VERIFIED / 51 BOUND / 6 TYPED_UNAVAILABLE / 36 UNBOUND**. Evidence:
  `docs/evidence/dde-069/SCREEN_AUDIT_ENGINE.md`.
- **M8 Source Intelligence — PARTIAL, FEDERATED CHECKPOINT** — migration `0034`
  and `engine/studio/source/` provide the common DesignSourceAdapter boundary,
  persisted source/search/artifact/admission/provenance/template/candidate-score/target-
  blend records, Design System Compiler admission, sandbox validation, provenance
  carry-forward, evidence-backed scoring, template recommendation and source promotion
  gate. Default source priority is project-native → DDE Library → shadcn/ui → ReUI →
  Magic UI → Aceternity UI → optional 21st → donors. The public web providers share
  `PublicShadcnRegistryAdapter`, a read-only HTTPS/JSON/size-bounded index/search/
  inspect/fetch boundary with exact-byte hashing and no install/publish/project-write
  capability. Live 2026-09-06 evidence fetched/hash-pinned one item from each of the
  four public providers; shadcn/ReUI/Magic UI carry observed MIT reuse evidence while
  Aceternity remains licence `UNKNOWN` and therefore cannot be silently treated as
  reusable. The persisted M8 lifecycle separately passes against isolated PostgreSQL
  16.15, including sandbox/admission/provenance/score/promotion/audit flow. 21st remains
  an optional fail-closed adapter when exact certified credentials/transport exist; it
  is no longer a DDE-069 dependency. Full live-provider → PostgreSQL → sandbox/admission
  end-to-end evidence remains open. Evidence:
  `docs/evidence/dde-069/M8_SOURCE_INTELLIGENCE_CHECKPOINT.md`,
  `docs/evidence/dde-069/POSTGRES_REDIS_CLOSURE.md`, and
  `docs/evidence/dde-069/public-registry-live-run.json`.
- **Candidate Dock + Inspector functional closure** — accepted-current truth,
  exact code-backed candidate miniatures, real mutation counts, evidence-backed score
  explanations, two-LIVE compare, governed Promote and non-overlapping Universal DDE
  Chat are implemented. Inspector now renders Layout / Style / Behaviour / Responsive /
  Lock / Source-code tabs backed by semantic descriptors; layout/gap/padding are token-
  governed, breakpoint changes start exact viewport previews, locks are real and
  reversible, and source/provenance/accessibility stay evidence-backed. The current
  token authority still maps `space8` to 40px, so the implementation does not fabricate
  the golden mockup's 64px padding value. `CA-06` is BOUND only at packaged production
  E2E; `CA-07` has its direction-selection/Try-live UI and remains BOUND on that same packaged-host proof. Full workbench Playwright in the latest closure packet is **76/76**; extension
  tests remain green. Evidence: `docs/evidence/dde-069/CANDIDATE_DOCK_CLOSURE.md` and
  `docs/evidence/dde-069/INSPECTOR_GOLDEN_CLOSURE.md`.
- **Review, simulation, editor-assist and top-bar closure packet** — commits `09c4249`, `23f773f` and `e4347df` add anchored design-comment create/resolve with anchor-loss refusal, durable preview scenarios kept separate from runtime attestation, provider-honest Auto Layout/AI Suggest policy, derived attention acknowledgement, project switching, retained-event activity, help routing and principal identity. Migration `0036` is reversible and handles current-schema snapshots idempotently while failing closed on partial pre-existing state. The uninterrupted repository gate passed 1,483 Python tests with 6 skipped, generated-contract/design checks, 77 extension tests, all TypeScript checks and the Vite build; the expanded workbench Playwright suite passes 76/76.
- **DDE-068 carry-over CLOSED** — see the dedicated subsection below.

**Still incomplete / evidence-gated:** `CA-07` packaged production-host Try-live E2E;
strengthened real-provider materialization rerun after the strict manifest change; general React/Vite/Expo PreviewRuntimeAdapters beyond admitted
prototype HTML; row-specific packaged VS Code-host → Gateway → PostgreSQL browser E2E for controls whose own read/action/state is not yet exercised in the baseline run; remaining BOUND and typed-unavailable golden controls; provider design-system
sync; structural implementation-worker handoff for non-deterministic design proposals;
AD-039 exact binary repository pinning; live R2 certification; cross-DDE migration (M12),
mobile adapters (M13) and hardening (M14).

#### `Claude /design` — closed with a certified transport (2026-09-06)

`CT-06` is now `VERIFIED` across all eight evidence layers. The certified
transport is `engine/studio/design/claude_transport.py`: the authenticated
Claude Code executable used **only** as a bounded, non-interactive host
process for the official `claude-design` MCP server. Print mode, structured
`stream-json`, `--permission-mode dontAsk` with `--permission-prompts none`,
`--tools ToolSearch` (every file/command/network tool removed),
`--strict-mcp-config` admitting exactly one server, ephemeral `--settings`
allowing only `mcp__claude-design__*`, `--setting-sources ""`, and
`--no-session-persistence`. Those flags are treated as a claim: the returned
stream is checked for MCP connection, an allowlisted offered tool surface, no
non-allowlisted execution, empty `permission_denials`, and a successful
terminal result. The return contract is an explicit machine-readable manifest
(`engine/studio/design/manifest.py`, `dde.design.manifest/1`) delivered through
`--json-schema`, never arbitrary final prose; a direction may only name PXG
keys the `DesignEditContext` exported, and every claimed deliverable must be
tied to an observed successful MCP write.

Still deliberately **not** routed through `capability.claude_code_invoke`:
that capability grants arbitrary development execution against a human's own
rate-limited seat and keeps its mandatory per-invocation approval for that
reason (EDR-0001 Path A, EDR-0017). It remains forbidden as a `/design`
fallback, and this transport does not use it.

Activation is explicit configuration (`DDE_CLAUDE_DESIGN_ENABLED`, see
`.env.example`), never a host path and never inferred from an installed
binary. A deployment that has not enabled it registers no transport, so
`ClaudeDesignProvider` still reports `NOT_CERTIFIED` and the gateway still
refuses with no fallback — ordinary unit and CI runs never reach a live
provider. Provider state is typed: `NOT_CERTIFIED` / `AUTH_REQUIRED` /
`UNAVAILABLE` / `CERTIFIED`, and the toolbar control enables only on
`CERTIFIED`, sending `/design` into the **existing** Universal DDE Chat
conversation rather than opening a second one or mutating state directly.

**Live certification state.** The committed live run against real PostgreSQL 16.15,
Redis 7.0.15 and the real `claude-design` MCP proved provider discovery as `CERTIFIED`,
`/design` routing through Universal DDE Chat, persisted DesignSession/DesignArtifact
provenance, candidate isolation, content-hash browser handshake and DDE-068 promotion
refusal. That run is valid evidence for `CT-06` transport/control, but it predates the
new strict deterministic materialization contract and therefore must not be cited as
proof of golden `CA-07`.

After materialization hardening, `tests/live/test_claude_design_live_e2e.py` was
strengthened to read persisted direction artifacts through the product API and prove the
selected proposal. The 2026-09-06 rerun reached a `CERTIFIED` provider but the provider
invocation ended without a successful result (`PROVIDER_ERROR`), so no new materialized
live proof was produced. The failed observation is preserved as
`docs/evidence/dde-069/claude-design-live-rerun-failed-2026-09-06.json`; the earlier
passing transport evidence remains
`docs/evidence/dde-069/claude-design-live-run.json`. Rerun rather than weakening the
manifest/token/materialization contract.

**Not closed by the transport:** `frontend.design.sync_system` is still unimplemented;
structural design proposals still need the implementation-worker handoff; and `CA-07`
Direction-card selection/Try-live UI and structural visual layers are now verified, while
WIRED/E2E remain BOUND pending one packaged VS Code-host → real Gateway → PostgreSQL
browser run. The ordinary candidate strip remains independently functional.
AD-039 pixel-reference conformance and live R2 certification remain independent open
gates. 21st is no longer an independent blocker because public registry federation
provides free external source coverage and 21st is optional.

#### Golden visual artifact — BLOCKED_EXTERNAL

AD-035 names a user-approved 1672x941 Frontend Studio mockup as the canonical
visual baseline. The image has never existed in this repository (verified across refs),
but the exact artifact was externally recovered on 2026-09-06: 1672×941,
1,492,542 bytes, SHA-256
`8e24bb34e5fb5723bbc9e44c2716f05300f5f4e95f463770349f05fdba8a6377`.
Recovery identifies the authority; it does not pin it into Project Truth.

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

**To unblock:** commit the exact recovered bytes at
`docs/truth/golden/frontend-studio-shell.png`, verify the dimensions/size/SHA-256 above,
and record that hash in `docs/truth/golden/GOLDEN_VISUAL_MANIFEST.json`. Do not
reconstruct or regenerate a substitute.

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

**Required before completion** (from `FRONTEND_STUDIO_REV3.md` Part XVIII "Definition of Done," summarized): host-neutral React/TS/Vite workbench behind `DdeHostBridge`; production PXG/Frontend Contract/Coverage Engine; one unified mutation/lock/candidate-isolation path across chat, direct edit, templates and agents; governed source adapters (internal, federated public registries, optional 21st, donor, mobile) through the Design System Compiler; `Claude /design` as a first-class control sharing one DesignSession with Frontend Chat; DDE-068 visual verification gating promotion (not optional — see FRONTEND_STUDIO_REV3.md's own "DDE-068 DEPENDENCY" clause); every visible golden-mockup control bound to a real capability or an explicit honest unavailable state; cross-DDE shell migration for all other DDE windows.

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

**Mission:** DDE-069 — close remaining golden/control and live-design evidence without
rebuilding landed systems.

1. Keep the strengthened Claude live test and rerun it until a real current provider
   result satisfies `dde.design.manifest/1`; do not loosen token/materialization rules to
   make a provider response pass.
2. Implement the golden DesignArtifact direction cards/selection surface and bind it to
   `frontend.design.try_live`; prove selected artifact → atomic candidate mutation → exact
   code-backed LIVE preview → fresh DDE-068 verification. This is `CA-07`.
3. Finish remaining 99-control BOUND/UNBOUND rows from the binding ledger, prioritizing
   production host E2E where backend and TestHost evidence already exist separately.
4. Pin the exact recovered AD-039 binary when the bytes are available to the repository;
   until then continue structural conformance only.
5. Certify live R2 only after the private credential tuple is complete and correctly
   classified; one unverified opaque value is not permission to enable strict R2.
6. Continue M12/M13/M14 only after the above DDE-069 closure gates are reconciled.

Do not rebuild Screen Audit, Candidate Dock, Inspector, public registry federation,
Universal DDE Chat, PostgreSQL/Redis integration or the certified Claude Design transport.

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
