# Gap-closure record — infrastructure gaps verified and closed (2026-08)

**Status:** work record, not an EDR. No Project Truth rows were created or
modified. Where a gap touches chartered blueprint scope, the owning mission
or EDR is named below; this file only records what was verified, what was
closed in-repo, and what remains open with its owner.

This document exists so the main DDE setup agent (and any future mission
chain) sees, in one place, which infrastructure gaps were independently
audited, which were closed by whom, and which remain deliberately open —
so nothing is re-implemented twice or silently dropped.

## 1. Audit result: what the main setup agent had already closed

The independent audit confirmed the main agent closed several reported gaps
before this pass; these are **not** re-done here:

| Gap | Evidence it was already closed |
|---|---|
| Real worker adapter | `adapters/cursor/adapter.py`, `adapters/claude/adapter.py` (fail-closed T2 policy shells), `engine/workers/scripted_adapter.py` (real T1 adapter, lease-enforced) |
| Certification runner | `engine/workers/smoke.py` `run_smoke()` — all 12 Chapter 8.5 fixtures enforced |
| EDR lifecycle tracking | `engine/truth/service.py` `propose_edr`/`accept_edr`/`update_edr_status` + idempotent `scripts/accept_owner_edrs.py` |

## 2. Gaps still open before this pass, now CLOSED in this pass

### 2.1 Repo hygiene (`bin/`, `obj/`, `node_modules/`)
`.gitignore` had no .NET build-artifact or node_modules patterns while
`packaging/windows/DdeSetupWizard/bin/**` held hundreds of DLLs as untracked.
Added `[Bb]in/`, `[Oo]bj/`, `publish/`, `node_modules/`, `*.vsix`.

### 2.2 Windows dev loop: `just test-unit` + Windows CI job
- `justfile`: new `test-unit` recipe running `pytest tests/unit -m "not integration"`,
  plus a `set windows-shell` line so every single-invocation recipe runs on
  Windows hosts that have no `sh`.
- `pyproject.toml`: registered the `integration` marker.
- `tests/unit/conftest.py`: auto-marks any test whose module is `*_postgres.py`,
  imports `tests.support.db`, or imports `redis` — so the pure suite stays
  accurate without per-file decorators and picks up new service-backed suites
  automatically.
- `.github/workflows/ci.yml`: new `windows` job (lint, typecheck,
  `just test-unit`). The ubuntu `ci` job remains authoritative for
  services/migrations/integration.

Verified locally on Windows: `179 passed, 239 deselected` in ~21s with no
PostgreSQL/Redis running.

### 2.3 CLI `--json`
All four subcommands (`mission create|status|trace`, `task list`) now accept
`--json` and emit machine-readable JSON built from the same structures the
text renderer consumes (contracts via `model_dump(mode="json")`; view
dataclasses via a shared recursive serializer). Default text output, exit
codes and error mapping are unchanged. `mission trace --json` prints before
the completeness check so callers can parse a trace and still observe
`MISSION_TRACE_INCOMPLETE`'s exit code.

New pure unit tests: `tests/unit/test_cli_json.py`. The existing
subprocess-based postgres suites continue to prove end-to-end behaviour.

This unblocks the dde-studio CLI-JSON bridge seam (planning doc §3.1a).

### 2.4 dde-studio live Gateway client
New `shared/gatewayClient.ts`: typed client over the **real, existing**
Gateway `/v1` surface only — session open/resume/close, command acceptance
(202), `GET /missions/{id}`, `GET /mission-control/{id}` — mirroring the
generated contracts and mapping errors onto the Chapter 15.5 error family.
No endpoint shapes are invented client-side.

New `shared/studioGateway.ts`: session lifecycle service used by
`extension.ts` (opens a `/v1` session when `dde.studio.principalId` is
configured; degrades to explicit `disabled`/`unreachable` states otherwise;
heals expired sessions).

