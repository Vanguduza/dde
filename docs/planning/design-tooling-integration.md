# Design-tooling integration — consolidated recommendations

**Date:** 2026-08-26. **Nature:** docs-only consolidation of (1) the external build
brief `dde-design-tooling-integration-brief-1.md`, (2) an independent evaluation of
that brief against live repo state, and (3) a second evaluation of Taste Skill,
Vercel Web Interface Guidelines, and Awesome DESIGN.md. No engine code changes, no
Project Truth rows, no new dependency admitted by this file alone.

**Status in the sequential process:** **wired as binding design input** for the
Frontend Studio chain — consumed by `product-studio-charter.md` (DDE-065/067/068
scope + §6 sequencing), playbook §10.1 / §10.2 / §10.7, `frontend-studio-gui-spec.md`
§4.5, product-document UI law, and gap-closure §6.5 / §6.10. Phases 0–5 below do
**not** invent a parallel mission; they land inside DDE-065 → DDE-067 → DDE-068
(and optional DDE-046 reference boards).

**Disposition:** patterns-and-encodings, not package installs. Track A tools are
optional steering at best; Track B value is harvested into DDE-owned schemas, lints,
and verification seams already chartered under DDE-065 / DDE-067 / DDE-068.

**Orientation anchors:** `AGENTS.md` (Ch.9.6 dependency admission);
`docs/blueprint/REV_2_0.md` Ch.11 (AcceptanceOracle, generator/verifier independence,
Definition-of-Polished battery), Ch.13.8 (donor governance, conformance-by-construction);
`docs/planning/product-studio-charter.md`; `docs/planning/dde-frontend-ux-playbook.md`
§1.1 / §10; `docs/planning/gap-closure-record.md` §5–§6.5; `docs/truth/edr/EDR-0008-*`
(Playwright + axe); `docs/truth/edr/EDR-0016-*` (VLM critic, proposed);
`scripts/design_lints.py` (DD201–DD206 LIVE).

**Sources evaluated**

| Source | Role in this doc |
|---|---|
| `dde-design-tooling-integration-brief-1.md` (external) | Original Track A/B framing, Phase 0–5 sketch, tool table |
| Independent brief evaluation (2026-08-26) | Corrected gate ownership vs live CI; Impeccable/Vercel scope rewrite |
| Taste Skill (`Leonxlnx/taste-skill`, design-taste-frontend v2) | Concept harvest: dials, Design Read, production tell catalog |
| Vercel Web Interface Guidelines (`vercel-labs/web-interface-guidelines`) | Concept harvest: non-axe deterministic rules + `file:line` evidence shape |
| Awesome DESIGN.md (`VoltAgent/awesome-design-md`, Stitch format) | Concept harvest: art-direction document grammar; brand pack = reference only |

---

## 1. Framework (retained from the brief)

Everything researched splits into two mechanically different categories. They are not
interchangeable.

**Track A — generator-side steering.** Context/instructions loaded into the model that
produces UI (Anthropic `frontend-design`, Impeccable guidance, Taste Skill, UI/UX Pro
Max, Vercel agent-skills as prompt packs). Raises first-pass odds. **Cannot be the
oracle** — Ch.11.2: the system that generates a change must not be its only judge.

**Track B — verification-side evidence producers.** Deterministic scanners or
independent audits over *already-generated* output, bound to an `observable_outcome`
with a real `evidence_binding`, attached to mission Evidence — not merely a green CI
log. Preferred kinds: `invariant` / `test` / `visual_diff`; `judge` only when
calibrated and model-family-independent (Ch.11.2 / 11.4).

**Effort rule:** weight Track B and durable encodings (schemas, lints, authoring
refusals) far above Track A installs. Track A is largely redundant with the
product-document UI law block, playbook §1.1 nevers, and DDE-065 compile constraints.

**Evidence rule:** a CI job without an executable oracle binding and Evidence artifact
is operational hygiene, not chapter-gate closure. Wiring ahead of donor/admission
records (Ch.13.8 / Ch.9.6) is the shortcut the verification design exists to prevent.

---

## 2. Live repo baseline (evaluation corrections)

Do not re-open these as “unwired deferred gates.”

