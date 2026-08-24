# DDE — Frontend & UX/UI Design Playbook: Guardrails, Prototypes, Skills & Tools

**Version:** 1.2 (v1.2 2026-08-24: §10 distinctiveness adoption plan — six-stream anti-generic-output research integrated; art-direction record, combination lints DD207+, silhouette test, copy-specificity gate, template-sourcing law mapped to Ch.13.8 licence classes, motion-identity token layer; staged landing plan in gap-closure-record §6.5. v1.1 operationalized 2026-08-22: tokens SSOT + drift gate, design lints DD201–DD206, binding rule file, six skills, provenance ledger, Prototype Gallery, prototype-manifest verification sweep, design-gate CI; Phase 1 visual-gate toolchain admitted by **EDR-0008 ACCEPTED** — implementation in flight)
**Date:** 22 August 2026
**1.1 changelog:** Cocodly loop-shape ports folded in — pre-generation plan checkpoint (P1, §5.0/§5.1), live-streaming prototype gallery (P2, §5.3/§7.6), refine-in-place protocol (P3, §5.6), believable-density scorecard line (P4, §8.3). Process/engineering layers only per §2; no Cocodly values, layouts, or copy.
**1.1.1 changelog:** EDR-0008 (Playwright + `@axe-core/playwright` admission for the Phase 1 visual gates) **ACCEPTED 2026-08-22** by owner decision; §4.4 Phase B and §4.9's axe scan move from *post-EDR* to *admitted, implementation in flight*. Landed Phase-0 items marked operational: token SSOT pipeline + drift gate, static design lints with committed shrink-only baseline, studio client tests PR-blocking, prototype-manifest sweep wired into the verification runner, live Prototype Gallery.
**Purpose:** One operational document for producing clean, modern, professional DDE surfaces — and for *seeing* them (screens, flows, animations) during development, not after. Adapted from the Farm OS frontend playbook to DDE's actual stack: **string-rendered HTML webviews + plain CSS variables, no framework, no build-time CSS pipeline** (VS Code extension + Electron shell).
**Reads with:** `AGENTS.md` (authority ranks, dependency admission) · `.cursor/rules/mission-chapter-gate.mdc` ("CI green ≠ done") · `docs/planning/gap-closure-record.md` · `interfaces/dde-studio/docs/overview-mockup-alignment.md`.
**Binding on:** all humans and agents producing UI code, prototype artifacts, copy, or reviews for DDE surfaces (`interfaces/**` today; any future web frontend inherits this document unless superseded by an EDR).

---

## Contents

| § | Title |
|---|-------|
| 1 | Why DDE UIs go generic — the five root causes |
| 2 | The repo-mining protocol (copying safely) |
| 3 | Licence hygiene for reference repos |
| 4 | Guardrails — the complete list |
| 5 | Visual samples & living prototypes during development |
| 5.0 | Cocodly loop-shape ports (P1–P4) |
| 6 | Agent skills (loadable playbooks) |
| 7 | Toolchain catalog |
| 8 | Quality scorecards & thresholds |
| 9 | Gate-ready acceptance checklist |
| 10 | Distinctiveness adoption plan (2026-08-24 research integration) |
| 11 | Traceability |

**Enforcement-point legend used throughout:** ⚙ = GitHub Actions job · ◆ = pytest / `node --test` check · ▣ = schema contract (`schemas/` + `scripts/generate_contracts.py`) · § = binding rule file (`.cursor/rules/*.mdc`) · ✋ = human/manual gate.

---

## 1. Why DDE UIs go generic — the five root causes