New settings: `dde.studio.principalId`, `dde.studio.cliPath`.
`src/connection/cliTransport.ts` replaced the throwing stub with a real
`ProcessCliJsonTransport` that spawns `dde … --json` and parses stdout
(fail-loud on missing Core install). Fleet-room LIST views intentionally
remain empty — no list endpoint exists yet (DDE-027); honesty tests still
enforce no fabricated rows.

## 3. Gaps verified still open — NOT closed here, owners named

These require either Project Truth decisions or chartered missions; per
AGENTS.md they are recorded, not improvised:

1. **Cost telemetry hole (EDR-0005, open).** `WorkerRun.usage_record_id`
   still references a `UsageRecord` concept with no producing writer; every
   persisted outcome row discloses the gap via `disclosed_gaps`
   (`engine/telemetry/model.py`). Owner: a chartered mission implementing
   Chapter 6.5 actual-cost capture behind the broker (needs a real T2 run
   path first). Do not fabricate costs to close it.
2. **Live hosted-model worker execution.** Cursor/Claude adapters are
   deliberate fail-closed shells pending brokered credentials (Chapter 14.3).
   This is disclosed scope, not debt: closing it requires the credential
   broker mission, then certification of the live adapters.
3. **Gateway list endpoints (DDE-027, S3+).** `/v1` has reads by id and
   command acceptance but no mission/run/event listing. dde-studio fleet
   views stay empty until this lands. Owner: DDE-027's charter.
4. **`contradiction_rate` promotion gate (EDR-0003, partial).** Chapter 5.6
   conflict detection now exists (`engine/context/conflict.py`) and partially
   unblocks gate 3, but replay-through-eval wiring is explicitly deferred;
   see `docs/planning/mission-numbering-note.md` for the full interaction.
5. **Semantic retriever default gating (EDR-0002)** and remaining accepted
   EDR constraints — unchanged by this pass.

## 4. Integration guarantees (why nothing breaks)

- CLI changes are additive: new flag, default behaviour byte-identical,
  dispatch table untouched; existing tests pass unmodified.
- Routing/governance code from the earlier adoption pass is untouched.
- Studio changes are additive modules plus one new import and one guarded
  read block in `extension.ts`; all 44 existing client tests pass, including
  the honesty assertions that forbid fabricated data.
- The auto-marking conftest only *deselects* tests that provably need live
  services; pure tests can never be accidentally skipped.
- CI keeps the ubuntu job as authoritative; Windows is additive coverage.

## 5. Closed in this pass — frontend/UX design-gate infrastructure (2026-08-22)

Appended after the v1.1 frontend/UX playbook was operationalized. Only items
with landed commit evidence are recorded here; in-flight work (EDR-0008
implementation of Playwright/axe visual gates) is **not** listed below — it
is admitted but not landed, and will be recorded when its missions land.

### 5.1 Design gates wired into CI (`5f31142`)
- Token SSOT pipeline landed first (`58015fb`): `schemas/design/tokens.json`
  pins every leaf; codegen emits typed `tokens.ts` + CSS root; the generated
  artifact is covered by the existing generated-drift gate.
- Static design lints DD201–DD206 (`d03d415`) run as their own justfile
  recipe and CI step in committed baseline mode (shrink-only budget; legacy
  off-scale values frozen in a committed baseline rather than waived).
- dde-studio client tests became PR-blocking in `.github/workflows/
  dde-studio.yml`, closing the R5 hole where the workflow stopped at
  typecheck.
- Owner: none — wired at its production enforcement point; regressions fail
  the same PR that introduces them.

### 5.2 Prototype-manifest sweep pre-oracle (`b5a0ebb`, contract via `29cc55a`)
- `engine/verification/prototypes.py` validates a workspace's
  `prototypes/flows.json` structurally (version, flow ids, entry points,
  every transition target and declared screen exists on disk) before oracle
  evaluation; violations demote a clean PASS to PARTIAL with
  `VERIFICATION_FAILURE` classification on the existing recovery rows.
- Manifest shape is contracted by `schemas/design/prototype_flow.schema.json`
  under the normal SSOT/drift discipline.
