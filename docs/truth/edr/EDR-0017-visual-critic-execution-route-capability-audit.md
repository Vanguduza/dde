# EDR-0017 — Visual-critic execution route: capability audit finding and
# a real local route vs. EDR-0016's assumed brokered-API route

> **ACCEPTED 2026-09-04 by explicit project-owner decision, resolving this
> filing as OPTION C** (create a new, narrowly scoped capability dedicated
> to unattended, bounded multimodal visual critique; do NOT amend
> `capability.claude_code_invoke` to become generally unattended; do NOT
> bypass or weaken `STANDING_FORBIDDEN_TYPES`). The decision text and its
> guardrails are transcribed in the ACCEPTANCE section at the end of this
> file. See that section for what was actually built.

> **Location note.** Per Chapter 3.6, an EDR is a row in the `edrs` table,
> written only by `engine/truth/`. Following the convention established in
> `EDR-0001`–`EDR-0016`, this file is the **markdown pre-image** of that
> row. The durable row now exists: `EDR-0017` was added to
> `scripts/accept_owner_edrs.py`'s `ACCEPTED_OWNER_EDR_SLUGS` and payload
> map — the repository's authoritative, versioned representation of the
> accepted owner decisions, from which any environment's Project Truth is
> provisioned — and the propose+accept path was run, producing an accepted
> row readable back through `TruthRepository.get_edr_by_slug`.
> `tests/integration/test_accepted_edr_rows.py` pins that state for every
> accepted slug, so this decision cannot silently drift out of Project
> Truth. Where this file and the row differ in wording, the row outranks it.

- **slug:** `EDR-0017`
- **status:** `accepted (2026-09-04)`
- **supersedes:** none (amends `EDR-0016`'s decision 1 "Model choice" only;
  every other EDR-0016 decision — rubric storage, retention, bounded
  revise ≤3 cycles, rank-9-forever — is unaffected)
- **affected_requirement_slugs:** none filed yet
- **raised during:** DDE-068 implementation, capability audit performed on
  explicit instruction not to accept `BLOCKED_EXTERNAL` for the VLM critic
  without first auditing what DDE already has, rather than assuming a
  missing `ANTHROPIC_API_KEY` settles the question.

## Context

`EDR-0016` (accepted 2026-08-24) admitted a VLM design-critic capability for
DDE-068 and, at its own acceptance, decided (item 1) that the model would be
"selected by name at implementation time from whatever providers are then
declared," routed through "the EXISTING provider-agnostic selection path...
`RouterService.model_mode='fixed'`... rid[ing] the same broker/adapter
machinery as every other harness (brokered short-lived credentials, declared
`side_effect_class`)."

At DDE-068 implementation time (this tranche), a capability audit was
performed rather than assuming that gap unfillable:

- No `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/any multimodal-provider credential
  exists in any environment this project has run in to date.
- No module under `engine/**` imports an `anthropic`/`openai`/vision-provider
  SDK.
- `engine/routing/rules.py`'s Appendix A "vision and visual evidence"
  profile is a routing-*eligibility description*; no adapter under
  `adapters/**` implements it and no `RouterService.model_mode="fixed"`
  pin exists anywhere in the repo for a vision-capable model.
- **A real route DOES exist and is already fully implemented and tested**:
  `capability.claude_code_invoke` (`engine/capabilities/seed.py`), backed
  by `adapters/claude/adapter.py`'s `ClaudeCodeWorkerAdapter` (EDR-0001
  Path A, accepted 2026-08-24 per the same owner standing directive that
  accepted EDR-0016). It spawns the human's own already-`claude
  login`-authenticated local `claude` CLI as a real subprocess — a
  genuinely multimodal-capable process (it can read an image file path
  given in its prompt) — and is already covered by
  `tests/unit/test_claude_adapter_requires_approval.py`.

This route is real, but it is **not the mechanism EDR-0016 decision 1
describes**, on two structural points, not merely a naming detail:

1. **No brokered credential, by design.** `ClaudeCodeWorkerAdapter`'s whole
   point (its module docstring's explicit negative constraint) is that it
   *never* reads, stores, mints or forwards any Anthropic credential — it
   inherits the human's own terminal session authentication unmodified.
   EDR-0016 decision 1's "brokered short-lived credentials" and decision 2's
   per-call `$0.05`/`$10`-per-month cost-ceiling accounting (Ch.16.4) have no
   referent here: there is no broker call and no metered per-call cost to
   ceiling against (the real cost is the human's shared, rate-limited
   subscription-seat quota, accounted in EDR-0001's own terms, not dollars).
2. **`external_model_invocation` is `STANDING_FORBIDDEN_TYPES`, enforced in
   code** (`engine/governance/types.py`; checked at
   `engine/governance/service.py:1292`). Every single
   `capability.claude_code_invoke` use requires a fresh, individually
   human-decided `Approval` — `ApprovalService.grant_standing`/
   `authorize_standing` reject the type outright. DDE-068's charter text
   calls for "bounded **automatic** revision of at most 3 cycles" and a
   loop the runner drives without a human deciding each step. Using this
   route as-is means each of up to 3 critique calls in one revision loop
   individually blocks on a human clicking approve — the loop's *state
   machine* (what to fix, whether to retry, when to escalate) is genuinely
   automatic, but the *model invocation* is not unattended.

## Alternatives

**(a) Wait for a real brokered VLM provider**, exactly as EDR-0016 decision 1
originally envisioned (a low-cost, high-throughput multimodal API, wired
through `adapters/**` behind `RouterService.model_mode="fixed"`, with real
brokered short-lived credentials and real Ch.16.4 cost-ceiling accounting).
Correctly matches EDR-0016's letter. Cost: DDE-068's VLM-critique and
believable-density gates (both scored from the same rubric call) stay
`BLOCKED_EXTERNAL` indefinitely — no such provider has been provisioned in
any environment this project has run in, and nothing in this audit found a
path to provision one without a new paid API admission this EDR is not
authorized to make unilaterally.

**(b) Amend EDR-0016 decision 1 to route DDE-068's critic through
`capability.claude_code_invoke`** (EDR-0001 Path A) as its real execution
route, explicitly redefining "bounded automatic revision" for this
capability as *system-driven revision-loop orchestration, human-approved
per individual model invocation* rather than fully unattended — matching
what `STANDING_FORBIDDEN_TYPES` already, deliberately enforces for exactly
this capability, for exactly this reason (protecting a human's personal,
rate-limited entitlement from runaway automated use). Cost ceiling becomes
an invocation-count/frequency ceiling (Ch.16.4-style accounting in
invocation counts, not dollars) rather than EDR-0016 decision 2's `$`
figures. Benefit: DDE-068's critique and density gates become real,
callable, evidence-producing capabilities today, using only
already-admitted DDE architecture (EDR-0001), with no new paid API, no new
provider SDK, no new credential admission.

**(c) Admit a second, narrower capability** specifically for bounded,
lower-friction automated critique (e.g. a standing-approvable
`visual_critique_invocation` type distinct from the general-purpose
`external_model_invocation`, scoped tightly enough — read-only, screenshot
in, structured JSON out, capped call count — that a human could grant
standing approval for it specifically without reopening the general
"automate my whole subscription seat" risk EDR-0001 guards against). This
is the largest change: a new approval type, new `STANDING_FORBIDDEN_TYPES`
carve-out reasoning, and its own risk review — genuinely a new governance
decision, not a reading of an existing one.

## Decision (proposed at filing time)

The filing recommended **(b)** as the smallest change. The project owner
decided **(c)** instead — see ACCEPTANCE below. (c) was chosen precisely
because (b) would have relaxed a broad, privileged capability's approval
semantics to serve one narrow use, weakening DDE's security architecture
for everything else that capability governs.

## Consequences

- If (b) is adopted: DDE-068's VLM critique and believable-density gates
  become real, callable capabilities using already-admitted DDE
  architecture; the human retains a per-invocation approval checkpoint on
  every live model call (an intentional, not incidental, safety property);
  no new paid API dependency is added.
- If (a) is kept: DDE-068's critique/density gates remain `BLOCKED_EXTERNAL`
  until a brokered provider is actually provisioned — an open-ended wait
  with no committed unblock date in any document this audit found.
- If (c) is pursued: DDE-068 unblocks with a lower-friction (potentially
  standing-approvable) capability, at the cost of a genuinely new governance
  decision and its own risk review, deferred to a future EDR if the human
  wants it explored.
- Either way, this filing does not by itself complete DDE-068's VLM/density
  requirements; it only proposes which real route those requirements should
  be built against. No implementation in the filing tranche invoked
  `capability.claude_code_invoke` live — doing so before this EDR was
  decided would have spent the human's own subscription-seat quota on an
  architecture decision they had not yet made, which is exactly what
  EDR-0001's per-invocation approval gate exists to prevent an agent from
  doing unilaterally.

## ACCEPTANCE (2026-09-04) — OPTION C

**Accepted as Option C by explicit project-owner decision.** The owner
accepted the blocker analysis above and rejected both (a) waiting
indefinitely for a brokered provider and (b) relaxing the broad capability,
on the stated grounds that "relaxing its approval semantics globally merely
to satisfy DDE-068 would weaken DDE's security/capability architecture."

**Decision.** DDE exposes a **new, narrowly scoped** multimodal
visual-critique capability for machine-governed frontend verification. It
may use an already-authorized local multimodal execution substrate,
including the existing Claude Code runtime where technically appropriate,
but **it must not expose general Claude Code execution privileges to the
unattended verification loop**. Its whole purpose is to transform bounded
visual evidence plus a versioned rubric into a structured
visual-verification verdict.

**Guardrails set at acceptance, all binding:**

1. `capability.claude_code_invoke` is **not** weakened. It keeps
   `external_model_invocation` and its `STANDING_FORBIDDEN_TYPES`
   membership, and keeps requiring a fresh human `Approval` per invocation.
2. `STANDING_FORBIDDEN_TYPES` is neither bypassed nor edited.
3. The new capability must be narrower than the broad one, with distinct
   authorization and distinct schemas — never an alias for it.
4. No generic "narrowness" escape hatch: the exemption from per-invocation
   human approval attaches to this specific registered capability and its
   validated request schema, not to any capability that labels itself
   narrow.
5. Provider abstraction preserved: the engine asks for a multimodal visual
   critic, not for one vendor forever. Provider-specific execution stays
   behind an adapter.
6. Claude `/design` remains a Frontend Studio design capability and is
   architecturally distinct from the independent visual critic, even where
   the same model family serves both.
7. Unattended does not mean unbounded: hard caps on attempts, repair
   cycles, timeout, evidence size, spend; a fixed approved rubric; no
   arbitrary prompt; no general tools; no source mutation; no recursive
   agent creation; an explicit failure state; an auditable invocation
   record.
8. Real resource consumption is recorded, never invented.

### What was built against this decision

- **`capability.visual_critique`** — new `SeedCapability`
  (`engine/capabilities/seed.py`), `PURE_READ`, T1, distinct
  `capability_id`, distinct governance posture from the broad
  `EXTERNAL_NON_IDEMPOTENT` `capability.claude_code_invoke`. Governed by
  the ordinary Chapter 9 lease path; **no new approval type was added and
  none was removed from `STANDING_FORBIDDEN_TYPES`**.
- **`engine/capabilities/visual_critic.py`** — the typed seam
  (`VisualCriticCapability`, `VisualCritiqueRequest`,
  `VisualCritiqueResult`). The request type deliberately carries **no
  prompt/instruction field at all**, so no caller can smuggle instructions
  into the runtime (structural injection defence, asserted by test).
- **`adapters/visual_critic/adapter.py`** — `LocalMultimodalVisualCritic`,
  the provider-specific runtime, containment enforced by construction:
  a fresh per-invocation scratch directory holding **only** the screenshot
  (no repo, no workspace, no source in reach); `--restricted` (removes
  command/code-running tools and WebFetch, ignores settings files);
  `--allowed-tools Read` plus an explicit deny list; `--permission-prompts
  none` (anything that would prompt is denied, never silently allowed);
  `--json-schema` + `--output-format json` (structured output constrained
  at source); a hard `--max-budget-usd` ceiling and wall-clock timeout;
  no `--add-dir`, no `--mcp-config`, no `--agents`.
- **`schemas/design/visual_critique_rubric.json`** — the versioned rubric
  (EDR-0016 decision 3's storage location, unchanged), transcribed from
  playbook §8.1 and §8.3 including **believable_density** as a scored
  dimension. The adapter refuses to critique when the requested rubric
  version does not match the rubric on disk.
- **`engine/verification/visual_critique.py`** — verdict schema,
  fail-closed `parse_verdict` (rejects malformed JSON, missing fields,
  out-of-range scores and unknown fields), `evaluate_verdict` applying
  playbook §8's own "any dimension <4 blocks" rule, and
  `decide_revision_action` implementing the bounded repair policy
  (`PROMOTE` / `REVISE` / `ESCALATE_HUMAN`, capped at
  `MAX_REVISION_CYCLES = 3`).
  **The gate consumes validated fields, never prose**: a model claiming
  `"verdict": "PASS"` while scoring a dimension below threshold is still
  blocked (asserted by test), and `rubric_version`/`model`/`cost_usd` are
  attached from real transport metadata rather than read from the model's
  own response, so a model cannot spoof them.
- **Deterministic density evidence** (`compute_density_evidence` in
  `engine/verification/silhouette.py`) is kept strictly separate from the
  perceptual believable-density judgment and supplied to the critic as
  context only — neither impersonates the other.
- **`visual_critique` oracle kind** wired through
  `schemas/objects/acceptance_oracle.json`, `EXECUTABLE_KINDS`,
  `checks.py::_run_visual_critique` and the runner, so the verdict reaches
  the already-proven promotion gate with no bespoke merge logic.
- **Fail-closed classes kept distinct**, not collapsed: a missing
  capability is `POLICY_DENIED`; an unavailable/erroring/malformed critic
  is `ERRORED` (a check that could not run proves nothing); a genuine
  sub-threshold rubric score is `FAILED`.

### Resource governance, measured rather than assumed

A live discovery invocation during implementation cost **$0.142** and was
terminated by its own `--max-budget-usd` ceiling before generating output,
with the spend dominated by ambient context caching (~35k cache-creation
tokens) rather than the critique itself. Two facts follow, both recorded
rather than guessed:

1. A per-invocation ceiling below roughly $0.25 truncates real work, so the
   adapter's default is set above that with the real figure documented.
2. Nested invocations draw on **the same rate-limited pool as the
   operator's own interactive session** — observed directly when that pool
   was exhausted mid-implementation. This is the concrete reason the
   bounded caps in guardrail 7 are not ceremonial, and it is why the live
   end-to-end critique run is treated as an explicitly budgeted step rather
   than something a verification loop should perform casually.

### Live evidence (recorded 2026-09-04)

The decision was exercised for real, not just implemented:
`docs/evidence/dde-068/` records a full chain run with no stand-ins — real
Playwright render, real screenshot, real deterministic analysis, real
critique through `capability.visual_critique`, real verdict, real promotion
decision.

- The deliberately poor candidate was rejected (BLOCK at 0.92;
  `believable_density`, `token_discipline`, `data_presentation`,
  `copy_voice`, `states_completeness` all scored 1).
- The good candidate was blocked on `accessibility = 3` at cycle 0 —
  a defect the deterministic layer had passed — then its own
  `repair_instructions` were applied and cycle 1 passed with every
  dimension >= 4, moving `REVISE (1 of 3)` -> `PROMOTE`. That is the
  bounded repair loop working on real pixels, unscripted.
- The critic quoted the deterministic density evidence back verbatim in a
  non-blocking finding, confirming the two density layers cooperate without
  either impersonating the other (guardrail: believable-density judgment is
  perceptual, density evidence is measured).

Measured cost across three live invocations: **$0.3631** on
`claude-sonnet-5`, reported by the runtime rather than estimated —
satisfying guardrail 8.

**GUI-spec open item D2 closed as part of this work:**
`prototype_pixel_signoff` is now an admitted `APPROVAL_TYPES` member and is
in `STANDING_FORBIDDEN_TYPES`, so `ESCALATE_HUMAN` has a real approval class
to land on and no standing grant can pre-authorise a batch of pixel
sign-offs. `StudioFrontendService.request_pixel_signoff` creates a real
`Approval` bound by scope hash to the screen, rubric version and failing
dimensions.

### Residual

None blocking DDE-068. Two follow-ons are carried forward: writing this
accepted EDR as a durable row in real Project Truth (only the markdown
pre-image exists, because implementation ran against an ephemeral sandbox
database), and authoring default oracle bindings so generated screens carry
the visual checks automatically — DDE-065/067 authoring-surface territory,
inherited by DDE-069.
