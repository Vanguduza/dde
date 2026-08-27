# Frontend Studio charter — PRD → playbook-aligned generation prompt +
# Donor Lab feature-mapped donor discovery + Visual Verification & Critique Loop

**Status:** **SIGNED OFF by owner standing directive 2026-08-24** ("close
all these to your recommendations", in response to the queued-decision list).
v3 renames the workstream **Frontend Studio** and adds the
conformance-by-construction authoring law (§4.1) + GUI spec integration
(`frontend-studio-gui-spec.md`) per the owner's >95% confidence bar:
quality must be unautherable, not merely inspected. v2 hardened the
output-quality loop into a blocking mission (DDE-068) per the owner's
direction that generated products must be polished and non-generic, not
merely produced. Prepared from the six-stream anti-generic-output
research and verified against the repo state at `34127f4` (`09baee6`
findings re-checked where cited below). This is a work-planning
document, not an EDR; no Project Truth rows are created or modified by
it. At sign-off: **EDR-0015** and **EDR-0016** filed PROPOSED same day
(2026-08-24); DDE-065 + DDE-067 GUI shell authorized to start under the
standing auto-resume order (§7).

**Design-tooling priors (2026-08-26):**
`docs/planning/design-tooling-integration.md` is a **binding design input
and acceptance-criteria seed** for DDE-065 / DDE-067 / DDE-068 (recorded
in gap-closure-record §6.10). Disposition: encode harvested concepts
(art-direction dials + DESIGN.md grammar; DD207+ / WIG non-axe lints)
into first-party schemas and scanners — do **not** install third-party
design skills as merge-blocking oracles.

## 0. Naming

`dde-studio` (`interfaces/dde-studio/package.json`, displayName "DDE
Code") is already the **control-plane UI** — a Gateway/CLI client over
`/v1` that never touches Core tables. This requirement is a
**product-generation studio**: a pipeline that turns an approved PRD into
UI-generation prompts plus a categorized donor/tool inventory for the
*generated product*. Per owner decision 2026-08-24 the workstream is
named **"Frontend Studio"** (was "Product Studio"); "studio" alone stays
reserved by the existing extension. The GUI/UX specification for the
studio surface lives in `docs/planning/frontend-studio-gui-spec.md`
(button-add, drag-and-drop, live preview editing) and is binding input
to DDE-067's charter scope below.

## 1. Mission decomposition

Per `.cursor/rules/mission-chapter-gate.mdc`, this composes with S5
missions but adds real new surface (prompt compilation, donor search,
grouped results schema, visual critique/verification loop) that no
charter names. Inserted workstream of four missions:

### DDE-065 — Generation-Prompt Compiler (deterministic, offline)

- **Scope IN:** deterministic compiler under `engine/studio/` (sibling of
  `engine/planning/`). Inputs are all durable artifacts: the
  approved PRD's Requirement rows, the art-direction record
  (gap-closure-record §6.5 + **design-tooling-integration.md §4.1 / Phase 1** —
  Stitch/DESIGN.md section grammar plus Taste-derived dials
  `DESIGN_VARIANCE` / `MOTION_INTENSITY` / `VISUAL_DENSITY` and a one-line
  Design Read; `schemas/design/tokens.json` remains the sole visual
  value authority), the nevers
  catalog (playbook §1.1), the copy law (`FORBIDDEN_HELPER` superset),
  the declared layout-pattern map. Output: one versioned
  generation-prompt artifact per PRD, pinned to playbook version and
  token-sheet version. Composition rule: any candidate task decomposition
  flows through the DDE-040 registry path (`submit_draft` → UNTRUSTED →
  `validate_draft` → `promote_draft`) — never mints graphs directly.
  **Fail-closed input rule:** every visual input must RESOLVE before
  compilation runs. The compiler never accepts "stubbed" art-direction
  or placeholder token pins: if the art-direction record is absent, or
  the pinned `tokens.json` version cannot be loaded and matched against
  its recorded hash, compilation is refused. No compiled prompt exists
  before art-direction record + tokens pin BOTH resolve.
- **Scope OUT:** network calls; live model calls at compile time; donor
  search (DDE-066); Project Truth changes; new dependencies (stdlib-only
  string assembly).
- **Anchors:** Ch.2.2 rank discipline (rank-9 donor material informs,
  never modifies rank ≤3 artifacts); Ch.4.3 determinism split; playbook
  §4 guardrails as compile-time constraint injection; Ch.15.4 typed
  errors for every refusal; EDR-0014 context — the compiler must not
  become a second inert-gate site.
- **Acceptance criteria:**
 - MUST produce byte-stable output for identical inputs (hash recorded).
 - MUST refuse (typed, Ch.15.4 family) when the PRD has no approved
   Requirements or references an unknown token/playbook version.
 - MUST refuse (typed, same family) when the art-direction record is
   absent OR the tokens pin does not resolve — no degraded/stubbed
   compile path exists; the refusal names the missing input artifact.
 - MUST refuse when art-direction lacks the three dials, Design Read
   string, or semantic palette roles required by
   `design-tooling-integration.md` Phase 1 (same fail-closed family).
 - SHALL embed every §1.1 never and the token-sheet reference such that
   a generated prompt cannot instruct off-token values (contract test
   scans prompt content).
 - SHALL record provenance (input artifact ids + versions) so any
   generated screen traces back to its PRD.
 - MUST NOT make a network or model call in the compile path.
 - MUST NOT load third-party design skills (Taste Skill, Impeccable
   guidance, Vercel agent-skills) into the compile path — encodings only
   (`design-tooling-integration.md` §7).

### DDE-046 note — manual pin-by-URL (owner requirement, 2026-08-24)

DDE-046's ingest surface MUST accept a human-supplied `source_uri`
(repo, registry JSON, gallery page, fixture path) as a first-class entry
path — not discovery-only. Studio Donors view and Chat/MCP both post the
same Gateway command (`frontend.donors.submit_uri`); chat is a client,
not a bypass. Default class stays `UNKNOWN` until DDE-047; pinning
creates `identified` candidates only — adoption remains `donor_reuse`.

### DDE-066 — Donor Discovery & Feature-Function Taxonomy (extends DDE-046)

- **Scope IN:** search fan-out over donor sources classified per Ch.13.8:
  GitHub API for repos/tools/libraries; shadcn-ecosystem registries
  (`OPEN_REUSE`); commercial template products (`CONDITIONAL_REUSE`,
  metadata only); marketplace bundles (`REJECTED`, excluded entirely).
  Results grouped by product function/feature category derived from the
  PRD feature inventory; every result carries licence class + provenance
  taint from day one. Grouped-results schema lands in `schemas/design/`
  (or `schemas/objects/`) under the SSOT/drift discipline (Ch.3.1).
  Manual pins from DDE-046 appear in the same grouped inventory (they are
  not a parallel list).
- **Scope OUT:** executing donor code (never — Ch.13.8); ingesting code
  into the generator (adoption is a separate signed reuse decision);
  licence classification itself stays owned by DDE-047 — this mission
  consumes classifier verdicts.
- **Anchors:** Ch.13.8 (classification BEFORE use); Ch.2.2 rank 9;
  Ch.14.5 invariant 6 (injection authority cap); Ch.9.3 side-effect
  classes for every new capability.
- **Dependencies:** DDE-046, DDE-047, DDE-065, **EDR-0015** (egress,
  below).
- **Acceptance criteria:**
 - MUST classify every source against the six-value scale BEFORE any
   result becomes usable downstream; UNKNOWN defaults to
   `SOURCE_REFERENCE_ONLY`/`REJECTED` and can never silently upgrade.
 - SHALL group results by category where every category maps to ≥1
   PRD-derived feature id; every ungroupable result lands in an explicit
   `unmatched` bucket (no silent drops).
 - MUST persist taint tags answering Ch.13.8's question "which donor
   evidence influenced this artifact."
 - MUST fail closed (empty results + typed refusal) rather than degrade
   classification when the classifier is unreachable.
 - Every outbound query carries an idempotency key and writes an
   ExternalEffect journal row before retry (Ch.12.4).

### DDE-067 — Frontend Studio Surface & Consumption Wiring

- **Scope IN:** Studio-facing surface that accepts a PRD, triggers
  compilation, displays grouped donor results, feeds both consumers:
  (a) planning — adoptables enter as candidate draft nodes through the
  ordinary DDE-040 path; (b) generation — compiled prompt + selected
  donors feed prototype authoring through the existing pipeline (P1 plan
  checkpoint → screens × states → `flows.json` → pixel sign-off,
  playbook §5.4). Lives in `interfaces/dde-studio/**`, Gateway-client
  only.
- **Scope OUT:** renaming the control-plane extension; bypassing
  approvals; auto-adopting donor code without a `donor_reuse` approval.
- **Anchors:** Ch.15 Gateway rules; Ch.13 approvals (`donor_reuse` type
  already exists in `engine/governance/types.py`); playbook §5.4; Ch.16.4
  budget accounting includes search + compile costs.
- **Dependencies:** DDE-065, DDE-066, DDE-068 (the surface renders
  whatever quality verdicts DDE-068 produces); benefits from DDE-043/044
  but does not block on them.
- **Acceptance criteria:**
 - MUST require a recorded `donor_reuse` approval before donor-derived
   implementation enters a production task (wire the existing enum at a
   real mutation call site).
 - SHALL route every command through the Gateway command surface with
   idempotency keys (Ch.12.5 pattern as implemented in
   `engine/planning/registry.py`).
 - MUST keep honesty tests green: no fabricated donor rows in empty
   states. The empty-state UI shell MAY proceed in parallel with
   DDE-065/066/068, but only as honest empty states — no placeholder
   rows, no fake verdicts, no mock quality badges.
 - Generated UI passes the full §Definition-of-Polished battery (below)
   once DDE-068 lands; until then today's floor applies (DD201–DD206 +
   honesty tests), and no screen may merge on the promise of future
   gates.
 - The GUI implements `docs/planning/frontend-studio-gui-spec.md`:
   button-add, drag-and-drop, and live preview editing are ALL structured
   manifest mutations through one command path — never raw DOM patches.
   **Conformance by construction:** every value picker in the studio UI
   offers ONLY token-valid options (colors/fonts/spacing/motion from
   generated `tokens.ts`); there is no free-form style input anywhere in
   v1. This makes DD201–DD206 violation classes unautherable at authoring
   time rather than caught at lint time — the primary structural
   advantage over generate-then-critique builders.

### 4.1 Conformance by construction (the >95% bar)

The charter's confidence claim rests on three interlocking mechanisms,
each independently blocking:

1. **Unautherable violations (DDE-067 GUI):** token-bound pickers +
   manifest-mutation-only editing mean off-token values cannot be
   expressed in the authoring surface at all.
2. **Measured quality (DDE-068 loop):** rendered pixels judged against
   rubric/silhouette/density gates with bounded revise — catches what
   conformance-by-construction cannot (composition, hierarchy,
   distinctiveness).
3. **Constrained inputs (DDE-065 compiler):** generation prompts embed
   nevers/tokens/copy-law as compile-time constraints with fail-closed
   input resolution, so even model-generated first drafts start inside
   the guardrail envelope.

A builder that only generates (v0/Bolt-class) has none of these; Cocodly
implements mainly (2); DDE implements all three, which is why the bar is
"surpass" rather than "match."

### DDE-068 — Visual Verification & Critique Loop

The output-quality enforcement mission. The other three missions build
the pipeline; this one guarantees the owner's bar — polished, modern,
non-generic output ("cocodly-class") — is *measured* on every generated
screen before it can merge, using the blocking-gate grammar of
`.cursor/rules/mission-chapter-gate.mdc` applied to pixels instead of CI.

- **Scope IN:**
  1. **Phase-B toolchain as a real capability.** Wire the admitted
     EDR-0008 Phase B toolchain (Playwright render + screenshot evidence;
     `visual/screens.spec.ts` + `playwright.config.ts` + `server.cjs`
     exist and run in `.github/workflows/dde-studio.yml`) behind the
     engine's capability contract so the verification runner can request
     rendered-pixel evidence of any generated screen, with captures
     persisted as VerificationRun/Evidence artifacts (playbook §5.3 row
     3). Today `engine/verification/oracle.py` executes only
     `test`/`invariant` bindings — `judge`, `human`, and `visual_diff`
     are validated-but-unexecuted enum members; this mission gives the
     visual path a real executor or a declared adapter seam.
  2. **VLM screenshot-critique loop.** Screenshot → rubric critique
     (scored against playbook §8 scorecards) → bounded revise ≤3 cycles
     → residuals escalate to human. Each revise cycle consumes a stored
     critique artifact; cycle count >3 blocks auto-progression and
     requires explicit human approval. Critiques are rank-9 model-
     assisted evidence (Ch.2.2): they inform, they never auto-apply —
     every revise instruction flows through the existing
     verification/approval surfaces, never directly into code.
  3. **Silhouette test.** Coarse layout-shape fingerprint (block
     positions, column count, hero grammar) per rendered screen,
     compared against a corpus of documented generic layouts
     (playbook §10.3); near-match = blocker regardless of palette.
  4. **DD207+ combination lints.** Extend
     `tests/unit/test_studio_design_lints.py` (which implements exactly
     DD201–DD206 via `scripts/design_lints.py`) with the combination/
     fingerprint level: Inter-only type + indigo-family accent +
     centered-hero-3-card skeleton, emoji-as-icon + pill-spam rows
     (playbook §10.2). A file passing DD201–206 while slop-shaped must
     fail.
  5. **Density floor as enforcement, not documentation.** The playbook
     §8.3 believable-density dimension becomes a blocking
     verification-runner check over generated screens (marked sample
     data must let hierarchy/rhythm/states be judged; "Item 1"/lorem-
     grade filler fails).
  6. **Reduced-motion blocking assertions.** Playwright assertions that
     end-states are preserved and spatial movement removed under
     `prefers-reduced-motion: reduce` (the reduced-motion golden pass in
     `screens.spec.ts` covers animated fixtures today; extend to assert
     degradation semantics, not just snapshot stability).
- **Scope OUT:** embedding anti-centroid scoring (separate heavier EDR
  per gap-closure §6.5); motion-library budget admission (verification-
  runner extension EDR); CWV budgets (Ch.16.5 territory, DDE-063);
  template ingestion (DDE-046's EDR); any Project Truth changes.
- **Anchors:** EDR-0008 Phase B (accepted toolchain); Ch.11.2 acceptance
  oracles + Ch.11 verification chain (evidence, not vibes); Ch.2.2 rank
  discipline (critiques rank-9 forever); Ch.12.4 (each critique/revise
  cycle is a side-effecting step: idempotency key + journal row before
  retry); Ch.15.4 typed errors for every refusal class; Ch.9.3
  side-effect classes for the new capabilities.
- **Dependencies:** EDR-0008 Phase B (accepted; partially landed);
  **EDR-0016** — "VLM design-critic dependency & budget" — filed at THIS
  charter time, covering which multimodal model(s), brokered credential
  path, per-mission cost ceiling, rubric storage location and versioning,
  and critique-retention policy; implementation may not start before
  EDR-0016 acceptance (mirrors the EDR-0008 accept-first pattern).
  Benefits from DDE-043/044 browser capability but does not block on it
  — the Phase-B harness already renders fixture screens through the
  production CSP wrapper (`visual/server.cjs`).
- **Acceptance criteria (testable):**
 - A generated screen that fails the density floor OR matches a
   generic-corpus silhouette CANNOT reach a merged state: the merge-path
   check refuses with a typed error and records the refusal (contract
   test exercises the refusal, not just the happy path).
 - Each revise cycle consumes exactly one persisted critique artifact;
   a cycle count >3 escalates to human approval and auto-progression is
   blocked (testable by driving the loop counter past the bound).
 - Reduced-motion assertion failure BLOCKS (red run, no waiver flag).
 - VLM rubric below threshold blocks merge UNLESS an explicit human
   pixel sign-off row exists through the approvals surface.
   **Correction (2026-08-24):** `prototype_pixel_signoff` does NOT exist
   in `APPROVAL_TYPES` (`engine/governance/types.py` — verified; the
   earlier "vocabulary already exists" claim was wrong). DDE-068 scope
   IN: add the member through the ordinary contract path (types +
   `schemas/objects/approval.json` + contract regen + tests) or the
   owner designates an existing type — GUI-spec open item D2.
 - Silhouette fingerprints and lints are deterministic: identical inputs
   produce identical verdicts (hash-recorded), so the gate itself is
   reproducible evidence, not reviewer mood.
 - Every critique/critique-driven mutation carries an idempotency key
   and writes its journal row before retry (Ch.12.4), testable by
   replaying a duplicated critique request and asserting one effect.

## 2. Reuse map (verified against files)

| Existing asset | Verified location | Role |
|---|---|---|
| Prototype pipeline P1–P4 | playbook §5.0–§5.6 | DDE-067 consumes the loop |
| Art-direction record plan | playbook §10.1 + gap-closure §6.5 | compiler input |
| Template-sourcing law | playbook §10.5 + Ch.13.8 amendment | defines DDE-066's searchable universe |
| Donor governance + licence classes | REV_2_0.md Ch.13.8 (~2038–2046) | six-value scale, taint, signed reuse |
| DDE-046 ingestion / DDE-047 classifier | §18.3 S5; `engine/integration/gate_service.py:36,55` notes taint graph absent yet | DDE-066 extends, not competes |
| Model-assisted planning machinery | `engine/planning/registry.py` | composition path for decompositions |
| Approval vocabulary | `engine/governance/types.py` (`donor_reuse`, …) | human gates need zero new types |
| Prototype verification sweep | `engine/verification/prototypes.py` + flow schema | mechanical validation pre-oracle |
| Token SSOT | `schemas/design/tokens.json` + `scripts/generate_design_tokens.py` (--check drift gate in dde-studio.yml design-gates job) | prompts pin to the sheet |
| Design lints + honesty gates | DD201–DD206 only (`scripts/design_lints.py`; DD207+ ABSENT today), `clientHonesty.test.ts`, binding rule file | today's quality floor |
| Visual Phase-B harness (landed) | `interfaces/dde-studio/visual/{screens.spec.ts,playwright.config.ts,server.cjs}` + `dde-studio.yml` `visual` job (goldens light/dark × 320/900/1280 + axe wcag2a/aa/22aa + reduced-motion pass on animated screens) | DDE-068 builds its critique/silhouette/density gates on this renderer |
| Verification runner (Stage 1) | `engine/verification/oracle.py` — EXECUTABLE_KINDS = {test, invariant} only; judge/human/visual_diff accepted-but-unexecuted | DDE-068 adds the visual/judge executor seam |
| Studio surfaces | `interfaces/dde-studio/**` incl. live gallery + Gateway client | display surface |

## 3. Pipeline sketch

```
Approved PRD (Ch.2.2 rank 2)
 → Requirements rows (Ch.3)
 ↓
[DDE-065] deterministic generation-prompt compiler        NO network/model call
 inputs: requirements+features · tokens · art-direction (REQUIRED —
 · nevers · copy law · declared patterns · playbook version pin   fail-closed)
 output: versioned prompt artifact w/ provenance
 ↓
[DDE-066] Donor Lab search fan-out                        ⚠ NETWORK — see EDR-0015
 sources: GitHub API · shadcn registries (OPEN_REUSE)
 · commercial template metadata (CONDITIONAL_REUSE) · marketplaces excluded
 mapping: searched function ↔ PRD feature id
 ↓
grouping taxonomy (durable schema): { donor_id, source_class(Ch.13.8),
licence_class, taint_tags[], feature_categories[], provenance{url,ref,retrieved_at},
adoption_state: identified|screened|approved(donor_reuse)|rejected }
 ↓                                                    ↘
[DDE-067] planning consumer                    [DDE-067] generation consumer
 adoptables as draft nodes via                 prompt + approved donors feed
 DDE-040 promote path (gates intact)           prototypes/ → screens × states
                                                        ↓
                                              [DDE-068] Visual Verification & Critique Loop
                                              render (Phase-B harness) → screenshot
                                              → VLM rubric critique → bounded revise ≤3
                                              → silhouette + DD207+ + density + reduced-motion
                                              gates → PASS ⇒ pixel sign-off / FAIL ⇒ human
```

Constraints: grouping schema additive-first (Ch.3.1 rule 3) with
tenant/project scope + RLS where Ch.3.2 applies; search results AND VLM
critiques are rank-9 evidence forever; the compiler's artifact feeds the
P1 checkpoint so screens × states derives from the same inventory the
donor search used — one inventory, two consumers, no divergence. The
DDE-068 loop is the LAST stage before sign-off: nothing merges on the
promise of later polish.

## 4. Definition of Polished (blocking bar)

Every generated product/screen must pass this exact battery BEFORE
merge. Each gate names its live enforcement point today or its landing
mission; per the chapter-gate rule, a gate without a wired call site is
deferred, never "implicitly handled."

| # | Gate | Threshold | Status TODAY | Lands with |
|---|---|---|---|---|
| 1 | Design lints DD201–DD206 clean | zero violations vs committed shrink-only baseline | LIVE — `scripts/design_lints.py` in dde-studio.yml design-gates job | — |
| 2 | Combination lints DD207+ clean | no generic fingerprint combinations | NOT IMPLEMENTED (`design_lints.py` stops at DD206) | DDE-068 |
| 3 | Silhouette-distinct | layout-shape fingerprint ≠ generic-corpus near-match | NOT IMPLEMENTED | DDE-068 |
| 4 | Density scorecard ≥ floor | believable-density ≥4 per playbook §8.3 ("<4 blocks") | advisory-only (human review dimension) | DDE-068 (blocking runner check) |
| 5 | VLM rubric ≥ threshold OR explicit human pixel sign-off | rubric threshold set by EDR-0016; sign-off via approvals surface | manual fresh-context critique only (playbook §4.7) | DDE-068 (loop) |
| 6 | Honesty tests green | no fabricated rows/copy violations | LIVE — `clientHonesty.test.ts` PR-blocking in dde-studio.yml | — |
| 7 | Per-interaction motion spec present, incl. reduced-motion degradation | trigger/easing/duration/stagger/reduced-motion fields in manifest; assertion red on violation | partial — reduced-motion goldens exist for animated fixtures (`screens.spec.ts`); manifest fields absent | DDE-068 (+ prototype-manifest schema extension) |
| 8 | Provenance traceable to PRD | compiled prompt's provenance chain resolves PRD → features → donors → screen | mechanism defined (DDE-065 AC) | DDE-065 |

Rule: a screen may merge when ALL eight are green — five live today for
existing surfaces, three arrive with DDE-065/068. Until DDE-068 lands,
gates 2–4 remain OPEN GAPS: existing-surface floors stay DD201–DD206 +
honesty tests, and NO generated product ships claiming compliance it
cannot yet demonstrate (honesty law applies to process claims too).

## 5. Guardrails — every place this bites

1. **Network access — the big one.** EDR-0011 is proposed and its
   precondition was deferred by human decision 2026-08-23 (gap-closure
   §6.3). File **EDR-0015 — "Donor-search egress admission"**: which
   hosts, broker-issued credentials only, rate/quota ownership, T2
   boundary vs control-plane service placement. DDE-066 cannot start
   implementation before acceptance; its charter may be written now.
2. **Injection screening.** Donor READMEs/registry JSON/descriptions are
   untrusted; Ch.14.5 invariant 6 caps their authority at rank 10;
   screening precedes any model-visible surface; grouped fields are
   hypotheses, not facts.
3. **Licence classification BEFORE use** — enforced by ordering inside
   DDE-066 and tested by fail-closed-on-classifier-unreachable.
4. **Human gates.** Adoption = `donor_reuse` approval (exists);
   CONDITIONAL_REUSE purchases = owner decision first (playbook §10.5);
   VLM-loop residuals after ≤3 revise cycles = human pixel sign-off
   (DDE-068).
5. **No blind chaining.** Chapter gates per mission; note EDR-0014's
   finding — charters must verify they don't extend the inert-gate path.
   DDE-068 exists precisely so "generated" ≠ "shipped."
6. **AGENTS.md forbidden list:** no second source of truth (grouped
   results = derived cache + evidence; critiques = derived evidence);
   no un-keyed retries (critique/revise cycles included); no silent
   network widening (EDR-0015 is the instrument; EDR-0016 admits the
   model dependency, nothing else); side-effect classes declared.
7. **Rank discipline for model-assisted critique (NEW).** VLM critiques,
   rubric scores, and revise instructions are rank-9 evidence: they
   inform humans and the bounded revise loop but never modify rank ≤3
   artifacts directly, never auto-approve themselves, and never widen
   autonomy. A revise instruction reaches code only through the ordinary
   verification/approval surfaces.
8. **Idempotent side effects in the loop (NEW).** Every critique call,
   revise cycle, screenshot capture, and refusal write is side-effecting
   or durable: idempotency key + journal row before retry (Ch.12.4),
   observable state machine for cycle count, typed Ch.15.4 errors for
   each refusal/bound-exceeded class.

## 6. Sequencing

| Item | When | Why |
|---|---|---|
| DDE-067 GUI shell | may start after charter sign-off, in parallel | honest empty states only; implements `frontend-studio-gui-spec.md` navigation/canvas skeleton |
| DDE-065 compiler | can start after charter sign-off | offline, stdlib-only, deps landed. Fail-closed rule replaces the old stubbed-input caveat: sequence the art-direction record first (it remains §6.5 adopt-now), and until then the compiler REFUSES rather than accepts stubs — no compiled prompt exists without art-direction record + resolved tokens pin |
| Art-direction record + font corpus | before first real DDE-065 compile | §6.5 adopt-now items the compiler hard-depends on; owning missions named in gap-closure §6.5 table |
| EDR-0015 | file at DDE-066 charter time | mirrors EDR-0008's accept-first pattern |
| EDR-0016 | file AT THIS CHARTER TIME (with sign-off) | DDE-068 needs the VLM critic admitted (model calls, cost ceiling, rubric storage) before implementation starts |
| DDE-066 | after EDR-0015 accepted AND DDE-046/047 exist | classify-before-use ordering (Ch.13.8) |
| DDE-067 surface | UI shell earlier IN PARALLEL — honest empty states only; full wiring after 065+066+068 | honesty tests permit empty states now; no fabricated rows, no mock quality verdicts |
| DDE-068 quality loop | after EDR-0016 accepted; Phase-B harness already landed so it starts from a working renderer | the guarantee layer: nothing merges on promised polish |
| Silhouette/VLM quality loop | OWNED BY DDE-068 (was: rides DDE-044's EDR cycle) | Phase-B screenshots exist today in dde-studio.yml; only the critic dependency was missing |

Stage placement: S5 (Capability breadth), appended behind the current
chain head as DDE-065/066/067/068; numbering beyond §18.3 documented via
`docs/planning/mission-numbering-note.md`.

## 7. Charter sign-off

**SIGNED OFF 2026-08-24 by owner standing directive** — "close all these to
your recommendations", issued in response to the queued-decision list
presented that day. Recorded actions: (1) acceptance is recorded in this
file's status line; (2) **EDR-0015** and **EDR-0016** were filed PROPOSED on
the same day (both mirror EDR-0008's accept-first pattern — charters written
now, implementations gated on acceptance); (3) **DDE-065 (offline compiler)
and the DDE-067 GUI shell are authorized to start immediately** under the
standing auto-resume order, since they touch no egress and no model calls;
DDE-065's fail-closed input rule makes the art-direction record (§6.5
adopt-now) the pacing item for the FIRST real compile; (4) DDE-068's chapter
gate covers the whole quality loop: per
`.cursor/rules/mission-chapter-gate.mdc`, the gate is passed only when every
§Definition-of-Polished gate names a production call site (or a named
deferral + EDR), and the bounded-revise/human-escalation rules are wired
where mutations actually happen — CI green alone closes nothing. DDE-066
waits on EDR-0015 acceptance; DDE-068 implementation waits on EDR-0016
acceptance.

Pre-sign-off text retained for the record: this charter required the owner's
decision before any of DDE-065..068 entered execution; until signed off,
nothing here authorized implementation work.
