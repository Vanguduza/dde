# DDE — Agent Operating Rules

## What this repository is
DDE is a software manufacturing control plane. It owns product truth, mission state,
context policy, routing policy, capability governance, verification and evidence.

## Rev 3 bootstrap — read before changing code
The repository, not chat history or model memory, is the project memory layer. Read in
this order before starting or resuming implementation:

1. `docs/truth/BLUEPRINT_REV3.md` — canonical human-readable product/technical architecture.
2. `docs/truth/ARCHITECTURE_DECISIONS.md` — readable locked decision index; accepted EDR rows outrank summaries.
3. `docs/truth/DEV_PLAN_REV3.md` — canonical delivery sequence and gates.
4. `docs/truth/IMPLEMENTATION_STATE.md` — evidence-based current implementation state and next packet.
5. The relevant accepted EDR pre-images in `docs/truth/edr/**` and mission planning/chapter-gate documents.

`docs/truth/RESUME_PROMPT.md` is the canonical prompt for starting a fresh engineering
session without the historic ChatGPT thread.

`docs/blueprint/REV_2_0.md` is retained as historical/reference depth. It is no longer
the forward-development authority. Where it conflicts with Blueprint Rev 3, use Rev 3
unless an accepted Project Truth record decides otherwise.

## Authority — non-negotiable
1. Project Truth (constitution, approved requirements, accepted EDRs) outranks all code,
   all markdown summaries, all agent memory, and all model opinion. Never edit
   `docs/truth/**` as an incidental side effect of implementing an ordinary task. Change
   these controlled artifacts only when the task explicitly requires truth/state/plan
   maintenance or an accepted decision requires synchronization.
2. `docs/truth/BLUEPRINT_REV3.md` outranks convenience and legacy Blueprint Rev 2 for
   forward work. If code must diverge from a locked contract, stop and raise it — a
   material divergence is an EDR/change-control event, not a convenient commit.
3. `schemas/` is the single source of truth for every generated contract. Never hand-edit
   anything in `engine/contracts/` — it is generated. Change the schema and regenerate.
4. `docs/truth/IMPLEMENTATION_STATE.md` describes what is actually implemented. Do not
   promote a feature's state without production call-site and verification evidence.

## Boundaries — enforced by tests, do not work around them
- `engine/core/**` imports DDE contracts only. It must never import a vendor SDK.
- Vendor code lives in `adapters/**` behind the WorkerAdapter or Capability contract.
- `cursor_sdk` / `cursor-sdk-bridge` may be imported only from `adapters/cursor/**`.
- `interfaces/**` consumes the API/Gateway/MCP surface. It never touches core tables.
- Nothing except `engine/truth/**` writes to Project Truth tables.
- Nothing except `engine/capabilities/broker/**` reads secret material.

## Definition of done — all of these, every time
- [ ] Contract test exists and failed before the implementation existed, where practical.
- [ ] `just check` is green (lint, typecheck, unit, contract).
- [ ] Migration applies cleanly to an empty database and is reversible.
- [ ] New tables carry tenant_id/project_id and RLS policies where the blueprint requires.
- [ ] New async operation has a durable identity, an idempotency key and observable state.
- [ ] New side-effecting capability declares a `side_effect_class`.
- [ ] Public behaviour change is reflected in the applicable Rev 3 architecture/decision/plan artifact through proper change control.
- [ ] The golden mission fixture still passes.
- [ ] A real production call site invokes the new behavior; schemas/stubs/tests alone are not completion.
- [ ] `docs/truth/IMPLEMENTATION_STATE.md` is updated after a meaningful implementation tranche.

## Style
- Python 3.12, async throughout. No sync database calls in request paths.
- Pydantic v2 for all boundary types. Dataclasses for internal value objects.
- Errors are typed and mapped to the canonical error contract. Never raise bare
  Exception across a module boundary.
- Comments explain constraints, never mechanics. No narration.
- No new dependency without stating licence, maintenance signal and why the stdlib is
  insufficient.

## Forbidden
- Introducing a second source of truth for any mutable state.
- Introducing an agent framework, graph runtime, or message bus for core state.
- Allowing Fable, Hermes, Claude Code, DeepSeek, Cursor or any other harness to own authoritative mission/truth state.
- Passing a long-lived credential to anything that executes model-generated code.
- Retrying a side-effecting operation without an idempotency key or a reconciliation read.
- Broadening a capability lease scope to make a test pass.
- Silently widening autonomy_level, network policy, or filesystem policy.
- Treating UI presence, a schema enum, a fixture, a prompt, or a planning document as proof of implemented production behavior.
- Fabricating rows/status/quality results in DDE Code when the backing contract/data does not exist.

## Worker/orchestration discipline
- DDE owns state and governance. External harnesses are replaceable workers.
- Fable 5 is the preferred strategic orchestration worker only when a real supported adapter/interface exists and is evaluated; never invent one.
- Hermes is preferred for persistent research, reconnaissance, context preparation, dependency intelligence, failure triage/recovery preparation and operator assistance; Hermes memory is not authoritative.
- Premium coding/reasoning workers are escalation resources for tasks where quality materially changes outcomes, not default dispatch/crawl/monitor workers.
- Lower-cost workers are valid for bounded/mechanical work when deterministic verification can arbitrate quality.
- High-risk implementation should receive independent review or deterministic oracle coverage.

## When blocked
Say so, state the smallest decision that would unblock you, and stop. Do not invent a
contract. Do not implement a "temporary" alternative that weakens authority, security or
recovery semantics.

## Gap-closure record (read before re-implementing infrastructure)
`docs/planning/gap-closure-record.md` is the authoritative log of which
infrastructure gaps (repo hygiene, Windows dev loop, CLI `--json`, dde-studio
Gateway client, telemetry/adapter/certification state, Frontend Studio
distinctiveness / design-tooling harvest) were audited, closed, or left open
with named owners. Check it before implementing any of those; do not duplicate
closed items and do not silently close owner-named ones. Design-tooling
disposition (encode concepts into DDE-065/067/068; do not install third-party
design skills as oracles): `docs/planning/design-tooling-integration.md`
(§6.10). DDE-066 donor-search egress is admitted by EDR-0015; implementation
is `DonorDiscoveryService.search` (not the DDE-067 GUI).

## Mechanical commit helpers
`scripts/commit_if_green.ps1` (Windows) and `scripts/commit_if_green.sh` (Linux/
Codespaces/CI) run the exact check list from the justfile `check` recipe (`ruff
check`, `ruff format --check`, `mypy`, `pytest tests/unit tests/contract
tests/recovery`, `generate_contracts --check`, `pytest tests/contract`) and, only
if every check passes, stage changes, commit with a caller-supplied message, and
push to the current branch's upstream (creating it with `-u origin HEAD` on first
push) — one invocation instead of separate lint/typecheck/test/add/commit/push
calls. They fail fast with no git operations at all on the first failing check,
and refuse to create an empty commit if nothing is staged.

These scripts automate **only** the mechanical "run checks, then commit+push"
step. They are explicitly invoked, never a git hook, and they are **not** a
substitute for the independent blueprint chapter-gate review that
`.cursor/rules/mission-chapter-gate.mdc` requires before any chartered DDE-N
mission can be declared done. A green exit from either script means CI is green;
it says nothing about whether the applicable Rev 3 MUST/SHALL/recovery rules are
actually wired at a production call site. Do not treat `commit_if_green` exiting
0 as chapter sign-off.