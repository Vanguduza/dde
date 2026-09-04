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
| DDE-068 Visual Verification & Critique Loop | `IMPLEMENTED_PARTIAL` | See §3's dedicated DDE-068 entry below: silhouette-distinctiveness gate landed with a real production call site; token-injection golden fix landed; VLM critique and the density floor that depends on it remain `BLOCKED_EXTERNAL` (no real multimodal-model provider credential exists in any environment this project has run in to date). |
| DDE-069 DDE Code / Frontend Studio V2 + Live Design Foundation | `PLANNED` | Adopted domain architecture: `docs/truth/FRONTEND_STUDIO_REV3.md` (AD-036). Supersedes the earlier "Mobile/Multi-target" framing that was never updated after `DEV_PLAN_REV3.md`'s Rev 3.3 edit (commit `b5753db`) redefined DDE-069; see AD-030. Mobile/multi-target is not deferred work of its own — it is a governed sub-capability (platform-specific design-source adapters + Expo/device runtime verification) inside this mission. Hard-blocked on DDE-068 evidence per FRONTEND_STUDIO_REV3.md's own "DDE-068 DEPENDENCY" clause; no implementation commit exists yet. |
| Fable 5 strategic orchestration profile | `BLOCKED_EXTERNAL` | Rev 3 role is defined, but no actual Fable 5 adapter/runtime integration was found in the observed repository state. Implement only when a supported interface is available and testable. |
| Hermes persistent research/coordination role | `IMPLEMENTED_PARTIAL` | Hermes is represented in routing registry and DDE Code worker/harness UI surfaces; the full Rev 3 persistent coordination/research/recovery role still requires explicit runtime/profile hardening and evidence. |
| Claude Code worker integration | `IMPLEMENTED_PARTIAL` | DDE Code/packaging references Claude Code worker setup; Rev 3 quota-aware specialization and independent-review routing still require explicit implementation/evaluation. |
| DeepSeek worker integration | `IMPLEMENTED_PARTIAL` | Harness/profile references exist; Rev 3 lower-cost delegation policy and measured routing specialization remain to be proven end-to-end. |
| Frontend Studio professional Rev 3 redesign | `PLANNED` | DDE-067 surface exists and design-tooling rules exist, but Rev 3 calls for a broader professional operator-shell redesign and DDE-068 evidence integration. |
| Routing intelligence / learned policy promotion | `IMPLEMENTED_PARTIAL` | Existing routing registry/telemetry/learning planning exists; open EDR/partial implementation records require careful production-call-site audit before claiming full adaptive routing. |
| Context optimization / repository memory | `IMPLEMENTED_PARTIAL` | Rev 3 bootstrap removes chat history as a required project-memory source; deeper task-packet/retrieval optimization remains planned. |
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

**State:** `IMPLEMENTED_PARTIAL`.

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
5. believable-density enforcement — `BLOCKED_EXTERNAL`. Per
   `docs/planning/product-studio-charter.md` line 373 and playbook §8.3,
   this is a *rubric-scored* dimension ("believable-density >= 4",
   "hierarchy, rhythm, and states" judged from rendered pixels), not a
   deterministic check — it is one scored dimension of the same VLM
   critique call as item 7, so it shares that blocker. A deterministic
   proxy (e.g. regex-detecting `"Item 1"`/lorem-style filler strings) was
   considered and rejected: it would silently substitute a materially
   weaker mechanism for the spec's rubric-scored gate and misrepresent
   what "believable-density enforcement" means per the accepted EDR/plan.
6. reduced-motion semantic assertions — `LANDED` (recovered this session,
   commit `582e06a`'s parent `b35fb41`). `screens.spec.ts`'s
   reduced-motion-semantics test reads real computed
   `animation-duration`/`animation-name` under
   `prefers-reduced-motion: reduce`, distinct from the pre-existing
   snapshot-only reduced-motion golden.
7. VLM screenshot critique as rank-9 evidence — `BLOCKED_EXTERNAL`.
   Verified (not assumed) before writing this: no `ANTHROPIC_API_KEY` or
   any multimodal-provider credential is present in this or any prior
   session environment for this project; `engine/routing/rules.py`'s
   Appendix A "vision and visual evidence" profile is a routing-eligibility
   *description*, not a wired adapter; no `engine/**` module imports an
   `anthropic`/`openai`/vision-provider SDK — the only sanctioned model
   egress recorded anywhere in the repo is
   `engine/capabilities/seed.py`'s `"external:anthropic (via local claude
   CLI only)"`, which is not a callable production API surface this
   codebase can invoke as a brokered capability. Per RESUME_PROMPT.md
   §15's stop condition ("a provider/interface ... is unavailable and no
   generic contract path can progress safely"), this is reported as a
   genuine external blocker rather than stubbed with a fabricated verdict.
8. bounded revision <= 3 cycles — `BLOCKED_EXTERNAL`, downstream of 7 (the
   revision loop has nothing to bound without a real critique call).