- Byte-stable `index.html` regeneration remains deferred until a gallery
  generator ships (currently a review-skill concern); disclosed above in the
  playbook's §5.3 table.

### 5.3 Live Prototype Gallery (`a80f5a6`)
- `interfaces/dde-studio/src/webviews/previewGalleryProvider.ts`: sandboxed
  srcdoc previews over the workspace `prototypes/` directory, flows table,
  file-watch streaming for mid-mission viewing, reduced-motion toggle.
- The Preview module moved from stub to exists-with-honest-liveToday; the
  honesty tests still forbid fabricated gallery rows.

## 6. Open items with explicit closure triggers (2026-08-23)

Recorded so the next mission chain sees not just WHAT is open but exactly
WHEN each item must be picked up. Per AGENTS.md these stay open until their
trigger fires; do not improvise them early, and do not silently drop them.

### 6.1 Usage-meter ingestion — trigger: first usage-forwarding harness adapter

The engine half is LANDED (`035d5bb`): `engine/workers/usage.py` derives
remaining budget from `execution_plans.token_budget` minus summed
`WorkerRunUsageReported` event payloads; `WorkerManagerService.
record_run_usage` is public, ledger-guarded and tested. What does NOT exist
is any producer: `ScriptedWorkerAdapter.collect_usage` /
`ClaudeCodeWorkerAdapter.collect_usage` honestly return zero (EDR-0001
Finding 3) and no live adapter forwards real provider usage today.

**Trigger:** the FIRST mission that certifies a worker/harness adapter
capable of reporting real provider token usage MUST call
`record_run_usage` from its ingestion path as an acceptance criterion.
That mission closes this item and EDR-0005's Finding-3 hole together.
Until then, building a producer would fabricate data — forbidden.

### 6.2 Independent chapter-gate review before DDE-(N+1) — trigger: standing

Per `.cursor/rules/mission-chapter-gate.mdc`, CI green ≠ chapter done. The
2026-08-22/23 landing batch (commits `f97b9c7`…`baad25a` plus its follow-up
missions) touched Chapters 7 (T2), 9 (kill flag/budgets), 11 (guardrails),
12 (recovery/confidence), 13 (approvals), 14 (containment admission), 17
(design gates). Before any new chartered DDE-N mission starts, an
independent chapter-gate review must confirm every in-scope MUST/shall/
recovery rule names a production mutation call site — or is deferred with
its EDR named.

**Trigger:** standing requirement, evaluated at every "start DDE-(N+1)"
decision point. With standing auto-resume in force, a PASS or
PASS-WITH-EDR verdict permits the chain to continue without re-asking; a
FAIL freezes progression until corrected.

### 6.3 Network egress + container containment (EDR-0011) — trigger: first non-DDE-native execution substrate

DEFERRED by human decision (2026-08-23), with a hard precondition: before
ANY mission lets a third-party/non-DDE-native harness execute real commands
on this deployment (live Claude Code / Cursor / container backends), EDR-
0011's first slice — broker-level egress admission — must land. The local
process backend discloses its residual gaps honestly (`AMBIENT_ENVIRONMENT_GAP`,
grandchild reach); those disclosures must never be silently widened.

### 6.4 DDE-039 gate residuals — trigger: named per item (2026-08-24)

The independent chapter-gate review of DDE-039 returned PASS (all fourteen
verification items OK). Three MINOR residuals, recorded with owners:

- **Repair-task workflow not yet consumed** — `repair_task_ref` is stored
  on every invariant evaluation (`engine/invariants/service.py`) but no
  downstream surface creates a repair task from a FAILED `financial_state`
  row. **Trigger:** the mission that charters Chapter 10.5's `invariant`
  conflict class / recovery surface MUST consume it as an acceptance
  criterion. Chapter 11.5's own rule (never auto-repaired, human
  visibility) is already wired at the row level.