| Capability | Status TODAY | Authority |
|---|---|---|
| DD201–DD206 design lints | **LIVE** — `scripts/design_lints.py` + shrink-only `docs/design/lint-baseline.json` in dde-studio design-gates | playbook §4.5; charter §4 gate 1 |
| Token SSOT + drift | **LIVE** — `schemas/design/tokens.json` → generated `tokens.ts` | playbook §4.2 |
| Honesty / copy floor | **LIVE** — `clientHonesty.test.ts` PR-blocking | charter §4 gate 6 |
| A11y WCAG floor | **LANDED** via EDR-0008 — Playwright + `@axe-core/playwright` in dde-studio visual job (`wcag2a/aa/22aa`) | EDR-0008; charter reuse map |
| Visual Phase-B harness | **LANDED** — goldens × viewports × reduced-motion pass | charter §2 |
| DD207+ combination / slop fingerprints | **NOT IMPLEMENTED** — owned by **DDE-068** | gap-closure §6.5; charter §4 gate 2 |
| Silhouette-distinctiveness | **NOT IMPLEMENTED** — **DDE-068**; corpus licensing in EDR-0016 | charter §4 gate 3 |
| Believable-density floor | **NOT IMPLEMENTED** — **DDE-068** | charter §4 gate 4 |
| VLM rubric / pixel sign-off | **GATED** on EDR-0016 acceptance; `prototype_pixel_signoff` not yet in `APPROVAL_TYPES` | charter §4 gate 5; EDR-0016 |
| Conformance-by-construction authoring | **CHARTERED** — **DDE-067** (Ch.13.8 §4.5) | GUI spec §4.5 |
| Art-direction record + font corpus | **ADOPT-NOW** for **DDE-065** (fail-closed compile input) | gap-closure §6.5 |
| Provenance PRD→screen | **DDE-065** AC | charter §4 gate 8 |

**Implication for the original brief:** Phase 1 (“Impeccable as DD201–DD206 executor”)
and Phase 2 (“Vercel agent-skills as a11y evidence”) are **mis-aimed** against this
baseline and must not be executed as written.

---

## 3. Tool register — consolidated verdicts

Legend: **Skip** = do not install as DDE dependency or always-on generator context;
**Harvest** = encode concepts into DDE-owned artifacts; **Optional Track A** = may
load for greenfield experiments only, never as evidence.

| Tool | Track | Verdict | Notes |
|---|---|---|---|
| Anthropic `frontend-design` | A | Optional Track A | Brief claimed “already installed”; not present under `.cursor/` in this repo. Steering only. |
| Impeccable guidance layer | A | Skip by default | Overlaps UI law + DDE-065 constraints; brand-override risk. |
| Impeccable detector CLI (~59 rules) | B candidate | **Harvest / optional supplement** — **not** DD201–DD206 executor | Those gates are LIVE in-house. Candidate only for **DD207+** complementary slop rules after Phase 0 licence pin + Ch.9.6 EDR justifying why extending `design_lints.py` is worse. **Licence landmine:** monorepo `LICENSE` is Apache-2.0; npm `@impeccable/detect` has advertised **BSL-1.1** — pin the exact artifact before any `OPEN_REUSE` / CI-blocking row. |
| UI/UX Pro Max | A | Skip / evaluate-only | Unverified scale; not needed with token sheet + playbook. |
| Taste Skill (Leonxlnx) | A | **Skip install; Harvest concepts** | Excellent dials + tell catalog; stack defaults (Tailwind/Motion/Phosphor, GSAP skeletons) conflict with playbook motion law and GSAP `CONDITIONAL_REUSE`. Landing/portfolio-biased; overrides established brand. |
| Vercel `agent-skills` / `web-design-guidelines` skill | A (misclassified as B in brief) | **Skip skill as evidence; Harvest rules** | Skill fetches guidelines and asks an LLM to audit — not a deterministic scanner. Axe covers WCAG core. |
| Web Interface Guidelines (source rule list) | B material | **Harvest into lints/tests** | High-value deterministic checklist; `file:line` output shape is the Evidence format to mirror. |
| Awesome DESIGN.md brand corpus | Donor / reference | **Skip as generator input; Harvest schema** | Brand DESIGN.md files = `SOURCE_REFERENCE_ONLY` reference boards at most (Ch.13.8). Never “build like Stripe/Linear” into generated products. |
| Stitch / Awesome DESIGN.md **format** | Infra | **Harvest as art-direction grammar** | Nine-section document + YAML roles → DDE-065 art-direction record shape. |
| shadcn official skill | Infra / donor | Narrow reuse | Supports DDE-066/067 provenance of component updates under `OPEN_REUSE`; **not** Definition-of-Polished gate 8 (that is PRD→features→donors→screen via DDE-065). |
| Impeccable `/init` token scan | Infra | Reference only | May inform token-sheet authoring; **canonical SSOT remains** `schemas/design/tokens.json` — never a third-party cache. |

