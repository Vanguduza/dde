# Product Studio charter — PRD → playbook-aligned generation prompt +
# Donor Lab feature-mapped donor discovery

**Status:** proposed charter (2026-08-24), awaiting owner sign-off.
Prepared from the six-stream anti-generic-output research and verified
against the repo state at `09baee6`. This is a work-planning document,
not an EDR; no Project Truth rows are created or modified by it.

## 0. Naming

`dde-studio` (`interfaces/dde-studio/package.json`, displayName "DDE
Code") is already the **control-plane UI** — a Gateway/CLI client over
`/v1` that never touches Core tables. This requirement is a
**product-generation studio**: a pipeline that turns an approved PRD into
UI-generation prompts plus a categorized donor/tool inventory for the
*generated product*. "Product Studio" names the new workstream; "studio"
alone stays reserved by the existing extension.

## 1. Mission decomposition

Per `.cursor/rules/mission-chapter-gate.mdc`, this composes with S5
missions but adds real new surface (prompt compilation, donor search,
grouped results schema) that no charter names. Inserted workstream of
three missions:

### DDE-065 — Generation-Prompt Compiler (deterministic, offline)

- **Scope IN:** deterministic compiler under `engine/planning/` (or
  sibling `engine/studio/`). Inputs are all durable artifacts: the
  approved PRD's Requirement rows, the art-direction record once it lands
  (gap-closure-record §6.5; until then `schemas/design/tokens.json` is
  the sole visual authority per the binding rule file), the nevers
  catalog (playbook §1.1), the copy law (`FORBIDDEN_HELPER` superset),
  the declared layout-pattern map. Output: one versioned
  generation-prompt artifact per PRD, pinned to playbook version and
  token-sheet version. Composition rule: any candidate task decomposition
  flows through the DDE-040 registry path (`submit_draft` → UNTRUSTED →
  `validate_draft` → `promote_draft`) — never mints graphs directly.
- **Scope OUT:** network calls; live model calls at compile time; donor
  search (DDE-066); Project Truth changes; new dependencies (stdlib-only
  string assembly).
- **Anchors:** Ch.2.2 rank discipline (rank-9 donor material informs,
  never modifies rank ≤3 artifacts); Ch.4.3 determinism split; playbook
  §4 guardrails as compile-time constraint injection; EDR-0014 context —
  the compiler must not become a second inert-gate site.
- **Acceptance criteria:**
 - MUST produce byte-stable output for identical inputs (hash recorded).
 - MUST refuse (typed, Ch.15.4 family) when the PRD has no approved
   Requirements or references an unknown token/playbook version.
 - SHALL embed every §1.1 never and the token-sheet reference such that
   a generated prompt cannot instruct off-token values (contract test
   scans prompt content).
 - SHALL record provenance (input artifact ids + versions) so any
   generated screen traces back to its PRD.
 - MUST NOT make a network or model call in the compile path.

### DDE-066 — Donor Discovery & Feature-Function Taxonomy (extends DDE-046)

- **Scope IN:** search fan-out over donor sources classified per Ch.13.8:
  GitHub API for repos/tools/libraries; shadcn-ecosystem registries
  (`OPEN_REUSE`); commercial template products (`CONDITIONAL_REUSE`,
  metadata only); marketplace bundles (`REJECTED`, excluded entirely).
  Results grouped by product function/feature category derived from the
  PRD feature inventory; every result carries licence class + provenance
  taint from day one. Grouped-results schema lands in `schemas/design/`
  (or `schemas/objects/`) under the SSOT/drift discipline (Ch.3.1).
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

### DDE-067 — Product Studio Surface & Consumption Wiring

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
- **Dependencies:** DDE-065, DDE-066; benefits from DDE-043/044 but does
  not block on them.
- **Acceptance criteria:**
 - MUST require a recorded `donor_reuse` approval before donor-derived
   implementation enters a production task (wire the existing enum at a
   real mutation call site).
 - SHALL route every command through the Gateway command surface with
   idempotency keys (Ch.12.5 pattern as implemented in
   `engine/planning/registry.py`).
 - MUST keep honesty tests green: no fabricated donor rows in empty
   states.
 - Generated UI passes gap-closure §6.5 standing rule (combination lints
   + silhouette test once they exist; DD201–DD206 + honesty tests are
   today's floor).

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
| Token SSOT | `schemas/design/tokens.json` → generated `tokens.ts` | prompts pin to the sheet |
| Design lints + honesty gates | DD201–DD206 scanner, `clientHonesty.test.ts`, binding rule file | quality floor |
| Studio surfaces | `interfaces/dde-studio/**` incl. live gallery + Gateway client | display surface |

## 3. Pipeline sketch

```
Approved PRD (Ch.2.2 rank 2)
 → Requirements rows (Ch.3)
 ↓
[DDE-065] deterministic generation-prompt compiler        NO network/model call
 inputs: requirements+features · tokens · art-direction (when landed)
 · nevers · copy law · declared patterns · playbook version pin
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
 DDE-040 promote path (gates intact)           prototypes/ → pixel sign-off
```

Constraints: grouping schema additive-first (Ch.3.1 rule 3) with
tenant/project scope + RLS where Ch.3.2 applies; search results are
rank-9 evidence forever; the compiler's artifact feeds the P1 checkpoint
so screens × states derives from the same inventory the donor search used
— one inventory, two consumers, no divergence.

## 4. Guardrails — every place this bites

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
   CONDITIONAL_REUSE purchases = owner decision first (playbook §10.5).
5. **No blind chaining.** Chapter gates per mission; note EDR-0014's
   finding — charters must verify they don't extend the inert-gate path.
6. **AGENTS.md forbidden list:** no second source of truth (grouped
   results = derived cache + evidence); no un-keyed retries; no silent
   network widening (EDR-0015 is the instrument); side-effect classes
   declared.

## 5. Sequencing

| Item | When | Why |
|---|---|---|
| DDE-065 compiler | can start after charter sign-off | offline, stdlib-only, deps landed. Caveat: art-direction record is §6.5 adopt-now — sequence it first or ship compiler accepting stubbed input that fails closed until present |
| EDR-0015 | file at DDE-066 charter time | mirrors EDR-0008's accept-first pattern |
| DDE-066 | after EDR-0015 accepted AND DDE-046/047 exist | classify-before-use ordering (Ch.13.8) |
| DDE-067 surface | after 065+066; UI shell earlier | honesty tests permit empty states now |
| Silhouette/VLM quality loop | rides DDE-044's EDR cycle | needs browser capability + Phase B screenshots |

Stage placement: S5 (Capability breadth), appended behind the current
chain head as DDE-065/066/067; numbering beyond §18.3 documented via
`docs/planning/mission-numbering-note.md`.

## 6. Charter sign-off

This charter requires the owner's decision before any of DDE-065..067
enters execution. On sign-off: (1) record acceptance in this file's
status line, (2) file EDR-0015 as PROPOSED at DDE-066 charter time,
(3) launch DDE-065 (offline compiler) — it may start immediately under
the standing auto-resume order since it touches no egress and no model
calls. Until signed off, nothing here authorizes implementation work.

