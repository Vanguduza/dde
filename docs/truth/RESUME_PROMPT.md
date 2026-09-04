# DDE Rev 3 — Canonical Resume Prompt

Use this prompt when starting a new engineering session, coding agent, Claude Code/Cursor run, Hermes session or equivalent worker. The repository is the memory source; do not require the historic ChatGPT thread.

---

## Prompt

You are resuming development of **DDE — Development & Engineering Engine** in the repository `Vanguduza/dde`.

Your job is to continue the project from its **actual current repository state** toward the canonical Rev 3 architecture. Do not reconstruct the project from assumptions, model memory or chat history.

### 1. Establish authority before touching code

Read, in this order:

1. `AGENTS.md`
2. `docs/truth/BLUEPRINT_REV3.md`
3. `docs/truth/ARCHITECTURE_DECISIONS.md`
4. `docs/truth/DEV_PLAN_REV3.md`
5. `docs/truth/IMPLEMENTATION_STATE.md`
6. `docs/truth/FRONTEND_STUDIO_REV3.md` — adopted domain architecture for DDE-069/Frontend Studio V2, required reading once DDE-068 is evidence-complete (AD-036)
7. the relevant accepted EDR markdown pre-images under `docs/truth/edr/**` — note some EDRs referenced elsewhere (e.g. EDR-0027, EDR-0028, EDR-0031, EDR-0033) have no markdown pre-image in this directory; if the file is absent, the accepted Project Truth database row is the record, not a missing file
8. the relevant mission charter / chapter-gate / specialist planning documents under `docs/planning/**`

Accepted Project Truth database records outrank every markdown file. `BLUEPRINT_REV3.md` is the canonical human-readable architecture. `docs/blueprint/historical/REV_2_0.md` is historical/reference depth only unless Rev 3 explicitly points to it.

Do not silently choose a convenient document when sources conflict. Identify the conflict and use the EDR/change-control path if the authoritative contract must change.

### 2. Verify the repository instead of trusting the state summary

Before implementing:

- inspect current branch and HEAD;
- inspect recent commits affecting the target mission;
- inspect current code paths, schemas and tests;
- verify whether `IMPLEMENTATION_STATE.md` is still accurate;
- run focused baseline tests for the target area where feasible;
- consult `docs/planning/gap-closure-record.md` before re-implementing infrastructure that may already have been closed.

If the repo has advanced beyond `IMPLEMENTATION_STATE.md`, update the state from evidence first and continue from the first genuinely incomplete dependency.

### 3. Default next mission

**DDE-068 closed 2026-09-04 (`COMPLETE_EVIDENCED`). DDE-069 — DDE Code /
Frontend Studio V2 + Live Design Foundation — is `IN_PROGRESS`.** Read
`IMPLEMENTATION_STATE.md`'s DDE-069 section for what has landed, then
`docs/truth/FRONTEND_STUDIO_REV3.md` as domain authority. Verify both from
the repository rather than trusting this line.

**Find the next packet in the ledger, not in this file.**
`docs/truth/FRONTEND_STUDIO_BINDING_MATRIX.md` carries one row per golden
control with its current state. Work proceeds by turning `UNBOUND` rows
into real bindings, not by completing M-numbers in order (AD-038). A row
may not claim `BOUND` without naming production files that exist, nor
`VERIFIED` without naming tests that exist —
`tests/unit/test_frontend_binding_matrix.py` enforces that, and
`scripts/render_binding_matrix.py --check` runs in `just contract-test`.

Highest-value unbound work at this snapshot, dependency-first:

1. **M9 preview runtime** — the largest remaining gap and what unblocks
   the most ledger rows at once: candidate rendering on the canvas, stable
   selection instrumentation, the inspector's descriptor-driven controls,
   candidate thumbnails, Try-live preview and the LIVE badge. The mutation
   path they would drive is already real and governed.
2. **M8** — design source adapters (internal library, donor, 21st),
   template recommendation, the Design System Compiler, provenance and
   `CandidateScorecard`. Unblocks the Sources and Templates explorer
   groups, Source Blend and candidate scores.
3. **M12** — migrate the remaining DDE windows onto the shared shell.

**Two owner-action blockers.**

*The golden image.* The AD-035 1672x941 mockup is not in the repository
and never has been (AD-039). Structural conformance is verified;
pixel-reference conformance fails closed until the image is committed at
`docs/truth/golden/frontend-studio-shell.png` with its sha256 recorded in
`docs/truth/golden/GOLDEN_VISUAL_MANIFEST.json`. Do not fabricate the
artifact, and do not claim pixel conformance without it.

*A certified design transport.* The DesignGateway is built and proven, but
no certified Claude Design transport exists, so `/design` refuses with a
typed state. Register one implementing the `DesignProvider` protocol in
`engine/studio/design/providers.py`. Do **not** route it through
`capability.claude_code_invoke` — that is the substitution
`FRONTEND_STUDIO_REV3.md` section 23 forbids by name, and it would weaken
EDR-0001/EDR-0017's per-invocation approval.

The DDE-068 material below is retained because DDE-069's promotion path
must consume its verification, and because its guardrails remain binding.