**None of the evaluated tools cover:** silhouette-distinctiveness against a
generic-layout corpus, or believable-density judgment. Both remain DDE-068
build-from-scratch. Do not let the DoP battery look more covered than it is.

---

## 4. Concept harvest — what improves DDE considerably

Encode these; do not install the source tools to obtain them.

### 4.1 From Taste Skill (skip package)

| Concept | Lands in | Form |
|---|---|---|
| **Three dials:** `DESIGN_VARIANCE` / `MOTION_INTENSITY` / `VISUAL_DENSITY` (1–10) | DDE-065 art-direction record | Schema fields + brief→dial inference table; compile fails closed if unset |
| **One-line Design Read** before generate | DDE-065 compile ritual | Required provenance field on compiled prompt (page kind × audience × language × foundation) |
| **Production-tested tell catalog** (em-dash ban; scroll cues; version/section-number eyebrows; zigzag ≥3; split-header; beige+brass premium default ban; Fraunces / Instrument Serif as default display ban; decoration text strips) | DDE-068 DD207+ + copy/honesty gates | Extend playbook §1.1 + `design_lints.py` / honesty regexes |
| **Color consistency lock** (one accent, whole surface) | DD207+ combination lint | Static scan: unrelated accent families in one surface = fail |
| **Motion claimed = motion shown** + motivated-motion | DDE-068 motion gate | If motion-identity band > static, assert real motion specs + reduced-motion degradation |
| Pre-flight checklist (mechanically checkable subset only) | DDE-068 + prototype validator | Taste judgments stay VLM/human |
| Official design-system map when brief reads as known DS | DDE-066 donor taxonomy | Route to Ch.13.8 class; never auto-install into DDE Core |
| Audit-first redesign (infer existing dials, preserve) | Frontend Studio redesign path | Mission mode: measure before overhaul |

### 4.2 From Web Interface Guidelines (skip skill-as-evidence)

| Concept | Lands in | Form |
|---|---|---|
| **`file:line` terse finding format** | All design Evidence producers | Standard shape for lint/audit → Evidence artifact refs |
| **Non-axe deterministic rules** | `design_lints.py` + studio tests | Ban `transition: all`; `outline-none` without `:focus-visible` replacement; compositor-only `transform`/`opacity`; `tabular-nums` for numeric columns; flex `min-w-0` + truncate; explicit `img` width/height; modal `overscroll-behavior: contain`; `color-scheme` on root; `touch-action: manipulation`; `env(safe-area-inset-*)` |
| **URL reflects UI state** / deep-link stateful panels | Generated-product UI law + contract tests | Filters/tabs/expanded panels in query params |
| Forms: never block paste; `autocomplete`/`name`; focus first error | Generated-product a11y floor | Beyond axe |
| Copy micro-rules (ellipsis, curly quotes, specific CTAs, active voice) | DDE-067 copy-specificity gate | Extend `FORBIDDEN_HELPER` / honesty suite |

### 4.3 From Awesome DESIGN.md / Stitch format (skip brand pack as generator input)

| Concept | Lands in | Form |
|---|---|---|
| **Nine-section DESIGN.md grammar** | DDE-065 art-direction record | Theme & atmosphere; color palette **with roles**; typography hierarchy; component stylings **with states**; layout principles; depth & elevation; dos/donts; responsive behavior; agent prompt guide |
| **YAML tokens + markdown rationale** | Same record | Machine-readable for compiler; human-readable for Studio |
| Semantic color roles (canvas / surface / ink / accent / semantic-*) | `tokens.json` + art-direction | Roles required, not bare hex lists |
| Component tables require interactive states | States-completeness law / DDE-067 | Authoring shape in Studio |
| `preview.html` catalog pattern | Prototype Gallery | Emit preview from **product’s own** sheet after compile |
| Brand DESIGN.md corpus | DDE-046 reference boards (optional) | `SOURCE_REFERENCE_ONLY`; §14.5 injection-screened; human art-direction only |

