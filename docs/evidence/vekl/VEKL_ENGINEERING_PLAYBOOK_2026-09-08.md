# Production VEKL engineering playbook — 2026-09-08

## Status

`IMPLEMENTED_PARTIAL` — the reusable engineering patterns requested from the DDE/DIAL
library and current first-party Anthropic Claude Code guidance have been normalized into
DDE-owned Production VEKL resources and policy. This tranche does not declare DDE-082 or
Production VEKL complete.

## Research inputs and authority boundary

Library inputs mined for reusable patterns included:

- `DDE_PRODUCTION_VEKL_ARCHITECTURE_v1.md` — qualified-resource hierarchy, minimal
  activation, Hook IR, bounded loops, evidence-first completion, provider neutrality and
  hard separation between knowledge/install/execute authority;
- `VEKL_IMPLEMENTATION_MISSION_PLAN.md` — P4-P10 task signature, activation, executable
  resource, loop, Studio and production-certification gates;
- `DIAL_GOOGLE_SKILLS_VERSIONED_ENGINEERING_KNOWLEDGE_LAYER_AND_HERMES_ORCHESTRATION_v1.md`
  — canonical-context-first selection, task classification, hard filters, mandatory
  activation, minimal 1-3 skill target, immutable activation manifests and guard capsule;
- the DDE master technical blueprint — DDE authority, independent verification, bounded
  autonomy and worker/harness replaceability.

Current Anthropic material was re-checked on 2026-09-08 against the first-party Claude Code
Best Practices, Skills, Hooks and Subagents documentation. Useful patterns adopted include
executable verification, explore/plan/implement separation when warranted, concise global
instructions with conditional knowledge in Skills, isolated research, restart after two
failed corrections, worktree-isolated fan-out, fresh-context adversarial review, explicit
Skill invocation control and deterministic hook events.

These sources are research/provenance, not Project Truth. No Anthropic documentation host
was admitted to DDE egress by this work and no provider prompt text is copied verbatim into
runtime authority.

## DDE-owned engineering resource pack

`engine.vekl.engineering_playbook` now defines:

- 16 content-addressed DDE Skills;
- 14 explicit engineering task archetypes layered over canonical `Task.task_class`;
- 12 verification-gate requirements;
- 7 harness-neutral hook-policy definitions;
- a three-Skill maximum per archetype, including any required fresh reviewer;
- deterministic policy for planning, investigation context, parallelism, fresh-start,
  independent review and completion.

The policy guard capsule states that engineering guidance is non-authoritative, Project
Truth wins, architecture/gates cannot be changed by the guidance, secrets are not implied,
scope cannot be thinned and verifiers cannot be tampered with.

`TaskSignatureSpec.engineering_archetype` is optional and explicit. DDE does not guess an
archetype merely to make routing convenient. If selected, the compiled policy is stored in
existing `TaskSignature.constraints`, so no second task/orchestration ledger is introduced.

## Skill qualification and activation

`vekl.playbook.install_candidates` registers the exact DDE engineering playbook revision
as local `VEKLResource(resource_kind=SKILL)` candidates for a target application. The
command:

- has no network side effect;
- sets no external `source_uri`;
- grants no capability or secret scope;
- leaves resources candidate-only (`DISCOVERED`);
- is target-app scoped through the existing VEKL resolver.

When an engineering archetype is bound, its Skill IDs must resolve to the exact playbook
revision and `PROCEDURAL_GUIDANCE` mode. The selected resources are made mandatory inputs
to the existing eligibility/ranking pass and therefore still must satisfy lifecycle,
provenance, budget, revocation and other VEKL gates. Missing/wrong-revision/unqualified
Skills fail closed rather than silently falling back to model recall or another Skill.

## Completion and review policy

The playbook's completion gates do not grade code themselves. They consume attestations
from the existing AcceptanceOracle / VerificationRun / Evidence authority. Worker prose
cannot close a required gate.

Policy includes:

- direct execution for genuinely small/clear archetypes where planning overhead is not
  justified;