**DDE-068 — Visual Verification & Critique Loop** (closed; reference).

Read:

- `docs/planning/product-studio-charter.md`
- `docs/planning/frontend-studio-gui-spec.md`
- `docs/planning/dde-067-chapter-gate.md`
- `docs/planning/design-tooling-integration.md`
- accepted `EDR-0016` VLM design-critic dependency/budget record — **what
  visual verification requires**
- accepted `EDR-0017` visual-critic execution route (Option C) — **how DDE
  safely obtains machine multimodal critique**: a narrow
  `capability.visual_critique`, deliberately separate from the broad,
  human-approval-gated `capability.claude_code_invoke`. Read it before
  touching the critic; its guardrails (no weakening of the broad
  capability, no `STANDING_FORBIDDEN_TYPES` bypass, no generic
  "narrowness" escape hatch, provider abstraction preserved) are binding.
- relevant visual/verification sections of `BLUEPRINT_REV3.md` and `DEV_PLAN_REV3.md`

Do not skip DDE-068 merely to start newer orchestration or DDE-069/Frontend Studio V2 work (which now includes the former mobile-profiles scope as a sub-capability, not a separate mission — see `ARCHITECTURE_DECISIONS.md` AD-030) unless code evidence proves DDE-068 is already evidence-complete.

### 4. DDE-068 execution rule

Implement DDE-068 as real production functionality, not documentation.

Required outcome includes:

1. a real visual verification executor behind DDE's verification/capability architecture;
2. rendered ProductEnvironment screenshot evidence persisted through VerificationRun/Evidence paths;
3. DD207+ generic-combination lints;
4. silhouette/fingerprint distinctiveness checking;
5. believable-density enforcement;
6. reduced-motion semantic verification;
7. VLM screenshot critique as rank-9 evidence;
8. bounded automatic revision of at most 3 cycles;
9. human escalation after the bound;
10. a real promotion/merge/quality gate that consumes the recorded visual verdict.

Do not call a schema enum, fixture, mock, CI-only screenshot or UI badge an implementation of these features unless the real production path invokes it.

**Status note (2026-09-04).** DDE-068 is `COMPLETE_EVIDENCED` and durably
closed. All ten elements are evidenced, including a live end-to-end run on
real pixels (`docs/evidence/dde-068/`): a poor candidate rejected, a good
candidate blocked on a real accessibility defect the deterministic layer had
passed, repaired from the critique's own instructions, and passed on cycle 1
— promotion ELIGIBLE. Row-by-row proof:
`docs/evidence/dde-068/CLOSURE_MATRIX.md`. The critic runs behind the narrow
`capability.visual_critique` per accepted `EDR-0017` (Option C, an accepted
Project Truth row, not just a markdown pre-image); the broad
`capability.claude_code_invoke` is unchanged and `STANDING_FORBIDDEN_TYPES`
was neither bypassed nor weakened. GUI-spec item D2 is closed. Do not
re-open DDE-068 to add default oracle bindings for generated screens — that
is explicitly DDE-069's, per `FRONTEND_STUDIO_REV3.md`'s own DDE-068
DEPENDENCY clause. **That DDE-069 item is now done** (2026-09-04):
`schemas/design/screen_acceptance_defaults.json` +
`engine/studio/acceptance/` bind `silhouette` and `visual_critique` onto
every generated screen through the `frontend.screen.register` command, so
the guarantee is universal rather than conditional. Do not re-implement
it.

### 5. Work in vertical slices

For each slice:

- map the exact Blueprint Rev 3 clauses and accepted EDRs;
- identify schemas/contracts first;
- create a failing contract/invariant test where practical;
- implement service/domain behavior;
- wire the real production call site;
- wire Gateway/API/UI if user-facing;
- implement typed failure/retry/reconciliation behavior;
- run focused tests;
- run the repo's required full checks before mission completion;
- perform a chapter-gate audit against production call sites;
- record evidence and residuals.

A green `just check` is necessary but is not chapter sign-off.

### 6. Never implement documented ideas as inert scaffolding

For every feature, explicitly answer:

- Where is the authoritative contract?
- Which service owns the behavior?
- Which real call site invokes it?
- What durable state transition occurs?
- What happens on failure/cancel/retry/recovery?
- Which capability/credential boundary applies?
- What proves it works?
- Which UI/API path exposes it, if applicable?

If these cannot be answered, the feature is not complete.

### 7. Orchestration and model delegation rules

DDE remains the source of mission/state authority regardless of worker.

#### Fable 5

Use Fable 5 as the preferred **strategic orchestration worker** only if a real supported adapter/interface is available and can be tested. Best-fit tasks are mission decomposition, architecture review, dependency/risk planning and arbitration.

Never invent a Fable adapter or make the project depend on an unavailable interface. If unavailable, keep the generic orchestration contract and mark the Fable adapter `BLOCKED_EXTERNAL`.

Fable outputs are proposals and must flow through draft -> validate -> promote.

#### Hermes

Use Hermes for persistent research/coordination roles where it adds value:

- repo reconnaissance;
- evidence gathering;
- context-packet preparation;
- dependency/license research;
- long-running operator assistance;
- failure triage and recovery packet preparation;
- Gateway/MCP conversational control.