---

## 5. Architecture additions (governance — retained, corrected)

### 5.1 Donor register (Ch.13.8 / `donor_artifact`)

Add a row **before** any code references a third-party tool or corpus. Draft shape:

```yaml
- source_uri: <exact repo or package URI>
  source_class: OPEN_REUSE | CONDITIONAL_REUSE | SOURCE_REFERENCE_ONLY | REJECTED
  media_kind: source_tree | guideline_corpus | skill_pack
  license: <SPDX from LICENSE file of the pinned artifact>
  maintenance_signal: <verified, not blog star counts>
  checked_at: <ISO date>
  intended_use: <one sentence; e.g. "DD207+ rule reference only" or "art-direction schema prior">
```

**Classification defaults for this workstream**

| Artifact | Default class until proven otherwise |
|---|---|
| In-house `design_lints.py` extensions | N/A (first-party) |
| Web Interface Guidelines markdown (rules as reference) | `SOURCE_REFERENCE_ONLY` until rules are re-expressed as first-party lints |
| Taste Skill / Vercel agent-skills installs | Prefer **no ingest**; if cited, `SOURCE_REFERENCE_ONLY` |
| Awesome brand DESIGN.md files | `SOURCE_REFERENCE_ONLY` |
| Impeccable detector (if admitted to CI) | Licence-pin first; Apache-2.0 path may be `OPEN_REUSE`; BSL-1.1 path is likely `CONDITIONAL_REUSE` / non-CI until legal read |

### 5.2 Ch.9.6 admission (merge-blocking dependencies only)

Any tool wired as a **CI-blocking** or runtime dependency needs the AGENTS.md triple:
licence, maintenance signal, why building the equivalent in-house is worse. Missing
justification → `REJECTED` by fail-closed rule. **Do not** file admission for optional
Track A skills that never enter the dependency graph.

### 5.3 Evidence binding (Section 4 / AcceptanceOracle)

Each DoP sub-check that becomes machine-decidable gets an `observable_outcome` with a
real binding. Prefer extending first-party executors (`design_lints.py`, studio tests,
Phase-B visual harness) so `kind: invariant` / `test` / `visual_diff` stay honest.

```yaml
- outcome_id: <uuidv7>
  acceptance_condition_ref: AC-<slug>-N
  statement: "generated screen produces zero DD207+ combination-lint violations"
  evidence_binding:
    kind: invariant
    ref: design-lints-dd207
    command: ["python", "scripts/design_lints.py", "--rules", "DD207+"]
    independence: "static rule scan; not the generating model"
```

For any LLM judge (VLM rubric, or a third-party `/critique` repurposed as check):
`independence` MUST name a **different model family** than the generator; uncalibrated
judges cannot bind (Ch.11.2). EDR-0016 gates VLM start.

**Runner seam:** binding JSON alone is not closure — the verification runner must
execute the kind and attach Evidence. Charter already owns visual/judge executor work
under DDE-068.

### 5.4 Authoring surface (DDE-067 / Ch.13.8 conformance-by-construction)

- Valid value sets come from the **project token sheet** (and art-direction record),
  not from Impeccable init caches or brand DESIGN.md packs.
- Live-edit refuses out-of-set color/font/spacing/duration/easing at the authoring
  boundary — unrepresentable, not “lint later.”
- shadcn skill behavior may inform non-destructive component update UX; provenance
  gate 8 remains DDE-065’s PRD chain.

---

## 6. Phased plan (corrected)

Ordered so nothing becomes trusted evidence before governance and ownership align.
Phases map onto **existing missions**, not a parallel integration chain.

### Phase 0 — Governance intake (before any new CI-blocking third party)

- [ ] **T0.1** Decide per candidate: first-party encode vs third-party CI. Default =
  first-party encode (this doc’s disposition).
- [ ] **T0.2** If Impeccable detector remains a candidate for DD207+ supplement: verify
  SPDX on the **exact** package/CLI CI would invoke (Apache-2.0 vs BSL-1.1); set
  `checked_at`; draft donor row.