- **Downgrade reversibility test — CLOSED in this pass**: the
  migration-verification recovery suite gained
  `test_downgrade_from_head_lands_on_baseline_reversibly`
  (`verify_downgrade_reversible`, forward to head → downgrade to baseline
  → database revision asserted).
- **`ERRORED` evaluation status unreachable** — schema admits it,
  `judge_rows` never produces it; reserved until execution errors become
  recordable outcomes. **Trigger:** any mission that makes datastore
  failures a recorded evaluation outcome must either wire or retire the
  enum value.

### 6.5 UI-distinctiveness adoption plan — trigger: staged per item (2026-08-24)

From the six-stream anti-generic-output research (AI-slop tells, builder
techniques, template sources, motion/animation state of the art,
mechanical quality gates). Full report: research agent transcript,
2026-08-24. The playbook (docs/planning/dde-frontend-ux-playbook.md)
carries the design-law detail; this section records WHEN each item lands.

**Adopt-now items — each named to its owning mission (2026-08-24
ownership sweep, per product-studio-charter.md v2: DDE-065 compiler,
DDE-067 studio surface, DDE-068 visual verification & critique loop):**

| Item | Lands in | Surface |
|---|---|---|
| Art-direction record schema (type pairing, palette **roles**, layout idiom, motion identity, **VARIANCE/MOTION/DENSITY dials**, Design Read, DESIGN.md section grammar — see `design-tooling-integration.md` §4.1/§4.3) | **DDE-065** — hard compiler input; compilation fails closed (typed refusal) until it resolves | `schemas/design/` extension + generator |
| Font-pairing corpus (curated distinctive pairs w/ licence metadata; bans Inter-as-display) | **DDE-065** — lands with the art-direction record it populates | `schemas/design/` data file, no dependency |
| Combination lints (DD207+: flag Inter-only + indigo-gradient + centered-hero-3-card fingerprint) | **DDE-068** — blocking merge gate | `tests/unit/test_studio_design_lints.py` scanner |
| Silhouette test (layout-shape fingerprint distinctiveness vs generic corpus) | **DDE-068** — unblocked from DDE-043/044: the EDR-0008 Phase B Playwright harness already renders screens in dde-studio.yml's visual job | Playwright suite admitted by EDR-0008 (`interfaces/dde-studio/visual/**`) |
| Copy-specificity gate (reject generic AI-tell copy patterns) | **DDE-067** — first Studio surface it touches extends the test | Studio client suite (`clientHonesty.test.ts`) |
| Icon-family governance (one stroke set per product, no emoji icons) | already partially enforced by DD-lints; completion owned by **DDE-068** | DD-lints |
| Motion-identity presets in tokens (arrival/state/progress + spring spec, per-product selection) | **DDE-065** — rides the art-direction record | tokens schema motion block |
| Per-interaction motion specs in prototype manifests (trigger/easing/duration/stagger/reduced-motion degradation) | **DDE-068** — required fields asserted as blocking gates; DDE-067 consumes | `schemas/design/prototype_flow.schema.json` + validator |
| Reduced-motion blocking assertions (end-states preserved, movement removed) | **DDE-068** — Phase B harness landed; upgrade existing reduced-motion goldens to degradation-semantics assertions | dde-studio.yml visual job |

**Needs-EDR items — filed when their enabling mission starts:**

