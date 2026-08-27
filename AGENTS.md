# DDE — Agent Operating Rules

## What this repository is
DDE is a software manufacturing control plane. It owns product truth, mission state,
context policy, routing policy, capability governance, verification and evidence.
The authoritative specification is `docs/blueprint/REV_2_0.md`. Read the relevant
chapter before changing a contract.

## Authority — non-negotiable
1. Project Truth (constitution, approved requirements, accepted EDRs) outranks all code,
   all agent memory, and all model opinion. Never edit `docs/truth/**` as a side effect
   of implementing a task. Propose a change; do not make one.
2. The blueprint outranks convenience. If the code must diverge from the blueprint,
   stop and raise it — a divergence is an EDR, not a commit.
3. `schemas/` is the single source of truth for every contract. Never hand-edit anything
   in `engine/contracts/` — it is generated. Change the schema and regenerate.

## Boundaries — enforced by tests, do not work around them
- `engine/core/**` imports DDE contracts only. It must never import a vendor SDK.
- Vendor code lives in `adapters/**` behind the WorkerAdapter or Capability contract.
- `cursor_sdk` / `cursor-sdk-bridge` may be imported only from `adapters/cursor/**`.
- `interfaces/**` consumes the API/Gateway/MCP surface. It never touches core tables.
- Nothing except `engine/truth/**` writes to Project Truth tables.
- Nothing except `engine/capabilities/broker/**` reads secret material.

## Definition of done — all of these, every time
- [ ] Contract test exists and failed before the implementation existed.
- [ ] `just check` is green (lint, typecheck, unit, contract).
- [ ] Migration applies cleanly to an empty database and is reversible.
- [ ] New tables carry tenant_id/project_id and RLS policies where Chapter 3.2 requires.
- [ ] New async operation has a durable identity, an idempotency key and observable state.
- [ ] New side-effecting capability declares a `side_effect_class` (Chapter 9.3).
- [ ] Public behaviour change is reflected in the blueprint chapter it belongs to.
- [ ] The golden mission fixture still passes.

## Style
- Python 3.12, async throughout. No sync database calls in request paths.
- Pydantic v2 for all boundary types. Dataclasses for internal value objects.
- Errors are typed and mapped to the Chapter 15.4 error contract. Never raise bare
  Exception across a module boundary.
- Comments explain constraints, never mechanics. No narration.
- No new dependency without stating licence, maintenance signal and why the stdlib is
  insufficient (Chapter 9.6).

## Forbidden
- Introducing a second source of truth for any mutable state.
- Introducing an agent framework, graph runtime, or message bus for core state.
- Passing a long-lived credential to anything that executes model-generated code.
- Retrying a side-effecting operation without an idempotency key or a reconciliation read.
- Broadening a capability lease scope to make a test pass.
- Silently widening autonomy_level, network policy, or filesystem policy.

## When blocked
Say so, state the smallest decision that would unblock you, and stop. Do not invent a
contract. Do not implement a "temporary" alternative.

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
it says nothing about whether a blueprint chapter's MUST/shall/recovery rules are
actually wired at a production call site. Do not treat `commit_if_green` exiting
0 as chapter sign-off.
