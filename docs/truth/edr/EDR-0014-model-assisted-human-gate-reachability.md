# EDR-0014 — Model-assisted human-gate reachability and draft risk
# vocabulary

> **Location note.** Per Chapter 3.6, an EDR is a row in the `edrs` table,
> written only by `engine/truth/`. Following the convention established in
> `EDR-0001`–`EDR-0013`, this file is a **markdown pre-image** of the eventual
> `edrs` row, filed as the proposal itself. **This file is not itself an
> accepted EDR.** `status` is `proposed`; only a human decision via
> `scripts/accept_owner_edrs.py` can move it to `accepted`.

- **slug:** `EDR-0014`
- **status:** `proposed`
- **supersedes:** none (carries the one MAJOR finding of the independent
  chapter-gate review of DDE-040; the three MINOR findings are closed in
  the remediation commit on `dde-040-planning-mode` and recorded here for
  completeness)
- **raised during:** independent chapter-gate review (2026-08-24) of the
  DDE-040 planning landing (`f448140`); verdict PASS-WITH-EDR.

## Context

Chapter 4.3's approval table (`docs/blueprint/REV_2_0.md`, §4.3) requires
graph approval "when any node is `risk_class ≥ high` or
`blast_radius ≥ cross_module`". DDE-040 encoded that threshold verbatim
(`engine/planning/registry.py` `promote_human_gate_required`,
`{high, critical}` / `{cross_module, systemic}`). The gate review proved —
including with a live counterfactual probe — that the threshold function is
correct **but can never fire on real input**:

- `DraftNode` (`schemas/objects/plan_draft.json`,
  `engine/contracts/plan_draft.py`) carries no `risk_class` /
  `blast_radius` fields;
- `_materialise` hardcodes every materialised Task to
  `risk_class="low"`, `blast_radius="local"`,
  `requires_approval=False`;
- the gate result's only consumer is the `PlanDraftPromoted` event
  payload — `activate_task_graph`
  (`engine/planning/service.py`) performs no planning-mode/risk-aware
  check, and dispatch-side approval enforcement keys off
  `task.requires_approval`, which is hardcoded false on this path.

So the model-assisted path has an inert computation where Chapter 4.3
requires an enforceable human boundary. It is **safe-by-erasure today**
(drafts cannot express risk, and no dispatch surface consumes promoted
graphs), which is why this is PASS-WITH-EDR rather than FAIL — but the
moment drafts grow risk vocabulary, or `promote_draft` gains any
gateway/dispatch exposure, the gate stays silently off unless this EDR's
decision lands first.

## Decision (proposed)

1. **Risk vocabulary reaches the draft.** `DraftNode` gains `risk_class`
   and `blast_radius` (with `requires_approval` derived from the same
   Ch.4.3 threshold); `_materialise` maps them onto materialised Task
   objects instead of hardcoded defaults, so a model-proposed high-risk
   node produces a high-risk Task.
2. **The gate is enforced where graphs become live, not merely recorded.**
   The APPROVED→ACTIVE boundary (the existing TaskGraph lifecycle writer)
   refuses activation of a graph whose promotion was
   `human_gate_required=True` until the corresponding human approval
   exists — keyed on durable state (planning mode + node risk on the
   graph/tasks), never on event payloads alone.

**Landing condition (hard precondition):** items 1–2 MUST be landed
before `promote_draft` is exposed through ANY gateway command surface,
dispatch path, or automation consumer. Today's erasure-safety is the only
thing that makes the current wiring honest.

**MINOR findings closed in the remediation commit (recorded here):**

- `mission_template.json` `blast_radius` enum value `system` corrected to
  `systemic` — Chapter 4.2 and the Task contract say `systemic`; the old
  value validated a template whose instantiation later crashed Task
  construction;
- `mission_template.json` `order` 210 → 212 — 210 collided with
  `verification_run.json`, silently coupling canonical table order to a
  future rename;
- five refusal branches gained direct negative tests (duplicate node
  keys, unknown template edge type, promote-time graph-not-APPROVED,
  null-result replay guard, fresh-key validate-on-non-PROPOSED).

## Consequences

- If adopted: model-assisted planning gains a genuinely enforceable
  human boundary at activation, and the Ch.4.3 table becomes true end to
  end rather than true-at-the-threshold-function-only.
- If rejected: `promote_draft` must remain unexposed indefinitely, or the
  divergence must be recorded as an explicit accepted decision — an inert
  gate behind an exposed surface is not an option.