| Capability | Enabler / stage | EDR timing |
|---|---|---|
| Template-ingestion pipeline (shadcn/jsrepo registry JSON as donor input; env-var-keyed commercial tiers supported natively) | S5 Donor Lab (DDE-046) | EDR with DDE-046 charter |
| Commercial-template licensing path (Tailwind Plus/Cruip = CONDITIONAL_REUSE end-products only; GSAP CONDITIONAL_REUSE pending legal read of its builder-competing clause) | S5, owner decision first | EDR before any purchase/use |
| VLM design-critic loop (screenshot → rubric critique → bounded revise ≤3 → residuals to human; evidence: +17.8% WebDev Arena improvement over 3 cycles) | **DDE-068** (product-studio-charter v2); Phase-B screenshots already land via dde-studio.yml's visual job | **EDR-0016**, filed at product-studio-charter v2 sign-off — implementation may not start before acceptance |
| Reference-board grounding (godly/land-book-class corpus into ContextPackage art-direction pass; entries SOURCE_REFERENCE_ONLY, injection-screened per §14.5) | S5 DDE-046/044 | folds into those charters' EDRs |
| Embedding-based anti-centroid gate (DINOv2-class similarity scoring vs generic-layout centroids; prior art: ReftrixMCP originality scoring) | after browser capability exists; explicitly OUT of DDE-068 scope | separate heavier EDR (ML runtime + vector store) |
| Motion polish check class + animation-library budget rule for generated products (CSS scroll-driven + View Transitions default; Motion within declared KB budget; GSAP only post-legal) | after EDR-0008 Phase B wired; DDE-068 delivers the reduced-motion/polish assertion base | verification-runner extension EDR |
| Animation-bundle performance budgets / CWV floors for generated outputs (LCP/CLS/INP; compositor-property-only lint) | S7 load/capacity (DDE-063); lint earlier at DDE-043 | Chapter 16.5 budget amendment |

Standing rule: no generated UI ships from a DDE mission without passing
the combination lints + silhouette test once both exist; until then the
existing DD201-DD206 lints and honesty tests are the floor. The
Definition-of-Polished battery in product-studio-charter.md §4 names the
full gate list with per-gate status (live today vs lands-with-DDE-065/
068); a screen may merge only when all eight gates are green. Tooling
disposition and concept harvest that feed these rows:
`docs/planning/design-tooling-integration.md` (§6.10).

### 6.6 Owner decision sweep — closed 2026-08-24

Owner standing directive "close all queued decisions per coordinator
recommendations" (2026-08-24). Dispositions:

- **EDR-0012/0013/0014 ACCEPTED** into Project Truth via
  `scripts/accept_owner_edrs.py` (accepted processing now EDR-0001..0014).
- **Frontend Studio charter v3 SIGNED OFF** (DDE-065..068); DDE-065 +
  DDE-067 GUI shell authorized under standing auto-resume.
- **EDR-0015** (donor-search egress admission) and **EDR-0016** (VLM
  design-critic dependency & budget) filed PROPOSED same day; DDE-066/DDE-068
  implementations stay gated on their acceptance.
- **EDR-0011 remains proposed** — its containment precondition stays
  deferred (§6.3); EDR-0015 amends it for the donor-search egress surface.
- Silhouette generic-corpus sourcing folded into EDR-0016 as an open item
  (licence-clean provenance; galleries are SOURCE_REFERENCE_ONLY, no APIs);
  decided at DDE-068 charter time.
- Density-floor calibration deferred to DDE-068 implementation (charter §4
  gate 4 unchanged); GSAP unchanged — CONDITIONAL_REUSE pending legal read.

### 6.7 Orca-router research integration — trigger: DDE-057/058/059 charters (2026-08-24)