Community research is unambiguous about *why* AI-built frontends converge on the same look: models optimize for the statistical centre of their training corpus, which in 2024–2026 is Tailwind/shadcn defaults inside B2B-SaaS layouts ([rottoways](https://rottoways.com/blog/ai-generated-website-looks-generic), [tasteprofile](https://tasteprofile.io/blog/why-ai-generated-ui-looks-generic), [prg.sh](https://prg.sh/ramblings/Why-Your-AI-Keeps-Building-the-Same-Purple-Gradient-Website)). Named tells recur across independent catalogs: purple-to-indigo gradients, Inter-as-only-typeface, three identical feature cards, emoji as icons, pill-spam badges, centered-hero-plus-badge skeletons, colored left-border cards, glassmorphism, terminal mockups with traffic-light dots ([uxskill slop](https://uxskill.laithjunaidy.com/what-is-ai-slop.html), [Sailop guide](https://sailop.com/blog/ai-slop-definitive-guide-2026), [Fountain Institute](https://www.thefountaininstitute.com/blog/signs-vibe-coded-ui), [Developers Digest 16-pattern](https://www.developersdigest.tech/blog/ai-design-slop-and-how-to-spot-it), [35 fingerprints](https://uxskill.laithjunaidy.com/blog/ai-design-fingerprints-list.html), [Unslop UI](https://www.claudecodehq.com/playbooks/unslop-ui)). The countermeasure class is always the same: **explicit constraints supplied before generation** — tokens, nevers, rubrics, and mechanical gates ([SeedFlip](https://seedflip.co/blog/cursorrules-design-output), [Anthropic frontend-design skill](https://github.com/anthropics/claude-plugins-official/blob/b392f51899343f35a203260a4b344803de236d13/plugins/frontend-design/skills/frontend-design/SKILL.md)).

DDE has the same failure modes with two local twists: its UI is *generated HTML strings* (so visual errors are invisible until a human opens a webview), and its honesty law forbids fabricated data (so screens are dominated by *empty states* — the easiest surface of all to leave generic).

| # | Root cause | DDE mechanism | Countermeasure (§) |
|---|---|---|---|
| R1 | **Blind authoring** | Webview HTML/CSS live in TS template strings (`shared/ui/*.ts`); agents edit them without ever rendering pixels; breakage surfaces only at runtime in VS Code/Electron | Gallery-first + prototype pipeline (5) + screenshot/fingerprint gates (4.4–4.5) |
| R2 | **Average-pull** | No constraint file tells the agent what DDE looks like, so it regresses to the training-corpus mean aesthetic | Binding rule file with explicit nevers (4.1), anti-tell catalog (1.1), fresh-context critique (4.7) |
| R3 | **Token bypass** | `sharedStyles()` `:root` block (`base.ts`) is the de-facto token sheet, but raw hex/px can be inlined anywhere in any `*.ts` string with nothing noticing | Token single-source + drift check (4.2), static design lints (4.5) |
| R4 | **Placeholder feel / dishonest density** | Empty states dominate early surfaces; generic "Nothing here yet" copy and dead chrome read as unfinished even when honesty law is satisfied | Empty-state composition law (4.10), copy-voice gate extending `FORBIDDEN_HELPER` (4.6) |
| R5 | **Silent drift** | Closed 2026-08-22 (`5f31142`): dde-studio.yml now runs the client suite PR-blocking, and the token drift gate + static design lints catch each deviation mechanically; the debt budget (4.14) trends whatever remains | Studio CI runs the suite (4.3), debt budget (4.14), scorecards (8) |

### 1.1 DDE anti-tell catalog (the nevers)

Banned from any committed DDE surface, because each is a documented AI-corpus tell: gradient fills as primary device (multi-stop `linear-gradient` decoration); purple/indigo accent defaults; emoji as icons, bullets, or nav items; identical repeated card grids with icon-over-heading skeleton; pill-spam badge rows; glassmorphism/backdrop-blur chrome; terminal mockups with three traffic-light dots; centered-marketing hero grammar inside operator tooling; pure `#fff`/`#000` text pairs; decorative charts or sparklines presenting no real data (also violates honesty law); instructional essays in empty states (already enforced by `clientHonesty.test.ts`). Icons come from the inline monochrome stroke SVG set in `overview.ts` (`ICONS`) or none at all — one silhouette family, sized consistently ([Fountain Institute](https://www.thefountaininstitute.com/blog/signs-vibe-coded-ui), [Sailop report](https://sailop.com/blog/ai-slop-2026-state-of-the-ai-generated-web)).

---

## 2. The repo-mining protocol (copying safely)

Consulting repositories — including external AI generators (v0/Lovable/Bolt output treated as *mined material*, never as paste-ready code; [ShipSet](https://shipset.app/blog/best-ai-builder-for-pms), [ToolChase](https://toolchase.com/blog/v0-vs-lovable-vs-bolt/)) — is encouraged for the right layers, with provenance. What is forbidden is unscoped consultation where visual patterns ride along with engineering ones.

### 2.1 Layer extraction table (web-stack edition)

| Layer | May copy/mine? | Form allowed | Examples |
|---|---|---|---|
| Test-harness patterns (string fingerprints, honesty regex lists, screenshot harness structure) | Yes | Code/pattern, cited | `overviewVisual.test.ts`-style fingerprints; Playwright baseline workflows ([Playwright docs](https://playwright.dev/docs/test-snapshots)) |
| Gallery/workshop *structure* (index page, per-state entries, naming scheme) | Yes | Pattern, cited | Storybook/Ladle story organization ([Ladle](https://ladle.dev/blog/introducing-ladle/)) |
| Schema/manifest validation patterns (flows manifests, drift checks) | Yes | Pattern, cited | Contract-drift CI ([schemadiff pattern](https://medium.com/@duckweave/tool-schema-drift-11-checks-before-agents-guess-6038c1748309)) |
| Component/API discipline (pinning, wrapper-layer separation) | Yes | Pattern only, cited | Three-layer primitives/wrappers/app pattern ([TheCodeForge](https://thecodeforge.io/javascript/reusable-component-library-shadcn-ui/)); headless accessibility-first split ([Headless UI](https://tailwindcss.com/blog/headless-ui-unstyled-accessible-ui-components)) |
| CSS technique (reduced-motion cascade, focus-visible, container collapse) | Yes | Code, cited, token-conformant | Two-layer reduce-motion reset ([css-animation.com](https://www.css-animation.com/accessible-motion-architecture/prefers-reduced-motion-architecture/)) |
| Theme *code structure* (where variables live, light/dark alias switching) | Yes | Structure only | Alias-remapping architecture ([orchestkit tokens rules](https://github.com/yonatangross/orchestkit/blob/main/plugins/ork/skills/design-system-tokens/rules/tokens-theming-darkmode.md)) |
| Theme *values* (colors, type scale, radii, shadows, easing curves) | **No** | Never | Any palette/type/motion values from any repo |
| Screen layouts, information architecture, navigation graphs | **No** | Never | Any dashboard/composition |
| Motion specs (specific keyframes, choreography, springs) | **No** | Never | Any transition design |
| Microcopy & product vocabulary | **No** | Never | Any user-facing string; DDE vocabulary is manufacturing-domain exact (Truth, Evidence, Gates, leases) |

### 2.2 Provenance rule

Every PR that mines a repo must carry a `References:` footer citing `repo@commit/path` per extracted item and the layer mined (per 2.1). A cumulative **provenance ledger** lives at `docs/design/provenance-ledger.md` *(landed 2026-08-22, commit `f54313f`)* — append-only, one row per extraction. Reviewers reject unclosed borrowings; the ui-review skill (6.3) checks the footer.

### 2.3 Adaptation requirement

Copied engineering code is renamed to DDE conventions and passes repo lints before merge; verbatim vendored blocks are prohibited except behind `adapters/**`. If more than ~40% of a copied file survives unchanged, justify it in the PR body or split the extraction. External-generator output (v0 et al.) counts as mined material: it must be re-expressed through the DDE token sheet and re-reviewed; direct paste is a licence-and-provenance violation even when the tool's ToS permits it.

---

## 3. Licence hygiene for reference repos

Licence check happens **before** reading code deeply, and is recorded in the provenance ledger row. GPL contamination discovered late forces a rewrite of every touched file — prevention is cheap, cure is not.

| Licence | Code reuse | Ideas/patterns | DDE stance |
|---|---|---|---|
| MIT (shadcn/ui, Radix docs/examples, Ladle) | Allowed with attribution | Allowed | Fine |
| Apache-2.0 (Playwright, Storybook, Style Dictionary, Headless UI) | Allowed with attribution + NOTICE entry if vendored | Allowed | Preferred mining/tool source |
| MPL-2.0 (axe-core) | File-level copyleft: allowed; modified MPL files stay MPL | Allowed | Fine as dependency; do not inline-modify |
| GPL/LGPL/AGPL | **Contaminating — never copy into DDE** | Ideas only | Mine visually; zero code transfer |
| Unlicensed / "other" | Treat as All Rights Reserved | Ask owner first | Do not mine until cleared |

New *dependencies* additionally pass the AGENTS.md admission bar: licence, maintenance signal, and why the stdlib/existing toolchain is insufficient (Chapter 9.6), recorded as an EDR (guardrail 4.13). This playbook's own recommendations respect that bar: every proposed tool is either already in the repo, Node/Python stdlib, or flagged for EDR before adoption (§7).

---

## 4. Guardrails — the complete list

Each guardrail names its production enforcement point in *this* repo. Per the chapter-gate rule, a guardrail without a wired call site is **deferred**, never "implicitly handled."

1. **Visual-authority split** §✋ — the mockup (`interfaces/dde-studio/docs/dde-mission-overview-mockup.png`), the token sheet (4.2), and this playbook are the only visual authorities; repos are engineering references. An agent needing a layout decision cites a declared pattern (11), never a repo screen. Enforced by the binding rule file (`.cursor/rules/dde-design-guardrails.mdc`, landed 2026-08-22, commit `f54313f`) and ui-review checklist.
2. **Token single-source + drift check** ⚙◆▣ — **landed 2026-08-22 (commit `58015fb`)**: `schemas/design/tokens.json` pins the token sheet; `scripts/generate_contracts.py` emits `interfaces/dde-studio/shared/ui/tokens.ts` (typed constants + the CSS `:root` string). `base.ts` consumes the generated export; hand-edits to generated files fail the existing **"Fail on generated drift"** step in `.github/workflows/ci.yml`. This is Style Dictionary's SSOT/codegen/drift pattern ([devcheolu](https://devcheolu.com/en/posts/0sa4JzPKHIoeWmwdx6Am), [jdp.work](https://jdp.work/design-tokens-architecture/), [Lenka](https://lenkastudio.com/blog/how-to-build-design-tokens-pipeline-figma-to-code)) implemented with the repo's existing generator instead of a new dependency. Semantic-alias structure (surface/text/accent per mode, dark mode as alias remapping — never inversion) follows OKLCH-era three-tier practice ([carmenansio](https://www.carmenansio.com/articles/oklch-and-the-modern-color-stack/), [atelier recipes](https://github.com/IamK77/Skill/blob/main/skills/atelier/color/references/oklch-palette-recipes.md)).
3. **Studio CI runs the client suite** ⚙ — **landed 2026-08-22 (commit `5f31142`)**: `.github/workflows/dde-studio.yml` runs the client suite (`npm test` → `node --test out/shared/*.test.js`) after `compile` and is PR-blocking, closing the R5 hole where the workflow stopped at typecheck. `just studio-check` mirrors it locally.
4. **Screenshot-evidence gate** ⚙◆ *(phased)* — Germ exists: `overviewVisual.test.ts` asserts a structural + style-token fingerprint. Phase A (no new dependency, **landed**): extend fingerprints to every shipped surface (connection, mission-control, panels, morning review) — zones, key classes, tone classes per probe state. Phase B (toolchain admitted by **EDR-0008, ACCEPTED 2026-08-22; implementation in flight — not yet wired**): Playwright `expect(page).toHaveScreenshot()` goldens over the Prototype Gallery pages — light/dark/high-contrast × reduced-motion on/off × widths 320/900/1280 — with `maxDiffPixels` budgets per element class, baselines generated in the CI container, updated only in the owning PR, never in CI ([Playwright snapshots](https://playwright.dev/docs/test-snapshots), [threshold tuning](https://web-automations.com/debugging-and-test-observability/visual-regression-testing/tuning-screenshot-comparison-thresholds/), [Grabbit](https://www.grabbit.live/blog/playwright-visual-regression-testing), [QAPractices](https://qapractices.com/documentation/playwright-visual-regression-testing/), [testdino skill](https://github.com/testdino-hq/playwright-skill/blob/main/core/visual-regression.md)). Diff = red build. Tests green ≠ UI done.
5. **Static design lints** ◆ — **landed 2026-08-22 (commit `d03d415`, DD201–DD206)**: `tests/unit/test_studio_design_lints.py` scans `interfaces/dde-studio/shared/**/*.ts` and fails on: raw hex/rgb outside the generated tokens module (Discourse ships exactly this rule for CSS; here CSS lives in TS strings, so a stdlib scanner is the honest port — [stylelint strict-value](https://www.npmjs.com/package/stylelint-declaration-strict-value), [CSS Architecture](https://www.css-architecture.com/token-scaling-validation-ci-pipelines/stylelint-plugin-configuration/)); `linear-gradient(`/`radial-gradient(` without an allowlisted exception; emoji ranges in UI strings; `font-family:` literals other than the token reference; raw `ms`/`s` durations and `cubic-bezier(` literals outside the tokens module (motion law, 5.5); `backdrop-filter`. Zero dependencies; runs in the normal `pytest tests/unit` leg of CI.
6. **Copy honesty & voice gate** ◆ — `clientHonesty.test.ts`'s `FORBIDDEN_HELPER` list becomes the codified copy law, extended with community-documented AI-tell phrases: "simply", "easily", "just", "Welcome to", exclamation marks, marketing superlatives, emoji. Buttons verb-first ("Start local Core"), sentence case everywhere, error banners state cause + next action, figures not words. Runs in the studio suite (4.3).
7. **Fresh-context critique** ✋§ — a reviewer agent with no authorship stake reviews changed surfaces **from rendered pixels** (gallery screenshots or prototype pages), scores them against the §8 screen scorecard, walks the anti-tell catalog (1.1), and verifies states matrix + copy voice. Any dimension <4 blocks merge. This is the UI twin of the chapter-gate's independent verification; the deterministic harness + pluggable-critic pattern is established practice ([visual-review harness](https://github.com/gosha70/code-copilot-team/blob/master/adapters/github-copilot/.github/instructions/visual-review.instructions.md), [design-review skill](https://github.com/humbleteam/design-review/blob/refs/heads/main/SKILL.md)).
8. **Interaction-state completeness** ◆✋ — every interactive surface declares idle/loading/empty/error/disabled (the `ProbeState` union in `base.ts` is the seed vocabulary). Bare happy-path-only lists fail review; fingerprint tests assert the presence of state containers (`ov-empty`, banner tones) per surface.
9. **Accessibility floor** ⚙✋ — Now: skip-link, `:focus-visible` rings, `aria-label`s, and `role="status"` regions stay asserted in client tests (already present in `base.ts`/tests — do not regress). After 4.4-Phase-B (toolchain admitted by **EDR-0008, ACCEPTED 2026-08-22; implementation in flight — not yet wired**): `@axe-core/playwright` scans gallery pages with tags `wcag2a, wcag2aa, wcag22aa`, zero critical/serious violations, non-zero exit blocks the PR; target-size (SC 2.5.8, 24×24px minimum; DDE standard 28px buttons today) included ([MFA11y gating](https://modern-framework-accessibility.com/testing-and-automating-accessibility/gating-accessibility-in-ci-cd-pipelines/), [failing PRs on axe violations](https://modern-framework-accessibility.com/testing-and-automating-accessibility/gating-accessibility-in-ci-cd-pipelines/failing-pull-requests-on-axe-violations/), [A11yFlow](https://www.a11yflow.dev/blog/accessibility-testing-github-actions), [QASkills a11y 2026](https://qaskills.sh/blog/ai-accessibility-testing-tools-2026)). Manual keyboard walk (Tab order, focus trap in dialogs, Escape closes) stays a checklist item.
10. **Empty-state composition law** ◆✋ — honesty means *truthful*, not *barren*: an empty zone ships icon (from the shared stroke set) + one-line factual title ("No active missions"), zero instructional essays, zero fabricated rows (already enforced). Composition (spacing, alignment, muted tone) is reviewed like any other screen; a dashed-border box with lorem-grade copy is a review blocker.
11. **One-surface-one-pattern audit** ✋ — every shipped surface maps to exactly one declared layout pattern (dashboard `ov-*` grid; mission-control columnar shell; status/form panels; settings form). Orphan layouts are chapter-gate blockers and EDR candidates.
12. **Theme-triad usability** ◆✋ — surfaces must remain usable under `body.vscode-light`, `vscode-dark`, and `vscode-high-contrast` (VS Code sets these classes on webview bodies — [Webview API](https://code.visualstudio.com/api/extension-guides/webview)). The token sheet defines semantic aliases per mode; components reference aliases only. All `var(--vscode-*)` reads carry literal fallbacks — null-default tokens resolve to nothing in some themes, a documented cross-editor pitfall ([Cursor forum analysis](https://forum.cursor.com/t/extension-webviews-dont-receive-vscode-theme-css-variables-themed-extension-ui-breaks-e-g-claude-code-panel/165601)). Contrast pairs meet WCAG AA (≥4.5:1 text, ≥3:1 large/UI) at design time in the token sheet ([OKLCH blueprint](https://dev.to/okabrionz/universal-oklch-color-system-blueprint-one-base-color-design-tokens-3639)).
13. **UI-dependency admission** ✑✋ — any new UI dependency (Playwright, axe wrapper packages, icon sets, webfonts) requires an EDR in `docs/truth/edr/` stating licence, maintenance signal, and why the existing toolchain is insufficient. Rejected-by-default list with reasons lives in §7. Mirrors AGENTS.md Chapter 9.6.
14. **Aesthetic-debt budget** ◆ — lint-violation count (4.5) per surface is reported in the mission record; a rising trend freezes new feature UI on that surface until zero, mirroring Farm OS debt trending.
15. **Provenance closure** ✋ — no merge with an unclosed mining borrowing: `References:` footer + ledger row (2.2) verified by the ui-reviewer.
16. **Prototype-before-implement gate** ▣⚙✋ — UI missions produce `prototypes/` artifacts (§5) validated against schema, with owner pixel-approval recorded through the approvals surface **before** the implementation PR merges. Auto-resume honors PASS / PASS-WITH-EDR per the standing chapter-gate rule; FAIL freezes progression. Details in §5.4.
17. **Motion restraint** ◆✋ — durations/easings only from the token sheet; no autoplaying loops beyond a bounded duration; `prefers-reduced-motion` variant mandatory per animated state (law in 5.5).
18. **Density & viewport matrix** ◆ — surfaces are asserted at sidebar-panel width (~320px, the activity-bar reality) and editor-width (~900–1280px); the `@media (max-width: 960px)` single-column collapse is part of the fingerprint set, not an accident.

---

## 5. Visual samples & living prototypes during development

### 5.0 Cocodly loop-shape ports (P1–P4)

Cocodly's finished-feeling output is driven by loop shape, not aesthetics: a visible plan before generation, pixels within seconds of starting, and many small in-place refinements instead of one-shot deliveries ([cocodly.com](https://www.cocodly.com/), [about](https://www.cocodly.com/about), [docs](https://www.cocodly.com/docs)). DDE ports the **process/engineering layers only** (§2.1): no Cocodly theme values, layouts, motion specs, or copy — those are never-minable rows. Four ports; each names its enforcement point.

**P1 — Pre-generation UI plan checkpoint (§✋).** Before authoring any prototype set, the worker publishes the intended screens × states manifest as *text* through the existing mission-plan/approval surface for owner comment; owner edits at this stage cost minutes, not re-authored pages. Blocking only when the mission charter declares `ui_plan_checkpoint: required` (default: advisory comment window); the checkpoint artifact is the same manifest shape later validated by §7.7.

**P2 — Live-streaming prototype gallery (⚙◆).** The Prototype Gallery webview (§7.6) is not a post-hoc viewer: while an authoring mission runs, it renders the workspace's live `prototypes/` directory (read-only, sandboxed per §5.3) with file-change polling, so the owner watches screens appear and corrects course mid-mission. Implementation: `interfaces/dde-studio/**` webview extension; no engine changes.

**P3 — Refine-in-place protocol (✋§).** Pixel feedback does not open a new mission cycle. The `prototype-authoring` skill (6.6) gains a refine pass: annotate specific screens/states → revise those pages **in place** → regenerate `index.html` → deliver a per-round delta summary → request re-sign-off. Latency budget tracked under §8.4 (`prototype sign-off latency`); two consecutive rounds with no delta on a flagged screen escalate to an EDR candidate rather than silent churn.

**P4 — Believable-density scorecard line (◆).** Sample data inside prototypes is already permitted and marked (`data-sample="demo"`, §5.1a). The §8.3 prototype scorecard gains a blocking dimension: sample data must be realistic enough to evaluate hierarchy, rhythm, and states — placeholder-grade filler ("Item 1", "Lorem") scores <4 even though it violates nothing, because density that cannot be judged cannot be approved.

**Requirement:** during implementation missions — not after — DDE must produce visual samples of how the app will look when complete, including multi-screen flows and animations, reviewable by the owner as pixels. The industry has converged on exactly this "preview-before-build" posture: v0/Lovable/Bolt made generate→preview→approve the core loop ([ToolChase](https://toolchase.com/blog/v0-vs-lovable-vs-bolt/), [DevReviewer](https://devreviewer.com/bolt-new-vs-v0-vs-lovable-full-stack-prototypes-2/)), single-file HTML galleries became the zero-infrastructure living spec for agentic work ([Spooner /prototype gallery](https://flexingforks.com/posts/one-slash-command-instant-prototype-gallery-no-figma-required), [static preview pattern](https://previewship-engineering.hashnode.dev/static-preview-pattern-ai-generated-html), [ShowDeck](https://github.com/GadatheGod/ShowDeck)), and Anthropic's own artifact guidance mandates self-contained single-file HTML output ([web-artifacts-builder](https://github.com/anthropics/skills/blob/HEAD/skills/web-artifacts-builder/SKILL.md)). DDE adopts the *pattern* with its own enforcement spine, not the SaaS tools.

### 5.1 The prototype pipeline — what the worker produces

During any mission whose charter touches a user-visible surface, the worker writes into the task workspace:

```
<workspace>/prototypes/
  screens/
    overview.ready.html          # one self-contained page per screen×state
    overview.unreachable.html
    mission-control.empty.html
    ...
  flows.json                     # manifest linking pages into named flows
  index.html                     # GENERATED gallery: every screen × state × flow
```

(a) **Screens** — one self-contained HTML page per screen × state. No framework, no CDN, no build step (the generate-normalize-publish discipline: [static preview pattern](https://previewship-engineering.hashnode.dev/static-preview-pattern-ai-generated-html)). Inline `<style>` uses **only** the project token sheet (the same variable names/values as the generated `tokens.ts`), so prototype and production cannot diverge silently. Realistic-but-clearly-scoped sample data is permitted *inside prototypes only* (marked `data-sample="demo"`); the production honesty law is unchanged. Each page carries the standard page scaffold: viewport meta, `lang`, skip-link, focus-visible styles — prototypes are accessibility-tested artifacts, not sketches.

(b) **Flows manifest** — `flows.json` links screens into named user flows: entry point, ordered transitions, the trigger of each transition (click target selector), and per-node state annotations. Shape example (authoritative form = the schema, not this snippet):

```json
{
  "version": 1,
  "flows": [
    {
      "id": "start-mission",
      "entry": "overview.ready.html",
      "steps": [
        { "from": "overview.ready.html", "on": "[data-cmd='startMission']", "to": "mission-control.running.html" },
        { "from": "mission-control.running.html", "on": "[data-cmd='pauseMission']", "to": "mission-control.paused.html" }
      ]
    }
  ]
}
```

(c) **Animations** — embedded CSS keyframes/transitions only. Every animated declaration references motion tokens (`--motion-duration-*`, `--motion-easing-*`) from the token sheet; every animated state includes a `@media (prefers-reduced-motion: reduce)` variant that removes spatial movement and preserves end-states (`opacity: 1; transform: none`) per the two-layer cascade pattern ([MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-motion), [css-animation.com](https://www.css-animation.com/accessible-motion-architecture/prefers-reduced-motion-architecture/), [Verdigris guide](https://design.verdigris.co/categories/animation/reduced-motion)).

(d) **Generated index/gallery** — `index.html` lists every screen × state × flow with thumbnails-in-place (same-page sections or iframe embeds), lightbox zoom, and a reduced-motion toggle. It is regenerated from `screens/` + `flows.json` by the worker; a stale index fails validation (below). This mirrors the slash-command gallery pattern ([Spooner](https://flexingforks.com/posts/one-slash-command-instant-prototype-gallery-no-figma-required)) but is machine-checked rather than vibes-checked.

### 5.2 Animation law

- Duration and easing values exist **only** as tokens in the token sheet; literals in screens, production CSS, or prototypes fail the design lints (4.5). Tokenized motion is what makes a global reduced-motion override reach components that do not exist yet ([css-scroll-driven tokens guide](https://www.css-scroll-driven.com/accessibility-inclusive-motion-standards/implementing-prefers-reduced-motion/reduced-motion-in-design-systems-and-tokens/)).
- Three easings maximum (arrival ease-out, symmetric state-change ease, linear for progress), matching system-scale practice ([Master CSS motion](https://rc.css.master.co/guide/motion)).
- No autoplaying infinite loops longer than one bounded cycle (≤2s) except essential status indicators (spinner while checking Core), which must degrade to opacity-only under reduced motion.
- Springs/bounce/overshoot banned (Farm OS parity; matches corpus-tell avoidance — decorative motion is a fingerprint category in the [fingerprints taxonomy](https://uxskill.laithjunaidy.com/blog/ai-design-fingerprints-list.html)).
- Reduced-motion variants are mandatory per state and are part of the screenshot matrix (4.4), not an afterthought ([Verdigris](https://design.verdigris.co/categories/animation/reduced-motion)).

Rive/Lottie/Figma-Motion-class runtimes are **not adopted**: they add runtime dependencies incompatible with the CSP `default-src 'none'` webview reality and the dependency-admission bar, while CSS keyframes fully cover DDE's current motion scope (comparison: [PkgPulse 2026](https://www.pkgpulse.com/guides/lottie-vs-rive-vs-css-animations-web-animation-formats-2026), [shaheermalik](https://www.shaheermalik.com/compare/rive-vs-figma-motion)). Revisit by EDR only if product motion demands state machines.

### 5.3 Where each artifact lands in DDE's enforcement surfaces

| Pipeline stage | DDE surface | Mechanism |
|---|---|---|
| `flows.json` contract | `schemas/design/prototype_flow.schema.json` *(landed 2026-08-22, commit `29cc55a`)* → `scripts/generate_contracts.py --check` | Same SSOT/drift discipline as every other contract: schema edited, contracts regenerated, drift fails the ci.yml **"Fail on generated drift"** step ([schema-as-versioned-artifact practice](https://medium.com/@duckweave/tool-schema-drift-11-checks-before-agents-guess-6038c1748309), [contract-drift CI pattern](https://github.com/KingInYellows/yellow-plugins/blob/main/docs/operations/ci-pipeline.md)) |
| Manifest validity of a workspace | pytest verification check | `engine/verification/prototypes.py` *(wired in v1.1)*: the verification runner validates a workspace's `prototypes/flows.json` structurally (version, flow ids, entry points, every transition target and declared screen exists on disk) pre-oracle; violations demote a clean PASS to PARTIAL with `VERIFICATION_FAILURE` classification. Byte-stable `index.html` regeneration is deferred until a gallery generator ships — currently a review-skill concern (`component-gallery`) |
| Visual evidence | `VerificationRun` / `Evidence` artifacts (`schemas/objects/verification_run.json`, `evidence.json`) | Once 4.4-Phase-B lands, gallery/prototype screenshots captured in CI are attached as verification evidence; until then the DOM fingerprints serve as the machine-checkable stand-in |
| Owner pixel-approval | Approvals surface (`schemas/objects/approval.json`, standing approvals) + chapter gate | Approval gate `prototype_pixel_signoff` is REQUIRED before the implementation PR merges; recorded like any governance approval; auto-resume proceeds only on PASS / PASS-WITH-EDR (`.cursor/rules/mission-chapter-gate.mdc` parity). *(Correction 2026-08-24: this type does NOT yet exist in `APPROVAL_TYPES` — it must be added through the ordinary contract path (types + schema + contract regen + tests) or an existing type designated, per GUI-spec open item D2; until then the sign-off gate is procedural, not typed.)* |
| In-development viewing | dde-studio **Prototype Gallery webview** *(landed 2026-08-22, commit `a80f5a6`)* | The `dde.studio.preview` view is a read-only gallery: renders the active workspace's `prototypes/index.html` (or a picker over `screens/`), click-through via sandboxed iframe; during authoring missions it **live-streams** the workspace `prototypes/` directory with file-change polling (P2) |
| Sandbox security | webview iframe policy | `sandbox="allow-scripts"` **without** `allow-same-origin` (the pair is the classic escape — [Invicti](https://www.invicti.com/blog/web-security/iframe-security-best-practices), [performanceisolation](https://www.performanceisolation.com/third-party-isolation-sandboxing-strategies/building-secure-iframes-for-third-party-widgets/), [showyourcode](https://www.showyourcode.app/blog/sandboxed-html-preview), [single-file skill](https://www.developersdigest.tech/library/skills/single-file-app-generation)), content served via `srcdoc`/blob, inner CSP `default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'` matching the existing webview CSP in `html.ts`; no network, no storage |

### 5.4 The gate, in chapter-gate grammar

```
❌ BAD: implementation PR ready, "prototypes coming later," docstring says screens match the mockup → merge
✅ GOOD: prototypes/ validated against contract → screenshots/fingerprints green → owner pixel sign-off recorded → THEN implementation merges (auto-resume honors PASS / PASS-WITH-EDR)
```

Adversarial self-check (mirroring the chapter gate): could a new mission id or a `flows.json` without the index regenerate bypass this? The verification check regenerates `index.html` itself and diffs — staleness cannot hide. Is the approval a real mutation? Yes — it is an approval-row write through the Gateway command surface, not a chat acknowledgement.

### 5.5 What this buys

The owner sees real pixels of the finished app — including how flows connect and how motion feels, with reduced-motion variants demonstrated — *during* the mission, while change is cheap. This is the DDE-shaped version of the preview-loop every 2025–2026 toolchain converged on, minus the SaaS: the gallery is files in the workspace, the contract is a schema, the evidence is a VerificationRun, and the approval is governance, not a thumbs-up emoji.

---

## 6. Agent skills (loadable playbooks)

Skills are self-contained instruction sets stored under `.cursor/skills/<name>/SKILL.md` *(landed 2026-08-22, commit `f54313f`: screen-implementation, repo-mining, ui-review, component-gallery, prototype-authoring, copy-voice)*. The binding rule file (4.1) tells agents when to load which. Pattern parity with the Farm OS skill set is intentional.

### 6.1 `screen-implementation` skill

Load before implementing or restyling any surface. Steps:
1. Read this playbook §1, §4; identify the declared pattern for the surface (11). If none fits, STOP → propose EDR; do not improvise.
2. Produce/refresh the prototype set first (§5): screens × states, `flows.json`, regenerated `index.html`, motion tokens + reduced-motion variants.
3. Implement in `shared/ui/*.ts` composing **only** token references and the shared primitives (`banner`, `pill`, `row`, `emptyState`); declare all interaction states (8).
4. Extend/adjust the surface's fingerprint assertions (`overviewVisual.test.ts` style) in the same PR; run `npm test` locally.
5. Self-audit against §8 checklist; attach gallery screenshots to the PR; add `References:` footer if anything was mined.

### 6.2 `repo-mining` skill

Load before consulting any external repository or generator output. Steps:
1. Classify the intended layer against table 2.1. Visual layers: stop — not minable.
2. Licence check per §3; draft the provenance-ledger row.
3. Extract the minimal reference; note the adaptation plan (renames, token conformance, lint compliance).
4. Implement the adaptation; confirm <40% verbatim survival or justify in the PR body.
5. Append the ledger row; close with the `References:` footer.

### 6.3 `ui-review` skill

Load for reviewing UI changes; also drives the fresh-context critic (4.7). Steps:
1. Render changed surfaces from the gallery/screenshots — never review from diff alone.
2. Score against §8.1; any dimension <4 blocks, with specifics and pixel references.
3. Walk the anti-tell catalog (1.1); flag every observed instance.
4. Verify: states matrix, viewport matrix, copy voice, provenance closure, reduced-motion variants.
5. Verdict: APPROVE / BLOCK(items) / EDR-needed.

### 6.4 `component-gallery` skill

Load when adding/updating gallery or fingerprint entries (successor to Farm OS `gallery-curation`). Steps:
1. One entry per surface × state combination; name = `Surface_State` (`overview.ready`, `mission-control.paused`).
2. Sample data marked `data-sample="demo"`; production honesty law untouched.
3. Regenerate fingerprints/screenshots; confirm zero diffs beyond the intended change.
4. Update `index.html` (regenerated, never hand-edited) and the pattern map when introducing patterns.

### 6.5 `copy-voice` skill

Load before writing or editing any user-facing string. Steps:
1. Apply voice rules: verb-first controls, sentence case, figures not words, manufacturing-vocabulary exactness (mission/run/lease/gate terms from the schemas — never invented synonyms).
2. Check forbidden list: `!`, "welcome", "simply/easily/just", marketing superlatives, emoji, helper essays (superset of `FORBIDDEN_HELPER`).
3. Errors state cause + fix; unreachable ≠ misconfigured; no blame, no exclamation.
4. Run the studio suite locally; the copy gate (4.6) must be green before PR.

### 6.6 `prototype-authoring` skill

Load before producing/updating a `prototypes/` directory. Steps:
1. Enumerate surfaces × states from the charter; missing state = missing screen.
0. P1 — if the charter declares `ui_plan_checkpoint: required`, publish the screens × states manifest as text for owner comment and wait for the comment window (or explicit pass) before authoring.
2. Emit self-contained pages using token-sheet variables only; mark sample data `data-sample="demo"`, realistic enough to judge hierarchy and rhythm (P4).
3. Wire `flows.json` to the current schema; every transition target must exist.
4. Embed motion via tokens; write the reduced-motion variant for every animated rule.
5. Regenerate `index.html`; run the manifest validator; request the pixel-signoff approval.

**Refine-in-place protocol (P3):** pixel feedback never opens a new mission cycle. Per round: annotate only the flagged screens/states → revise those pages **in place** → regenerate `index.html` → deliver a delta summary naming each change against its annotation → request re-sign-off. Two consecutive rounds with no delta on a flagged screen escalate to an EDR candidate instead of silent churn; per-round latency feeds §8.4 sign-off-latency tracking.

---

## 7. Toolchain catalog

Only tools compatible with the actual stack (TS template strings, inline CSS, CSP-locked webviews, uv/pytest + npm/node:test toolchains, Windows-first dev loop). "Rejected" rows are part of the record — they stop re-litigation.

| # | Tool | Role | DDE enforcement point | Cost |
|---|---|---|---|---|
| 7.1 | `schemas/design/tokens.json` + `generate_contracts.py` extension *(operational — landed 2026-08-22)* | Token SSOT → generated `tokens.ts`; drift detection. Adapts Style Dictionary/Tokens Studio SSOT+codegen+drift practice ([devcheolu](https://devcheolu.com/en/posts/0sa4JzPKHIoeWmwdx6Am), [Tokens Studio docs](https://docs.tokens.studio/fundamentals/design-tokens/), [sd-transforms](https://github.com/tokens-studio/sd-transforms)) without Figma or a new dependency | ci.yml generated-drift step ▣ | Build cost only |
| 7.2 | `node:test` string/DOM fingerprints (existing germ) | Structural + style regression per surface; copy law | `npm test` → dde-studio.yml ⚙ (4.3, PR-blocking since 2026-08-22) | Built-in |
| 7.3 | Stdlib design-lint scanner *(operational — landed 2026-08-22; DD201–DD206 with committed shrink-only baseline)* | Bans raw values/gradients/emoji/motion literals in `shared/**` — the TS-string port of stylelint token rules ([strict-value](https://www.npmjs.com/package/stylelint-declaration-strict-value), [Discourse require-design-tokens](https://feicode.com/Discourse/discourse/src/tag/esr/stylelint-rules/require-design-tokens.mjs)) | pytest unit leg ⚙◆ + own CI step | Build cost only |
| 7.4 | Playwright + `toHaveScreenshot` *(admitted by EDR-0008, ACCEPTED 2026-08-22; implementation in flight)* | Pixel goldens over gallery/prototype states; CI-container baselines; diff budgets ([Playwright](https://playwright.dev/docs/test-snapshots), [tuning](https://web-automations.com/debugging-and-test-observability/visual-regression-testing/tuning-screenshot-comparison-thresholds/)) | New `visual` job in dde-studio.yml ⚙; evidence into VerificationRun | OSS, Apache-2.0 — admitted under EDR-0008 |
| 7.5 | `@axe-core/playwright` *(admitted by EDR-0008, ACCEPTED 2026-08-22; implementation in flight)* | WCAG 2.2 AA zero-critical gate; target-size rule enabled ([MFA11y](https://modern-framework-accessibility.com/testing-and-automating-accessibility/gating-accessibility-in-ci-cd-pipelines/)) | Same visual job, runs before critic ⚙ | OSS, MPL-2.0 — same EDR |
| 7.6 | Prototype Gallery webview (`dde.studio.preview`) *(operational — landed 2026-08-22)* | Living style guide + flow click-through; **live-streams the workspace's `prototypes/` directory during authoring missions** (P2), not only post-hoc viewing; sandboxed iframe per 5.3 | Manual pixel-review surface ✋; screenshot source | Build cost only |
| 7.7 | `prototype_flow` schema + manifest validator *(schema landed 2026-08-22; validator wired pre-oracle in the verification runner)* | Flows-manifest contract; index freshness | Schema drift ▣ + verification-runner check ◆ | Build cost only |
| 7.8 | VerificationRunner screenshot evidence *(proposed; lands with the 7.4 visual job under admitted EDR-0008)* | Prototype/gallery captures persisted as VerificationRun/Evidence rows | Chapter/release gate evidence ▣✋ | Existing infra |
| 7.9 | **Storybook / Ladle** | Rejected: React/Vite component workshops; DDE has no component framework and no bundler — fingerprints + gallery cover the same need ([Ladle](https://blog.logrocket.com/ladle-storybook-performance-project-sizes/) assessed, inapplicable) | — | — |
| 7.10 | **Chromatic / Percy** | Rejected: SaaS per-snapshot cost + Storybook-centric; Lost Pixel sunsetting ([comparison](https://alisoueidan.com/blog/comparing-chromatic-storybook-with-lost-pixel-hostoire), [helpmetest](https://helpmetest.com/blog/visual-snapshot-testing-percy-chromatic/), [QASkills](https://qaskills.sh/compare/percy-vs-chromatic)); Playwright covers the gate locally | — | — |
| 7.11 | **Stylelint / ESLint styling plugins** | Rejected as runners: they lint `.css` files, DDE styles live in TS strings; 7.3 is the faithful adaptation | — | — |
| 7.12 | **v0 / Lovable / Bolt.new** | External generators permitted as *mining-class ideation inputs* under §2 only; outputs re-expressed through DDE tokens; never committed verbatim ([ShipSet](https://shipset.app/blog/best-ai-builder-for-pms), [Causo](https://hub.causo.ai/guides/v0-vs-lovable-vs-bolt-for-founders-2026)) | Provenance ledger ✋ | Free tiers |
| 7.13 | **Rive / Lottie / Figma Motion** | Rejected for current scope: runtime deps vs CSP + admission bar; CSS keyframes + tokens suffice ([PkgPulse](https://www.pkgpulse.com/guides/lottie-vs-rive-vs-css-animations-web-animation-formats-2026)) | Revisit via EDR only | — |

Adoption phasing: 7.1–7.3 + 7.7 are **Phase 0 — landed 2026-08-22**; 7.6 landed with them; 7.4–7.5 were admitted under one combined dependency-admission EDR (**EDR-0008, ACCEPTED 2026-08-22**) and their implementation is in flight; 7.8 lands with the visual evidence job.

---

## 8. Quality scorecards & thresholds

Used by reviewers and the fresh-context critic. Each dimension scored 1–5; **any dimension <4 blocks merge.**

### 8.1 Screen scorecard

| Dimension | 5 looks like | 1 looks like |
|---|---|---|
| Pattern fidelity | Recognisably the one declared pattern; zero orphan elements | Ad-hoc layout, mixed grammars |
| Token discipline | Only generated token references; lints green | Inline hex/px/motion literals |
| Hierarchy & rhythm | Clear scan path; spacing grid holds at both widths | Uneven gaps, competing emphasis |
| Data presentation | Tabular truth: aligned figures, quiet chrome, honest empties | Decorative charts, pill-spam status, fabricated density |
| Copy voice | Verb-first, sentence case, domain-exact, terse | Marketing tone, helper essays, exclamation marks |
| States completeness | idle/loading/empty/error/disabled designed and shown | Happy path only |
| Motion restraint | Token durations, bounded loops, reduced-motion variants shown | Autoplaying loops, bounce/spring, no reduce variant |
| Accessibility | Focus rings intact, labels present, AA contrast, targets ≥28px | Removed outline, unlabeled controls |

### 8.2 Repo-mining scorecard (per extraction)

| Dimension | 5 | 1 |
|---|---|---|
| Layer legality | Engineering-only layers | Any visual layer borrowed |
| Provenance | Ledger row + commit-pinned refs | Uncited borrowing |
| Adaptation depth | Renamed/token-conformant to DDE idioms | Verbatim block dropped in |
| Licence cleanliness | Cleared pre-read | Discovered post-hoc |

### 8.3 Prototype scorecard (per `prototypes/` submission)

| Dimension | Threshold | 5 looks like | 1 looks like |
|---|---|---|---|
| Fidelity-to-tokens | <4 blocks | Pages indistinguishable in palette/type/spacing from generated tokens | Off-palette guesses, inline values |
| State coverage | <4 blocks | Every chartered surface × state present | Entry + happy path only |
| Flow completeness | <4 blocks | `flows.json` covers the chartered journeys; every transition resolves | Single screens, dangling triggers |
| Motion restraint | <4 blocks | Token motion, bounded loops, working reduced-motion toggle | Infinite decorative loops, no reduce variant |
| Believable density (P4) | <4 blocks | Realistic marked sample data (`data-sample="demo"`) that lets hierarchy, rhythm, and states be judged | Placeholder filler ("Item 1", lorem) that cannot be evaluated |
| Manifest validity | Blocking (binary) | Validator green, index regenerates stable | Stale index, unresolved targets |

### 8.4 Aggregate health metrics (reviewed at chapter gates)

- Design-lint violation count per surface (target 0, trend ↓; rising trend freezes feature UI — 4.14)
- % shipped surfaces with current fingerprints/screenshots (target 100%)
- Gallery coverage of shipped surfaces (target 100%)
- Uncited borrowings found in audits (target 0)
- axe critical/serious violations (target 0 once 7.5 lands)
- Prototype sign-off latency: mission-start → pixel approval (tracked; growing latency = process smell)

---

## 9. Gate-ready acceptance checklist

A UI slice passes when every box is checkable:

- [ ] Declared pattern matches implementation; one-surface-one-pattern holds
- [ ] P1 plan checkpoint honored when chartered (`ui_plan_checkpoint`); owner comments addressed or answered
- [ ] Tokens only: generated-module imports; design-lint scanner green; no debt added
- [ ] Prototype set delivered under §5: screens × states, valid `flows.json`, regenerated `index.html`
- [ ] Animations use motion tokens; reduced-motion variant present per state; loops bounded
- [ ] Fingerprints/screenshots updated in the same PR (light/dark/HC × motion × widths per phase); diffs explained or fixed
- [ ] States matrix complete; empty states composed, honest, essay-free
- [ ] Copy voice verified: `FORBIDDEN_HELPER` superset green
- [ ] Keyboard walk clean: Tab order, visible focus, Escape behavior; targets ≥28px; axe clean (once enforced)
- [ ] Theme triad usable (light / dark / high-contrast); all `var(--vscode-*)` reads carry fallbacks
- [ ] Fresh-context critique ≥4 on every §8.1 dimension
- [ ] Any mining: layer-legal, licence-cleared pre-read, adapted, ledger row appended, `References:` footer present
- [ ] Owner pixel sign-off recorded via the approvals surface **before** merge; chapter-gate report links it

---

## 10. Distinctiveness adoption plan (2026-08-24 research integration)

The six-stream anti-generic-output research (AI-slop fingerprint catalogs,
builder technique comparison, template-source licensing scan, motion/
animation state of the art, mechanical quality gates) produced twelve
recommendations. They integrate with THIS playbook's existing law as
follows; the staged landing plan lives in
`docs/planning/gap-closure-record.md §6.5`.

### 10.1 Extends §4.2 tokens — the art-direction record

Beyond the token sheet (palette/scale/motion), each product carries an
**art-direction record**: chosen type pairing (display + body, from a
curated corpus of distinctive, licence-cleared pairs — not Inter-only),
accent identity, layout idiom, motion identity. Generated once per
product at mission start, consumed by every screen. **Lands:** S4 tail /
small dedicated mission; extends `schemas/design/tokens.json` + generator.

### 10.2 Extends §4.5 design lints — combination lints (DD207+)

DD201–DD206 ban raw literals per-property. The research adds the
*fingerprint* level: flag the COMBINATION that marks generic output
(Inter-only type + indigo-family accent + centered-hero-3-card skeleton,
emoji-as-icon + pill-spam rows). A file can pass DD201–206 and still be
slop; DD207 catches the silhouette. **Lands:** with 10.1 in the same
mission; `tests/unit/test_studio_design_lints.py` scanner extension.

### 10.3 New gate — the silhouette test (§4.4 sibling)

Playwright screenshot → coarse layout-shape fingerprint (block positions,
column count, hero grammar) compared against a corpus of documented
generic layouts; near-match = review blocker regardless of palette.
Evidence class: the VLM screenshot-critique loop measured +17.8% output
quality in controlled studies. **Lands:** S5 (DDE-043/044) once the
browser capability renders real pages under EDR-0008's admitted
toolchain; needs an EDR for the VLM critic dependency.

### 10.4 Copy voice — specificity gate (extends clientHonesty)

`FORBIDDEN_HELPER` bans helper-essay tells. Research adds
specificity-tells: generic superlatives ("seamless", "robust",
"cutting-edge"), unexplained numbers, placeholder-grade nouns. Same test
file, same enforcement point. **Lands:** next Studio surface touched;
adopt-now.

### 10.5 Template & component sourcing law (extends §2/§3)

- **Template & component sourcing law (extends §2/§3)**: shadcn-ecosystem
  registries and blocks (**OPEN_REUSE**, programmatically ingestable),
  Tailwind Plus / Cruip (**CONDITIONAL_REUSE** — end products only, never
  into DDE's generator), ThemeForest-class marketplaces (**REJECTED** for
  builder use), galleries like godly.site/lapa.ninja/mobbin
  (**SOURCE_REFERENCE_ONLY** — art-direction input via the provenance
  ledger, zero code transfer; none offer content APIs, scraping violates
  ToS). Motion libraries: Magic UI/react-bits-free/Kibo/Origin =
  `OPEN_REUSE`; react-bits Pro/Aceternity Pro = `CONDITIONAL_REUSE`;
  **GSAP free-since-2025 but builder-clause restricted →
  `CONDITIONAL_REUSE` pending legal read**. These map onto Chapter 13.8's
  licence classes (amended 2026-08-24); ingestion becomes real at Donor
  Lab (DDE-046) behind its EDR. Emerging MCP-native design corpora
  (ReftrixMCP-class originality scoring, design-dna-mcp) are validated
  prior art but each is an untrusted donor under Ch.13.8 until admitted.
  Until then: mining protocol §2 applies unchanged.

### 10.6 Motion identity (extends §5.2 motion law)

Motion is a first-class distinctiveness axis, not decoration — the
2025–2026 practitioner consensus is that static output now itself reads
as generated (v0/Bolt are rated polished-but-inert; Lovable's consumer
wins come exactly from its motion pass). Research findings integrated:

- **Technique posture**: CSS scroll-driven animations and the View
  Transitions API are cross-browser since 2026 (~89% traffic; Firefox
  shipped same-document late 2025) and displace 30–50KB of JS animation
  library per site; JS engines (Motion/GSAP-class) shift from default to
  exception. DDE's generated products default to compositor-friendly,
  zero-JS techniques; per-project runtime libraries only within declared
  budgets.
- **Motion-identity presets**: named presets in the tokens schema
  (arrival/state/progress easings + duration ramp + optional spring spec)
  selectable per product via the art-direction record — no builder ships
  a true brand-scoped motion identity system today; this is the open gap
  DDE occupies. Prevents every DDE-built product sharing identical motion
  timing (itself a sameness signal).
- **Per-interaction motion specs**: prototype-manifest transitions gain
  trigger/easing/duration/stagger/reduced-motion-degradation fields —
  structured motion specs are the documented best practice (mirrors the
  prompting discipline Lovable users converged on), and they make motion
  reviewable as contract rather than vibes (§8.3 scorecard dimension).
- **Guardrails stay mechanical**: reduced-motion variants remain table
  stakes (asserted as blocking Playwright assertions once EDR-0008 Phase
  B lands, not documentation); compositor-friendly properties only;
  `will-change` sparingly.
- **Licence classes** (Ch.13.8): Magic UI / react-bits free tier /
  Kibo / Origin = `OPEN_REUSE` via shadcn-registry format; react-bits Pro
  and Aceternity Pro items `CONDITIONAL_REUSE` (per-seat keys);
  **GSAP is free since April 2025 but its standard licence restricts use
  in tools offering visual no-code building — `CONDITIONAL_REUSE`
  pending legal read before any platform embedding**; Lottie/Rive stay
  rejected for DDE's own stack absent product demand.

---

## 11. Traceability

| Section | Source(s) |
|---|---|
| §1 root causes & tells | [rottoways](https://rottoways.com/blog/ai-generated-website-looks-generic) · [uxskill slop](https://uxskill.laithjunaidy.com/what-is-ai-slop.html) · [tasteprofile](https://tasteprofile.io/blog/why-ai-generated-ui-looks-generic) · [Sailop guide 2026](https://sailop.com/blog/ai-slop-definitive-guide-2026) · [prg.sh purple-gradient](https://prg.sh/ramblings/Why-Your-AI-Keeps-Building-the-Same-Purple-Gradient-Website) · [Fountain Institute](https://www.thefountaininstitute.com/blog/signs-vibe-coded-ui) · [Sailop state-of-web](https://sailop.com/blog/ai-slop-2026-state-of-the-ai-generated-web) · [Developers Digest 16 patterns](https://www.developersdigest.tech/blog/ai-design-slop-and-how-to-spot-it) · [35 fingerprints](https://uxskill.laithjunaidy.com/blog/ai-design-fingerprints-list.html) · [Unslop UI](https://www.claudecodehq.com/playbooks/unslop-ui) |
| §2 mining protocol | [PatrickJS/awesome-cursorrules](https://github.com/PatrickJS/awesome-cursorrules) · [best-cursor-rules](https://github.com/renvia-code/best-cursor-rules) · [MatchKit design-system setup](https://www.matchkit.io/blog/cursor-design-system-setup) · [SeedFlip](https://seedflip.co/blog/cursorrules-design-output) · [DesignMD DESIGN.md](https://designmd.directory/guides/how-to-make-cursor-generate-better-frontend-design) · generator-input framing: [ShipSet](https://shipset.app/blog/best-ai-builder-for-pms), [ToolChase](https://toolchase.com/blog/v0-vs-lovable-vs-bolt/) |
| §3 licences | Project licences observed during research: shadcn/ui & Ladle (MIT), Playwright & Storybook & Style Dictionary (Apache-2.0), axe-core (MPL-2.0) — verify at adoption in the EDR |
| §4.1–4.3 authority/CI | [Anthropic frontend-design skill](https://github.com/anthropics/claude-plugins-official/blob/b392f51899343f35a203260a4b344803de236d13/plugins/frontend-design/skills/frontend-design/SKILL.md) · [Tailkits skill survey](https://tailkits.com/blog/claude-skills-ui-design-web-development/) · [web-artifacts-builder](https://github.com/anthropics/skills/blob/HEAD/skills/web-artifacts-builder/SKILL.md) · [Medium: skills vs slop](https://alirezarezvani.medium.com/improving-frontend-design-through-claude-skills-breaking-free-from-ai-slop-2c9351d53ce4) |
| §4.2 tokens/codegen/drift | [devcheolu pipeline](https://devcheolu.com/en/posts/0sa4JzPKHIoeWmwdx6Am) · [jdp.work architecture](https://jdp.work/design-tokens-architecture/) · [Tokens Studio fundamentals](https://docs.tokens.studio/fundamentals/design-tokens/) · [Lenka pipeline](https://lenkastudio.com/blog/how-to-build-design-tokens-pipeline-figma-to-code) · [sd-transforms](https://github.com/tokens-studio/sd-transforms) |
| §4.4 screenshots | [Playwright snapshots](https://playwright.dev/docs/test-snapshots) · [threshold tuning](https://web-automations.com/debugging-and-test-observability/visual-regression-testing/tuning-screenshot-comparison-thresholds/) · [Grabbit](https://www.grabbit.live/blog/playwright-visual-regression-testing) · [QAPractices](https://qapractices.com/documentation/playwright-visual-regression-testing/) · [testdino visual-regression skill](https://github.com/testdino-hq/playwright-skill/blob/main/core/visual-regression.md) |
| §4.4/§7 rejected VRT SaaS | [Ali Soueidan comparison](https://alisoueidan.com/blog/comparing-chromatic-storybook-with-lost-pixel-hostoire) · [helpmetest Percy/Chromatic](https://helpmetest.com/blog/visual-snapshot-testing-percy-chromatic/) · [beefed.ai](https://beefed.ai/en/visual-regression-storybook-percy-chromatic) · [QASkills compare](https://qaskills.sh/compare/percy-vs-chromatic) |
| Landed Phase-0 implementation (2026-08-22) | commits `58015fb` (token SSOT + drift gate) · `d03d415` (design lints DD201–DD206, shrink-only baseline) · `5f31142` (design-gate CI, studio client tests PR-blocking) · `a80f5a6` (live Prototype Gallery) · `b5a0ebb` (prototype-manifest verification sweep) · `29cc55a` (prototype flow manifest contract) · `f54313f` (binding rule file, six skills, provenance ledger) |
| §4.5 lint-enforced law | [stylelint strict-value](https://www.npmjs.com/package/stylelint-declaration-strict-value) · [CSS Architecture plugin config](https://www.css-architecture.com/token-scaling-validation-ci-pipelines/stylelint-plugin-configuration/) · [custom token rules](https://www.css-architecture.com/token-scaling-validation-ci-pipelines/stylelint-plugin-configuration/writing-custom-stylelint-rules-for-token-usage/) · [stylelint configure messages](https://github.com/stylelint/stylelint/blob/HEAD/docs/user-guide/configure.md) |
| §4.7 critic practice | [visual-review instructions/harness](https://github.com/gosha70/code-copilot-team/blob/master/adapters/github-copilot/.github/instructions/visual-review.instructions.md) + [spec](https://github.com/gosha70/code-copilot-team/blob/master/specs/visual-review-ui-harness/spec.md) · [design-review SKILL](https://github.com/humbleteam/design-review/blob/refs/heads/main/SKILL.md) · [GAN-loop rubric scoring](https://github.com/modu-ai/moai-adk/blob/main/internal/template/templates/.claude/skills/moai-workflow-gan-loop/SKILL.md) |
| §4.9 a11y gates | [MFA11y CI gating](https://modern-framework-accessibility.com/testing-and-automating-accessibility/gating-accessibility-in-ci-cd-pipelines/) · [failing PRs on axe](https://modern-framework-accessibility.com/testing-and-automating-accessibility/gating-accessibility-in-ci-cd-pipelines/failing-pull-requests-on-axe-violations/) · [A11yFlow GH Actions](https://www.a11yflow.dev/blog/accessibility-testing-github-actions) · [QASkills a11y 2026](https://qaskills.sh/blog/ai-accessibility-testing-tools-2026) · [a11y-next-app example](https://github.com/chandansamal/a11y-next-app) |
| EDR-0008 (Phase 1 toolchain admission) | Accepted 2026-08-22 by owner decision; authoritative record is the accepted row in the Project Truth `edrs` table; readable copy at `docs/truth/edr/EDR-0008-frontend-visual-gate-toolchain-admission.md` |
| §4.12 theme triad / webview | [VS Code Webview API](https://code.visualstudio.com/api/extension-guides/webview) · [Struyf code-driven theming](https://www.eliostruyf.com/code-driven-approach-theme-vscode-webview/) · [Cursor forum fallback analysis](https://forum.cursor.com/t/extension-webviews-dont-receive-vscode-theme-css-variables-themed-extension-ui-breaks-e-g-claude-code-panel/165601) |
| Color/type foundations informing 4.2/4.12 | [OKLCH blueprint](https://dev.to/okabrionz/universal-oklch-color-system-blueprint-one-base-color-design-tokens-3639) · [carmenansio OKLCH](https://www.carmenansio.com/articles/oklch-and-the-modern-color-stack/) · [atelier palette recipes](https://github.com/IamK77/Skill/blob/main/skills/atelier/color/references/oklch-palette-recipes.md) · [orchestkit token rules](https://orchestkit.yonyon.ai/docs/reference/skills/design-system-tokens) · [dark-mode alias remap](https://github.com/yonatangross/orchestkit/blob/main/plugins/ork/skills/design-system-tokens/rules/tokens-theming-darkmode.md) |
| Component-API discipline informing 2.1 | [shadcn Base-UI default](https://ui.shadcn.com/docs/changelog/2026-07-base-ui-default) · [unified radix package](https://ui.shadcn.com/docs/changelog/2026-02-radix-ui) · [three-layer wrappers](https://thecodeforge.io/javascript/reusable-component-library-shadcn-ui/) · [Headless UI rationale](https://tailwindcss.com/blog/headless-ui-unstyled-accessible-ui-components) · [headlessui.com](https://headlessui.com/) · [MakerStack review](https://makerstack.co/reviews/headless-ui-review/) |
| Gallery/storybook-first context | [Storybook MCP sneak peek](https://storybook.js.org/blog/storybook-mcp-sneak-peek/) · [manifests docs](https://storybook.js.org/docs/ai/manifests.md) · [Rachel Cantor manifest pitfalls](https://rachel.fyi/posts/storybook-mcp-reads-your-manifest-not-your-docs-tab) + [agent design systems](https://rachel.fyi/posts/your-agent-is-reading-a-different-design-system) · [Ladle intro](https://ladle.dev/blog/introducing-ladle/) · [helpmetest Ladle](https://helpmetest.com/blog/ladle-react-component-development/) · [LogRocket Ladle perf](https://blog.logrocket.com/ladle-storybook-performance-project-sizes/) |
| §5 prototypes/preview loops | [Spooner /prototype gallery](https://flexingforks.com/posts/one-slash-command-instant-prototype-gallery-no-figma-required) · [static preview pattern](https://previewship-engineering.hashnode.dev/static-preview-pattern-ai-generated-html) · [ShowDeck](https://github.com/GadatheGod/ShowDeck) · [Bun standalone HTML](https://github.com/oven-sh/bun/blob/a0e221e0/docs/bundler/standalone-html.mdx) · [DevReviewer v0/Lovable/Bolt](https://devreviewer.com/bolt-new-vs-v0-vs-lovable-full-stack-prototypes-2/) · [DEV product-studio lessons](https://dev.to/jakub_inithouse/lovable-vs-bolt-vs-v0-vs-cursor-for-shipping-mvps-what-we-learned-running-a-product-studio-625) · [Causo founder guide](https://hub.causo.ai/guides/v0-vs-lovable-vs-bolt-for-founders-2026) |
| §5.0 Cocodly loop-shape ports | [cocodly.com](https://www.cocodly.com/) · [About Cocodly](https://www.cocodly.com/about) · [Cocodly docs](https://www.cocodly.com/docs) — loop-shape mechanics observed from public product behavior; process/engineering layers ported per §2.1, zero visual-layer transfer |
| §10 distinctiveness research (2026-08-24) | [Superdesign distributional convergence](https://www.superdesign.dev/blog/why-ai-design-looks-generic) · [Sailop shadcn monoculture](https://sailop.com/blog/shadcn-ui-design-monoculture-2026) · [Spot the Slop](https://world.hey.com/kostac/spot-the-slop-a-ui-designer-s-guide-to-fixing-ai-defaults-4c448c9c) · [VLM critique +17.8% (arXiv 2604.05839)](https://doi.org/10.48550/arxiv.2604.05839) · [shadcn registry format](https://ui.shadcn.com/docs/registry/getting-started) · [21st.dev registry directory](https://21st.dev/blog/shadcn-registry-directory) · [Tailwind Plus licence](https://tailwindcss.com/plus/license) · [ThemeForest Regular terms](https://themeforest.net/licenses/terms/regular) · [GSAP free announcement](https://webflow.com/blog/gsap-becomes-free) + [standard licence](https://gsap.com/community/standard-license/) · [View Transitions support matrix](https://www.css-scroll-driven.com/scroll-driven-view-transition-implementation-patterns/view-transition-browser-support-matrix/) · [scroll-driven 2026 analysis](https://mintec.co/blog/scroll-driven-view-transitions-css-2026/) · [uimotionprompts structured motion](https://uimotionprompts.com/blog/how-to-get-better-animations-in-lovable) · [DEV builder motion comparison](https://dev.to/bean_bean/v0dev-vs-boltnew-vs-lovable-the-complete-generative-ui-comparison-2026-klg) |
| §5.2 motion law | [MDN prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-motion) · [two-layer cascade](https://www.css-animation.com/accessible-motion-architecture/prefers-reduced-motion-architecture/) · [Verdigris reduced-motion guide](https://design.verdigris.co/categories/animation/reduced-motion) · [motion tokens override reach](https://www.css-scroll-driven.com/accessibility-inclusive-motion-standards/implementing-prefers-reduced-motion/reduced-motion-in-design-systems-and-tokens/) · [Master CSS motion](https://rc.css.master.co/guide/motion) · [PkgPulse formats 2026](https://www.pkgpulse.com/guides/lottie-vs-rive-vs-css-animations-web-animation-formats-2026) · [shaheermalik Rive/Figma Motion](https://www.shaheermalik.com/compare/rive-vs-figma-motion) · [Beryl comparison](https://www.beryldesign.fr/en/post/figma-motion-vs-rive-jitter-lottie) |
| §5.3 sandboxing | [Invicti iframe practices](https://www.invicti.com/blog/web-security/iframe-security-best-practices) · [performanceisolation isolation ladder](https://www.performanceisolation.com/third-party-isolation-sandboxing-strategies/building-secure-iframes-for-third-party-widgets/) · [showyourcode sandboxing](https://www.showyourcode.app/blog/sandboxed-html-preview) · [thedevtools sandbox guide](https://www.thedevtools.in/blog/html-renderer-sandbox-guide) · [single-file-app generation skill](https://www.developersdigest.tech/library/skills/single-file-app-generation) |
| §5.3 manifest contracts | [schema-drift checks](https://medium.com/@duckweave/tool-schema-drift-11-checks-before-agents-guess-6038c1748309) · [contract-drift CI pattern](https://github.com/KingInYellows/yellow-plugins/blob/main/docs/operations/ci-pipeline.md) · [schemadiff](https://github.com/jsleekr/schemadiff) |
| DDE-internal anchors | `AGENTS.md` · `.cursor/rules/mission-chapter-gate.mdc` · `.cursor/rules/dde-design-guardrails.mdc` (binding rule file, landed 2026-08-22) · `interfaces/dde-studio/shared/ui/base.ts` + generated `tokens.ts` · `schemas/design/tokens.json` + `schemas/design/prototype_flow.schema.json` · `tests/unit/test_studio_design_lints.py` · `engine/verification/prototypes.py` (manifest sweep pre-oracle) · `interfaces/dde-studio/src/webviews/previewGalleryProvider.ts` (live gallery) · `docs/design/provenance-ledger.md` · `shared/overviewVisual.test.ts` + `shared/clientHonesty.test.ts` (gate germs) · `.github/workflows/ci.yml` (drift + design-lint steps) · `scripts/generate_contracts.py` · `docs/planning/gap-closure-record.md` · `interfaces/dde-studio/docs/overview-mockup-alignment.md` |

*End of DDE frontend & UX playbook — v1.1 operationalized; Phase 1 visual gates admitted by EDR-0008, implementation in flight.*