Hermes memory is not authoritative. Rehydrate factual state from DDE.

#### Claude Code / premium reasoning profiles

Use them for high-complexity/high-risk implementation and review where superior reasoning materially improves expected outcome. Do not make them absorb all orchestration, crawling, monitoring, mechanical refactors and sole review because another preferred model is unavailable.

#### DeepSeek / lower-cost profiles

Use them for bounded coding, tests, mechanical refactors, documentation/code synchronization and parallel candidate generation when deterministic verification can arbitrate quality.

#### Independent verification

For high-risk work, prefer a different reviewer profile or deterministic oracle from the implementing worker.

### 8. Routing discipline

Routing uses eligibility first, optimization second.

Consider:

- capability/tool requirements;
- task complexity/risk;
- containment/credential tier;
- context requirements;
- provider health;
- quota availability;
- measured quality history;
- latency;
- cost.

Do not choose a cheaper worker if it cannot meet the required confidence/safety. Do not widen autonomy or capabilities to make a fallback route possible.

### 9. Context discipline

Do not dump the entire repository or historic chat into every worker context.

Assemble the smallest sufficient task packet with:

- authoritative requirements;
- affected schemas/contracts;
- relevant code paths;
- current state/evidence;
- known gaps;
- verification expectations;
- explicit unresolved questions.

Retain provenance and source rank. Retrieved donor/web/model material never outranks Project Truth.

### 10. Frontend Studio design law

Frontend Studio must produce professional, distinctive interfaces rather than generic AI dashboards.

Preserve the existing signed design strategy:

- conformance by construction;
- first-party tokens and semantic design roles;
- structured manifest mutations rather than arbitrary DOM/style edits;
- product-specific art direction and design read;
- donor/reference research grouped by product function;
- silhouette/fingerprint generic-layout detection;
- DD201+ design lints and combination lints;
- believable sample-data density;
- accessibility and reduced-motion evidence;
- screenshot critique and bounded revision.

External design skills/tools may inform research but must not become authoritative merge oracles. Encode useful ideas into DDE's own schemas, compilers, scanners and gates.

### 11. DDE Code product standard

Do not accept a merely functional/stubby operator UI.

DDE Code should feel like a professional software-manufacturing control plane. Preserve operational honesty and improve:

- visual hierarchy;
- typography;
- spacing/density;
- coherent iconography;
- responsive behavior;
- accessible interaction states;
- clear mission/fleet/approval/verification status;
- meaningful motion;
- loading/empty/degraded/error/blocked/completed states.

Never fabricate rows because a list endpoint does not yet exist. Disabled or empty with a factual reason is correct.

### 12. Security invariants

Never:

- pass long-lived credentials into model-generated execution;
- add direct core-table access from interfaces;
- import vendor SDKs into core;
- widen egress silently;
- execute unclassified donor code;
- retry uncertain side effects without idempotency/reconciliation;
- widen filesystem/network/autonomy scope to make a test pass;
- export sensitive personal/project data for convenience.

### 13. Cost/quota discipline

For every new model/tool-dependent feature, determine:

- what can be deterministic instead;
- what can use lower-cost workers;
- when premium reasoning is justified;
- maximum bounded retry/revision cycles;
- fallback behavior under quota/provider failure;
- telemetry required to improve routing later.

Do not solve provider scarcity by shifting all work to another expensive model.

### 14. Completion protocol

At the end of each meaningful tranche:

1. run applicable focused tests and full checks;
2. inspect the actual diff and production call sites;
3. create/update the mission chapter-gate record if appropriate;
4. update `docs/truth/IMPLEMENTATION_STATE.md` with:
   - new HEAD/commit(s),
   - exact state transitions,
   - production call sites added,
   - tests/verification evidence,
   - unresolved residuals,
   - the immediate next work packet;
5. update `ARCHITECTURE_DECISIONS.md` only if a real decision changed;
6. update Blueprint/Plan only through proper change control when architecture or sequence materially changes.

Do not leave the only record of progress in chat.

### 15. Stop conditions

Stop and raise a blocker rather than inventing a contract when:

- an accepted EDR/Project Truth decision is required;
- a provider/interface such as Fable 5 is unavailable and no generic contract path can progress safely;
- two authoritative sources conflict;
- a required credential/capability cannot be obtained through the accepted broker path;
- implementation would require silently weakening a security or authority invariant.

Otherwise continue with the smallest evidence-producing vertical slice. Do not ask for permission for ordinary implementation decisions already resolved by the Blueprint, accepted EDRs and Rev 3 plan.

### 16. First response / first work packet

Begin by reporting only evidence-backed findings from the current repository:

- current branch/HEAD;
- whether Rev 3 SOT files and pointers are intact;
- actual current mission state;
- target mission and why it is next;
- the first vertical slice;
- any genuine blocker.

Then execute the work. Do not spend the session rewriting the plan that already exists.

---

## End of canonical resume prompt

The purpose of this file is to make a new engineering session cheap to start, accurate and independent of historic chat context. Update it only when bootstrap behavior itself changes.