- required planning for migration, security/remediation, release, incident and bulk work;
- conditional planning for high-risk, cross-module or large tasks;
- isolated investigation context for orientation/debug/performance work;
- fresh-start policy after two failed corrections on the same issue;
- fresh-context adversarial review for high-risk/unattended work and always for
  migration/security/release/bulk archetypes;
- disjoint-worktree-only parallel writes for bulk migration;
- evidence-backed requirement, regression, root-cause, migration, security, visual,
  performance and release gates.

## Claude Code materialization

`adapters.claude.vekl` converts only already-selected DDE artifacts into provider delivery
formats:

- DDE Skill → `.claude/skills/<id>/SKILL.md`;
- Instruction IR → generated `CLAUDE.md` text carrying truth/policy/instruction hashes;
- concrete command Hook IR → semantics-preserving `.claude/settings.json` hook structure.

Generated Skills set `disable-model-invocation: true` and intentionally omit
`allowed-tools`. Claude therefore cannot independently choose a Production VEKL Skill or
receive tool authority from the generated Skill. Capability/lease policy stays in DDE.

Claude hook mappings currently cover `PreToolUse`, `PostToolUse`, `Stop` and
`TaskCompleted`; events that do not support matchers are emitted without a matcher field.
Only concrete command Hook IR entries are materialized. DDE-capability hooks remain in the
native `LeaseBoundHookRuntime` so provider settings cannot bypass capability leases or
ExternalEffect journaling.

Provider hooks are defense in depth, not a security boundary. Hard scope, effect and
completion rules remain DDE-native even if a provider hook is unavailable or weaker.

## Verification executed

Focused playbook/runtime/contract coverage proves resource authority, deterministic hashes,
archetype/task-class compatibility, risk-driven planning, two-failure fresh-start policy,
fresh review, migration/bulk policy, TaskSignature/context binding, exact Skill resolution,
wrong-revision and missing-Skill refusal, activation-mode refusal, Hook IR safety, Claude
Skill authority, Claude instruction rendering, global-vs-matched hook emission and
evidence-backed completion. A task-signature change on an existing activation attempt now
invalidates the prior manifest with `VEKL_TASK_SIGNATURE_CHANGED` rather than silently
rehydrating engineering knowledge under a changed policy. Its PostgreSQL proof is committed
as an integration test for the service-capable gate.

Executed on this host:

- focused VEKL/playbook/contract: **54 passed**;
- pure unit: **731 passed, 5 skipped, 562 integration deselected**;
- contract: **223 passed**;
- strict MyPy: **581 source files, no issues**;
- Ruff check + format check: PASS;
- generated contracts, design tokens and binding-matrix drift: PASS;
- design-lint ratchet: PASS at the committed DD206 budget of 70 (no increase);
- DDE Studio extension/shared suite: **77/77 passed**;
- desktop TypeScript check: PASS;
- UI TypeScript check + React/Vite production build: PASS;
- Frontend Studio Playwright: **79/79 passed**.

The local shell remains service-free, but the service-capable GitHub Actions gate has now
closed the database evidence that was previously unavailable here. CI run `34234702640`
provisioned PostgreSQL and Redis, executed a live Alembic `head -> base -> head` cycle
(including `0038 -> 0037` and the final `0037 -> 0038`), then completed **1550 passed /
7 skipped** across unit+contract+recovery, including **6/6** Production VEKL PostgreSQL
tests, followed by **5/5** integration tests and a clean generated-drift gate. The Windows
job in the same run passed **731 / 5 skipped / 562 deselected**, Ruff/format and strict
MyPy across 581 source files. This closes the basic PostgreSQL persistence/recovery and
reversible-0038 evidence gates; it does not imply that every DDE-082 executable adapter or
DDE-083 release-environment certification is complete.

## Remaining mission ownership

This work closes the engineering-playbook substrate requested for Production VEKL but does
not close DDE-082. Remaining DDE-082 scope still includes the complete operator authoring
surface, generalized certified workflow/playbook lifecycle, full qualified tool/plugin/MCP/
LSP adapter fleet, and end-to-end orchestration consumption of every policy transition.
DDE-083 retains release-environment adversarial, supply-chain, cross-project, migration and
learning-poisoning certification.