Completed web research on "Orca router" (disambiguated: OrcaRouter, Continuum AI's
LLM router — NOT the OSDI'22 GPU serving system) was integrated as design priors for
the routing-learning missions. Full note:
`docs/planning/orca-routing-research-integration.md` (sources, mechanics,
source-quality caveats: vendor-authored non-peer-reviewed paper with self-reported
results; unresolved whether the LinUCB learner ships in the MIT edition vs hosted
only; repo ≈4 months old / ≈3 humans / zero releases → patterns-not-packages under
Ch.9.6).

Adopted as **design inputs AND acceptance criteria** (patterns only, no dependency):

1. Full-information offline warmup before any online update (cold-start bandits
   measurably lose to constant baselines — their own data).
2. Frozen-exploitation-first rollout; continued-update behind an explicit switch.
3. Margin-based tie-breaker benchmarked against pick-flip rate in shadow eval.
4. Standing assertion: the learned policy must beat the best *constant* policy on
   the identical evaluation window, not merely the incumbent policy table.
5. Conceptual: SLO-derived per-class capacity budgets for gate 5 (Sarathi-Serve);
   observe→shadow→enforce corroboration (guardrail-policy scope only).

**Trigger:** the missions that charter Ch.6.8/6.9 (DDE-057 ExperienceRecord
eligibility filtering, DDE-058 routing learner + shadow evaluation/calibration/
canary/rollback, DDE-059 adaptive context policy) MUST consume that note as design
inputs and acceptance criteria at charter time. Until then nothing here authorizes
any learning code; deterministic Stage-1 posture is unchanged.

### 6.8 OpenSandbox/Graft research integration — trigger: EDR-0011 memo + structural-retriever/EDR-0002/059 missions (2026-08-24)

Completed web research on two agent-infrastructure products was integrated as design
priors: OpenSandbox (Alibaba's sandbox platform — egress sidecar, credential vault,
pluggable gVisor/Kata/Firecracker isolation tiers) and Graft (NanoNets' context layer —
deterministic tree-sitter symbol graph, index-time cached LLM summaries, push-vs-pull
benchmark methodology). Full note:
`docs/planning/opensandbox-graft-research-integration.md` (repo cards, mechanics,
source-quality caveats: vendor-run unreplicated benchmarks for Graft; press-release-heavy
coverage and no independent audit for OpenSandbox).

Adopted as **design inputs AND acceptance criteria** (patterns only, no dependency):

1. OpenSandbox egress-sidecar design (FQDN allow/deny, DNS-pin + nftables IP
   enforcement, runtime `PATCH /policy`, NET_ADMIN stripping, secrets injected at the
   sidecar never in env) → donor design evaluated in the **EDR-0011 decision memo**
   before DDE specifies its own proxy/resolver.
2. Isolation-tier-as-config (runc/gVisor/Kata via RuntimeClass) → validates EDR-0011
   Option A's mechanism table as industry-standard; evaluated in the same memo (the
   tier choice interacts with egress enforcement — their own docs flag gVisor×nftables
   incompatibility).
3. Graft deterministic structural retrieval (receiver-type method binding,
   in-degree-coupled ranking, monorepo per-scope fusion, ~3ms fingerprint freshness) →
   candidate improvements to the Ch.5.2 structural retriever, evaluated on the Ch.5.13
   eval corpus by the next mission touching it or by the DDE-059 charter.
4. Graft index-time LLM summarization (cached by content hash) → mandatory A/B
   alternative: any mission proposing semantic-retrieval default-on (EDR-0002/0003
   path) must first beat this approach on the eval corpus, not merely the lexical+
   structural baseline.
5. Push-vs-pull context methodology (push wins speed, pull won correctness; SWE-bench
   two-arm official-grader protocol) → benchmark methodology adopted for **DDE-059**:
   same agent, same tools, only the retriever/policy differs, graded against the
   certified baseline.

**Triggers:** (a) when EDR-0011 acceptance is decided, its decision memo MUST evaluate
patterns 1–2 against this reference implementation of the hard parts; (b) any mission
touching the structural retriever or chartering DDE-059 MUST evaluate patterns 3–5 on
the Ch.5.13 corpus at charter time. Until then nothing here authorizes engine changes;
T2 containment remains gated exactly as EDR-0011 leaves it (proposed), and semantic
retrieval remains off by default per EDR-0002.

### 6.9 Buzz / advisory-council research integration — trigger: governance/replan surfaces + any new worker adapter mission (2026-08-24)

Completed web research on Buzz (Block's Nostr-based human+agent workspace — Rust
monorepo, Apache-2.0, ~30.4k stars, prototype maturity) was integrated together with a
boardroom-pattern analysis (can agents deliberate and decide scope?). Full note:
`docs/planning/buzz-advisory-council-research-integration.md` (repo facts, pattern
mappings, boardroom-law verdict; source-quality caveat: launch-coverage-heavy, no
independent audit — patterns-not-packages under Ch.9.6).

