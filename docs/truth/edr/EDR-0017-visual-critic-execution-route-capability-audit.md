# EDR-0017 — Visual-critic execution route: capability audit finding and
# a real local route vs. EDR-0016's assumed brokered-API route

> **Location note.** Per Chapter 3.6, an EDR is a row in the `edrs` table,
> written only by `engine/truth/`. Following the convention established in
> `EDR-0001`–`EDR-0016`, this file is filed as a **markdown pre-image**
> awaiting a human decision — this session has no access to the durable
> Project Truth database (only an ephemeral, per-session sandbox instance
> used to run tests), so no `edrs` row exists for this slug yet. Do not
> treat this file as accepted; `status` below is `proposed`. Filing this
> pre-image, without self-accepting it, is itself the correct DDE-native
> response to a genuine authoritative-source conflict per
> `docs/truth/RESUME_PROMPT.md`'s own instruction: "Do not silently choose
> a convenient document when sources conflict. Identify the conflict and
> use the EDR/change-control path if the authoritative contract must
> change."

- **slug:** `EDR-0017`
- **status:** `proposed`
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

## Decision (proposed)

Recommend **(b)** as the smallest safe next step consistent with "do not
require a new paid API merely because that is the easiest conventional
solution" and DDE's own preference for reusing already-admitted machinery
over inventing parallel architecture — while being explicit this is a
recommendation, not a self-acceptance. The deciding human may instead pick
(a), (c), a hybrid, or reject this filing outright.

If (b) is accepted, the concrete follow-on implementation (not done by this
filing) is:

1. A `_run_visual_critique` executor in `engine/verification/checks.py`
   analogous to this tranche's `_run_silhouette`, but its capability
   dependency is `ClaudeCodeWorkerAdapter`/`ApprovalService.require_approved`
   (EDR-0001's existing gate) rather than `BrowserCapability` alone — it
   still needs the browser capability first, to get the screenshot to hand
   the CLI.
2. A structured critique schema (verdict, confidence, defect categories,
   repair instructions, blocking/non-blocking split) under `schemas/design/`
   per EDR-0016 decision 3's existing rubric-storage plan (unaffected by
   this amendment).
3. The bounded-revision state machine (cycle counter capped at 3, escalate
   to the approvals surface past the bound) as a DDE-native orchestration
   loop — real code, testable with the adapter's own established
   fake-binary-double pattern
   (`tests/unit/test_claude_adapter_requires_approval.py`'s convention) for
   fast, deterministic, no-live-cost tests, with the real live path
   exercised only under an actual human-granted `Approval` in a real
   deployment, never fabricated or run unattended by an agent session on
   the human's behalf.
4. Believable-density's rubric dimension rides the same critique response
   (playbook §8.3: `"believable-density >= 4"` is a scored field oftteh
   same structured critique output, not a separate call).

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
  be built against. No implementation in this tranche invokes
  `capability.claude_code_invoke` live — doing so before this EDR is decided
  would spend the human's own subscription-seat quota on an architecture
  decision they have not yet made, which is exactly what EDR-0001's
  per-invocation approval gate exists to prevent an agent from doing
  unilaterally.