9. human escalation after bound — `BLOCKED_EXTERNAL`, downstream of 7/8.
10. real production promotion/merge gate consuming visual verdicts — `NOT
    STARTED` this tranche. `FAILED` `CheckResult`s from `visual_diff`/
    `silhouette` already flow into the generic verification-run
    pass/fail signal, but no code path was found or built that makes a
    DDE "merge"/task-completion decision actually refuse on that signal
    (`engine/governance/` has no `promotion`/`merge_gate` module; the
    `promotion_gate_run` contract that does exist belongs to a different
    subsystem, Ch.5.13's eval-corpus promotion, DDE-031 — not this gate).
    Next work packet's first item.

**Immediate next work packet:**

- Wire item 10: find or build the real task/mission completion path that
  consumes `VerificationRun` status and refuses to advance on a `FAILED`
  `visual_diff`/`silhouette` result, with a contract test exercising the
  refusal (not just the happy path), per the charter's own acceptance
  criterion for this mission.
- Items 5/7/8/9 stay `BLOCKED_EXTERNAL` until a real multimodal-model
  provider credential is admitted through the brokered capability path
  (Appendix A "vision" profile gets a real adapter under `adapters/**`,
  `RouterService.model_mode="fixed"` pins it, EDR-0016's cost ceiling is
  enforced). Do not stub a fake critique response to unblock these —
  report the blocker at the next session's start per RESUME_PROMPT.md §16.

### DDE-069 — DDE Code / Frontend Studio V2 + Live Design Foundation

**State:** `PLANNED`. Not started; no implementation commit found.

**Domain authority:** `docs/truth/FRONTEND_STUDIO_REV3.md` (adopted 2026-09-03, AD-036), reconciling and superseding `docs/planning/frontend-studio-gui-spec.md`'s never-formally-adopted mission definition. Golden visual authority (light-first) is recorded separately as AD-035.

**Naming-drift note (resolved 2026-09-03):** earlier snapshots of this file described DDE-069 as "Mobile/Multi-target Profiles, `DEFERRED`." That description was accurate to `ARCHITECTURE_DECISIONS.md`/`RESUME_PROMPT.md` at the time but went stale the moment `DEV_PLAN_REV3.md` §6 was rewritten same-day (commit `b5753db`, "docs: adopt Rev 3.3 orchestrator attestation truth") to define DDE-069 as the Frontend Studio V2/live-design mission — a rewrite this file, `ARCHITECTURE_DECISIONS.md`, and `RESUME_PROMPT.md` were never updated to match. AD-030 now records the resolution. Mobile is not dropped: `FRONTEND_STUDIO_REV3.md` folds it in as a governed sub-capability (§11.6 mobile source adapters, §26 Expo/device runtime verification, migration phase M13) rather than a separately numbered deferred mission.

**Required before completion** (from `FRONTEND_STUDIO_REV3.md` Part XVIII "Definition of Done," summarized): host-neutral React/TS/Vite workbench behind `DdeHostBridge`; production PXG/Frontend Contract/Coverage Engine; one unified mutation/lock/candidate-isolation path across chat, direct edit, templates and agents; governed source adapters (internal, 21st, donor, mobile) through the Design System Compiler; `Claude /design` as a first-class control sharing one DesignSession with Frontend Chat; DDE-068 visual verification gating promotion (not optional — see FRONTEND_STUDIO_REV3.md's own "DDE-068 DEPENDENCY" clause); every visible golden-mockup control bound to a real capability or an explicit honest unavailable state; cross-DDE shell migration for all other DDE windows.

Do not expand targets, and do not begin DDE-069 implementation proper, before the DDE-068 quality loop is stable enough to avoid multiplying an immature pipeline.

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

### RISK-02 — DDE-068 becomes a documentation-only quality layer

Visual/VLM concepts already exist in planning, but completion requires real verification executors and promotion call sites.

**Mitigation:** implement DDE-068 using the vertical slices in `DEV_PLAN_REV3.md` and gate each at production paths.

### RISK-03 — Premium-model quota transfer

If Fable is unavailable, there is a temptation to make Claude Code absorb orchestration plus implementation plus review.

**Mitigation:** deterministic planning/validation + Hermes research + lower-cost bounded workers + premium escalation only for high-value reasoning.

### RISK-04 — Hermes UI presence mistaken for complete Hermes orchestration

A harness card/room is not proof of the full runtime role.

**Mitigation:** keep state `IMPLEMENTED_PARTIAL` until routing, capabilities, recovery and telemetry prove the Rev 3 role.

### RISK-05 — Frontend quality overclaim

DDE-067 landed the surface; DDE-068 is still required for rendered quality evidence.

**Mitigation:** no `Definition of Polished` or quality badge without evidence-backed DDE-068 gates.

---

## 7. Immediate next work packet

Unless newer implementation evidence exists:

**Mission:** DDE-068 Visual Verification & Critique Loop.

Start by auditing these areas against the signed charter and Rev 3 plan:

- `engine/verification/**`;
- visual executor/oracle bindings;
- `interfaces/dde-studio/visual/**`;
- `scripts/design_lints.py`;
- `tests/unit/test_studio_design_lints.py`;
- Gateway/verification command path;
- Evidence persistence;
- approval/promotion call sites.

First vertical slice should prove a real visual verification request can render a ProductEnvironment screen and persist an evidence-backed result.

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