- [ ] **T0.3** Ch.9.6 admission draft only for artifacts that would become merge-blocking
  dependencies (licence, maintenance, stdlib-insufficiency). Skip for markdown corpora
  re-expressed as first-party rules.
- [ ] **T0.4** Donor rows for any Awesome DESIGN.md entries used as human reference
  boards (`SOURCE_REFERENCE_ONLY`).
- [ ] **Acceptance:** no new third-party design tool in CI or `package.json` without
  donor row + (if blocking) accepted admission/EDR.

### Phase 1 — Art-direction record = DESIGN.md grammar + Taste dials (**DDE-065**)

Replaces the brief’s “wire Impeccable for DD201–DD206.”

- [ ] **T1.1** Extend `schemas/design/` with art-direction record: three dials;
  Design Read string; semantic palette roles; type hierarchy; layout idiom; motion
  identity; dos/donts; responsive notes (Stitch/Awesome section grammar).
- [ ] **T1.2** Font-pairing corpus with licence metadata; ban Inter-as-default-display
  per gap-closure §6.5 (allow Inter only when art-direction explicitly selects it).
- [ ] **T1.3** DDE-065 compiler fail-closed until art-direction + tokens pin resolve;
  embed dials + nevers into compiled prompt; byte-stable output; provenance chain.
- [ ] **T1.4** Emit optional preview catalog page from the product’s own sheet (gallery
  pattern), not from a third-party DESIGN.md.
- [ ] **Acceptance:** missing art-direction → typed refusal; identical inputs →
  identical prompt hash; prompt cannot instruct off-token literals (contract scan).

### Phase 2 — Expand deterministic gates (**DDE-068** lint layer; keep axe)

Replaces the brief’s “Vercel agent-skills as DD207 / a11y executor.”

- [ ] **T2.1** Implement DD207+ combination / fingerprint lints in
  `scripts/design_lints.py` (Inter-only + indigo fingerprint, pill-spam, etc. per
  playbook §10.2) **plus** harvested Taste §9 tells that are statically decidable.
- [ ] **T2.2** Port Web Interface Guidelines **non-axe** rules into studio / design
  lints with `file:line` findings; fail closed.
- [ ] **T2.3** Color consistency lock + selected copy micro-rules in honesty / lint
  suite.
- [ ] **T2.4** Optional only: evaluate Impeccable detect as **supplemental** DD207+
  rules after Phase 0 licence pin + Ch.9.6 “why not first-party” justification.
  Default remains first-party.
- [ ] **T2.5** Wire outcomes into oracle bindings / Evidence via DDE-068 executor seam
  (not CI-log-only).
- [ ] **Acceptance:** injected combination-slop fails; clean screen passes; axe path
  unchanged; findings retrievable as Evidence.

### Phase 3 — Conformance-by-construction authoring (**DDE-067**)

Unchanged intent from the brief; ownership explicit.

- [ ] **T3.1** Token-sheet (+ art-direction) → valid-value-set generator per target.
- [ ] **T3.2** Frontend Studio live-edit resolves only against that set; hard refuse
  freehand literals with nearest-token message (copy-honesty tone).
- [ ] **T3.3** Confirm refusal is a boundary, not an ignorable warning.
- [ ] **Acceptance:** raw hex/px/duration cannot reach the renderer.

### Phase 4 — Remaining DoP gates (build; no off-the-shelf substitute) (**DDE-068**)

- [ ] **T4.1** Silhouette-distinctiveness vs generic-layout corpus (licence-clean;
      EDR-0016 open item).
- [ ] **T4.2** Believable-density floor as blocking runner check.
- [ ] **T4.3** VLM rubric judge after **EDR-0016 acceptance**; independence +
      calibration; human `prototype_pixel_signoff` via ordinary contract path.
- [ ] **T4.4** Per-interaction motion specs + reduced-motion degradation assertions
      (motion claimed = motion shown).
- [ ] **Acceptance:** failing silhouette/density/VLM cannot merge; revise ≤3 then human.

### Phase 5 — Close the loop (docs / template hygiene)

- [ ] **T5.1** Worked donor-row example in product-document template Section 5 (or
  LedgerLine companion) for one harvested reference corpus end-to-end.