Adopted as **design inputs AND acceptance criteria** (patterns only, no dependency;
owner narrowing 2026-08-24: adopt only high-value items that fit the already existing
DDE structure):

1. Watch-and-borrow stance toward Buzz: track its protocol-level human+agent
   collaboration patterns, adopt none of its runtime.
2. Buzz patterns that DDE already implements are **confirmations, not adoption work**:
   signed agent identities (Ch.14.2/14.4), hash-chain audit logs (Ch.3.7),
   mention-batching / attention budget + batch approval (Ch.13.1/13.4). The ACP-class
   harness abstraction is likewise a donor reference ONLY if a future worker-adapter
   mission ever needs a new seam — no such seam is planned.
3. **Boardroom rejected:** an agent panel that DECIDES scope violates DDE law —
   Ch.2.2 rank discipline (rank-10 output cannot self-promote to rank-7 authority),
   Ch.13 approval ownership (scope decisions are human governance acts), and the
   blueprint's refusal of agent-to-agent conversation for core state transitions.
4. **Advisory council adopted-in-principle, bounded — the one forward adoption:**
   harnesses emit structured rank-9 position papers with citations; deterministic
   aggregation as a pure function (no model judge, no durable council state); ≤2 rounds
   budget-capped under Ch.16.4; output feeds ONLY the existing human approve/decide
   surface; starts as a shadow-mode experiment on replan decisions
   (`RecoveryService.replan` triggers) before any expansion.
5. Cautionary tale recorded: Buzz-class products show what happens when agent autonomy
   ships ahead of wired approval paths; DDE's bounded standing authority +
   acknowledge-gated stops exist to prevent exactly that.

**Triggers:** (a) the missions that charter the governance/replan decision surfaces
(any mission touching `RecoveryService.replan`'s human-decision UX or new
approval-surface commands) MUST evaluate the advisory-council design at charter time,
shadow-mode first. Until then nothing here authorizes engine changes: no council code
exists, no agent-to-agent channel is admitted for core state, and rank-10 material
stays non-authoritative per Ch.2.2.

### 6.10 Design-tooling integration — trigger: DDE-065/067/068 charters (2026-08-26)

Consolidated external brief + independent evaluations of Impeccable, Vercel
agent-skills / Web Interface Guidelines, Taste Skill, and Awesome DESIGN.md into
`docs/planning/design-tooling-integration.md`. Disposition: **patterns-and-encodings,
not package installs**. Track A skills are not evidence; DD201–DD206 and axe stay
first-party/LIVE; harvest Taste dials + Stitch/DESIGN.md grammar into DDE-065
art-direction, Taste production tells + WIG non-axe rules into DDE-068 lints,
conformance-by-construction remains DDE-067; silhouette/density/VLM remain
build-from-scratch under DDE-068 / EDR-0016.

**Trigger:** DDE-065, DDE-067, and DDE-068 charters (and any Phase-0 donor/admission
work for an optional Impeccable DD207+ supplement) MUST consume that note as design
inputs and acceptance-criteria seeds. Until then nothing here authorizes new
dependencies or skill installs as merge-blocking gates.

### 6.11 DDE-066 donor discovery — EDR-0015 accepted (2026-08-27)

EDR-0015 is **accepted** (Project Truth row + markdown pre-image
`docs/truth/edr/EDR-0015-donor-search-egress-admission.md`). DDE-066
implements control-plane search fan-out at
`engine.donor.discovery_service.DonorDiscoveryService.search`: in-repo
host+path allowlist, broker-issued short-lived credentials, query quota
on `execution_plans.token_budget.donor_search_max_queries`, Ch.12.4
journal (`prepare`/`mark_sent` before GET), classify-before-use grouping
with unmatched bucket, DDE-046 pins in the same inventory, taint persist
via DonorLab ingest. HTTP transport is `adapters/donor/http.py` (httpx
does not enter `engine/core` or `engine/donor`). Studio GUI and Gateway
command `frontend.donors.run_discovery` stay DDE-067. DDE-068 still waits
on EDR-0016.