- [ ] **T5.2** Completeness self-check: any tool promoted past Phase 0 names
  `dependency_addition` (and `donor_reuse` where applicable) in predicted approvals.
- [ ] **T5.3** Append playbook §1.1 / §10 with the harvested tell list and DESIGN.md
  grammar pointer (this file as normative planning source).
- [ ] **Acceptance:** future authors do not invent donor rows from scratch; chapter
  gate can name production call sites for each DoP item or a deferred EDR.

---

## 7. Explicit non-goals

- Not replacing DDE-065 with any third-party generator or skill.
- Not installing Taste Skill, Vercel `web-design-guidelines` skill, or UI/UX Pro Max
  as always-on / merge-blocking context for DDE Core or branded generated products.
- Not treating Track A steering (or LLM audits of WIG) as `kind: invariant` evidence.
- Not using Awesome brand DESIGN.md packs as generator input (“look like Linear”).
- Not importing Taste’s Motion / GSAP / Phosphor / Tailwind-default stack into DDE or
  generated-product defaults without separate Ch.9.6 / Ch.13.8 decisions.
- Not re-implementing DD201–DD206 via Impeccable; not dual-binding axe and an LLM
  a11y skill as the same outcome.
- Not skipping Phase 0 for any third-party CI-blocking tool.
- Not starting DDE-068 VLM implementation before EDR-0016 acceptance.
- Not inventing a parallel “design-tooling mission” that bypasses DDE-065/067/068
  chapter gates.

---

## 8. Mission ownership map

| Work | Owner | Gate |
|---|---|---|
| Art-direction schema + dials + DESIGN.md grammar + compiler | **DDE-065** | Fail-closed compile; provenance |
| Authoring refusals + copy-specificity + Studio surface | **DDE-067** | Ch.13.8 conformance-by-construction |
| DD207+, WIG non-axe lints, silhouette, density, VLM, motion claims | **DDE-068** | DoP battery; EDR-0016 for VLM |
| Donor discovery / reference-board ingest | **DDE-066** / **DDE-046** | Ch.13.8; EDR-0015 for egress |
| Playwright + axe toolchain | **EDR-0008** (accepted; landed) | Visual job |
| Optional Impeccable CI supplement | Only after Phase 0 + new/amended EDR | Must not displace first-party DD201–206 |

Standing rule (gap-closure §6.5): until DDE-068 lands gates 2–4, existing-surface floor
stays DD201–DD206 + honesty; no generated product may claim DoP compliance it cannot
demonstrate.

---

## 9. Acceptance criteria for “this integration is done”

This planning integration is **complete as a document** when recorded in
`gap-closure-record.md` and consumed at charter time. Implementation is **not** done
by publishing this file.

Implementation-level “done” (for a future chapter-gate):

1. Art-direction record schema exists; DDE-065 refuses without it.
2. DD207+ and harvested deterministic tells/WIG non-axe rules run fail-closed with
   Evidence, not CI-log-only.
3. DDE-067 authoring boundary refuses freehand literals.
4. Silhouette, density, VLM (or explicit pixel sign-off) are either wired at a
   production mutation/verification call site or explicitly deferred with named EDR.
5. No third-party design skill is the sole judge of generated UI.
6. Every adopted third-party artifact (if any) has donor classification + Ch.9.6
   admission where it enters the dependency graph.

---

## 10. Source-quality caveats

- Star/install counts for Taste Skill, Impeccable, and listicle write-ups are
  **untrusted** for maintenance signal — verify commit cadence, releases, and LICENSE
  on the pinned artifact.
- Taste Skill v2 is marked experimental; rule wording may change — another reason to
  **encode** dials/tells rather than pin the skill.
- Awesome DESIGN.md files are analyses of public CSS, not licences to reproduce brand
  identity.
- Web Interface Guidelines evolve at the upstream URL the skill fetches; first-party
  ports must version the rule subset DDE enforces.

---

## 11. One-sentence summary

**Keep the brief’s Track A/B law and Phase 0 discipline; discard Phase 1–2 as written;
encode Taste dials + DESIGN.md grammar into DDE-065, Taste tells + WIG non-axe rules
into DDE-068 lints, and conformance-by-construction into DDE-067 — without installing
the third-party skills as oracles.**
