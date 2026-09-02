# DDE — Agent Operating Rules (Rev 3 Consolidated)

## What this repository is

DDE is a governed software-manufacturing control plane. It owns product truth, mission state, context policy, routing policy, capability governance, change ownership, verification and evidence.

Models/harnesses/design providers are replaceable workers or capabilities. They never become the source of truth.

---

## Canonical Rev 3 bootstrap — read before changing code

The repository, not chat history/model memory, is the project memory layer.

Read in this order:

1. `docs/truth/BLUEPRINT_REV3.md` — **primary canonical human-readable architecture**.
2. `docs/truth/DEV_PLAN_REV3.md` — **primary canonical forward implementation sequence/gates**.
3. `docs/truth/IMPLEMENTATION_STATE.md` — evidence-backed current-state projection.
4. `docs/truth/ARCHITECTURE_DECISIONS.md` — readable decision index; accepted EDRs outrank it.
5. relevant accepted EDR pre-images under `docs/truth/edr/**`.
6. relevant mission charter/chapter-gate/specialist planning docs.

`docs/truth/RESUME_PROMPT.md` is the bootstrap helper for fresh sessions.

`docs/blueprint/REV_2_0.md` and standalone Rev 3 amendments/addenda are historical/reference where they conflict with the consolidated Blueprint/Plan.

Accepted Project Truth rows written through `engine/truth/**` outrank every markdown document.

---

## Immediate forward-work rule

Unless repository evidence shows it has already passed, the next implementation gate is:

```text
REV-3A Operational Safety Gate
  1. ProjectIdentity/bootstrap
  2. strategic-orchestrator occupancy safety
  3. ContextBudget/ContinuationPackage
  4. ChangePacket/rejection/staging guard
  5. evidence validity/delta audit
→ DDE-068
```

Do **not** resume directly at DDE-068 merely because older state/resume text said it was next.

---

## Authority — non-negotiable

1. Project Truth/accepted EDRs outrank code, markdown summaries, model memory and agent opinion.
2. `BLUEPRINT_REV3.md` defines the human-readable architecture; `DEV_PLAN_REV3.md` defines implementation order/gates.
3. `IMPLEMENTATION_STATE.md` may not promote a feature without production call-site + verification evidence.
4. `schemas/**` remains SSOT for generated contracts. Never hand-edit generated `engine/contracts/**`.
5. No model/harness may directly mint authoritative mission/task/design/workflow state outside DDE's accepted promotion path.
6. Interfaces are clients of Core/Gateway. They never become a second mutable-state authority.

A material divergence from a locked contract/security/authority boundary is an EDR/change-control event.

---

## Project identity / bootstrap discipline

Before provisioning project-specific configuration or accepting work:

- resolve intended RuntimeRoot/ProjectIdentity;
- verify the root/project relationship;
- load only authorized configuration sources;
- make effective configuration reconstructable;
- fail closed for unrelated/wrong roots.

Never inject DDE/Dial project configuration into an unrelated repository simply because the current working directory happens to expose a config file.

During REV-3A, follow the Blueprint/Plan even where the full native `BootstrapReceipt` runtime is not yet complete.

---

## Model/orchestration discipline

**Models occupy roles; models are not roles.**

Do not hard-code permanent jobs such as `Fable=strategy`, `Opus=specialist`, `Codex=coding`.

Locked target semantics:

### Fable available

```text
Fable = strategic-orchestrator occupant
ordinary candidates may include Opus/Sonnet/Haiku/Codex/DeepSeek/others
```

### Fable unavailable and Opus selected as fallback

```text
Opus = temporary strategic-orchestrator occupant
Opus removed from ordinary worker pool while occupying
remaining certified workers continue routine work
```

### Fable restored

At a safe atomic checkpoint:

```text
Fable reacquires strategic lease
Opus releases lease
Opus returns to ordinary eligible worker pool
```

No premium-model creep and no stale fallback state.

Routing hard-gates candidates before optimizing verified outcome/cost/latency/rework/risk. Initial model preferences are priors only and must decay as empirical evidence accumulates.

---

## Hermes discipline

Hermes is preferred for persistent research/context/continuity/experience intelligence:

- repository reconnaissance;
- evidence gathering;
- bounded context preparation;
- dependency/license research;
- failure/recovery memory;
- ExperienceScout-style retrieval;
- routing/playbook insight candidates;
- operator assistance;
- provenance/continuation support.

Hermes may remember, retrieve, correlate and propose. DDE governs.

Hermes memory may not directly rewrite Project Truth, promote routing/workflow policy, merge/release, replace authoritative telemetry or self-certify.

---

## Context discipline

Context is a runtime resource.

Do not consume most of a session and then begin the highest-risk work.

If context is pressured/unsafe for high-risk work:

```text
checkpoint
→ write/refresh ContinuationPackage
→ record active change/evidence state
→ resume in a fresh session
```

Do not use full historic chat/repository dumps as the default context strategy.

Previously verified evidence remains valid unless a changed dependency/invariant invalidates it. Do not blanket re-audit closed work.

---

## ChangePacket / workspace / staging discipline

Every controlled mutation belongs to explicit task/run/workspace ownership.

During/after REV-3A, this is represented by `ChangePacket`/write-scope/staging contracts. Before the native contracts are complete, apply the same operational discipline manually.

### Rejected work

`REJECTED` means mutations are identified and dispositioned (quarantine/revert/isolate), then the accepted baseline is checked. Do not leave rejected edits as anonymous dirty state.

### Staging

Normal feature work uses explicit path/hunk-scoped staging and inspects the staged diff.

**Do not use `git add -A` for ordinary controlled work.** Broad staging requires an explicit bulk-maintenance packet/owner-authorized exception and full staged-diff review.

Any unexpected staged path blocks the commit.

### Existing commit helper warning

`scripts/commit_if_green.ps1` and `scripts/commit_if_green.sh` predate the consolidated ChangePacket/staging rule. They may be used only when their actual staging behavior is compatible with the packet scope or when the work is explicitly classified as an authorized bulk-maintenance packet. They are **not** permission to sweep unrelated/rejected changes into a commit.

REV-3A must harden/replace the staging behavior so the helper verifies declared/staged scope.

---

## Boundaries — enforced, do not work around them

- `engine/core/**` imports DDE contracts only; no vendor SDK.
- Vendor code lives in `adapters/**` behind accepted worker/capability/design-provider contracts.
- `interfaces/**` consumes API/Gateway/MCP; it never touches Core tables directly.
- Nothing except `engine/truth/**` writes Project Truth.
- Nothing except the accepted capability/credential broker path reads secret material.
- Worker environments receive no ambient long-lived credentials.
- Network egress is deny-by-default and capability-admitted.
- Side effects require durable identity/idempotency/reconciliation semantics.

---

## Frontend Studio / Claude Design discipline

Claude `/design` is a first-class **specialist capability behind DDE DesignGateway**, not an authority or magic frontend button.

For material UI work:

```text
DesignGateDecision
→ DesignArtifact candidate(s)
→ isolated Try-Live implementation
→ real application LIVE candidate
→ refine/branch/compare
→ PROMOTE exact design/code pair
→ verification
```

Semantic states:

- `DESIGN` = provider artboard/design artifact;
- `LIVE` = actual application code running from an isolated candidate workspace;
- `VERIFIED` = live candidate that passed required gates.

Never label provider artboards LIVE.

Known design-system edits should compile deterministically rather than call AI for every token change.

Provider context must be minimal/allowlisted. Never export secrets, production user records, credentials, unrelated private docs or unrelated repository content for design convenience.

---

## Execution Graph / Workflow Composer discipline

The Execution Graph is a projection of **actual DDE runtime state**, not a manually maintained idealized diagram.

Node inspection/replay/reroute/fork/compare must preserve lineage and policy.

Reusable playbooks express capabilities/constraints rather than permanently pinning yesterday's model winner.

The visual Workflow Composer is a compiler front-end to DDE's validated workflow engine. It may not create a second orchestrator, duplicate TaskGraph truth, remove mandatory gates without policy or mutate Project Truth because a graph contains an agent/memory node.

Do not introduce Google Opal as a DDE core runtime dependency.

---

## Runtime capability / update discipline

Do not assume a harness supports a feature merely because vendor documentation says the product can. Discover/certify the exact installed version before production reliance.

Do not blindly auto-update executable tooling, including Hermes, Claude Code, Codex harnesses, DeepSeek, MCP servers, skills or plugins.

Until ToolUpdateManager is implemented, use controlled/pinned known-good versions. Later updates must follow quarantine → certification → canary → promotion with rollback.

---

## Definition of Done — every applicable item

- [ ] Authority/source is unambiguous.
- [ ] Contract change starts from schema/accepted contract owner.
- [ ] Contract/invariant test failed before implementation where practical.
- [ ] Real production writer and reader/call site exist.
- [ ] Async/side-effect operation has durable identity/idempotency/reconciliation.
- [ ] State machine includes failure/cancel/retry/recovery.
- [ ] Capability/credential/network/data-egress rules are enforced.
- [ ] Real telemetry/evidence is persisted.
- [ ] UI/API exposes honest backed state where applicable.
- [ ] Relevant previous evidence is explicitly inherited or invalidated.
- [ ] `just check` / required repo checks are green.
- [ ] Migration applies/reverses where applicable.
- [ ] Golden fixture/mission remains green where relevant.
- [ ] Chapter gate maps MUST/SHALL clauses to production call sites.
- [ ] `IMPLEMENTATION_STATE.md` is updated after a meaningful tranche.

A green test suite is necessary but is not chapter sign-off.

---

## Style

- Python 3.12, async request paths.
- Pydantic v2 for boundary types; dataclasses for internal values where appropriate.
- Typed errors across module boundaries; no bare `Exception` contract.
- Comments explain constraints, not mechanics.
- No new dependency without license, maintenance signal and reason stdlib/current stack is insufficient.

---

## Forbidden

- second source of truth for mutable state;
- external framework/agent graph owning Core state;
- any model/harness/design provider owning mission/truth/approval/completion authority;
- long-lived credentials in model-generated execution;
- direct interface→Core-table mutation;
- blind retry of uncertain external side effects;
- widening capability/autonomy/network/filesystem scope to make tests pass;
- fabricated UI rows/status/quality;
- documentation-only capability closure;
- static model-role architecture;
- broad staging that can sweep unrelated/rejected work;
- blanket re-audit of unaffected verified work;
- provider artboards labelled LIVE;
- decorative execution graphs disconnected from runtime;
- blind executable-tool auto-update.

---

## Gap-closure record

Before re-implementing previously audited infrastructure, read `docs/planning/gap-closure-record.md` and the relevant chapter gate. Preserve closed evidence unless the current delta invalidates it.

---

## When blocked

Raise the smallest real blocker when an accepted EDR/Project Truth decision is required, authoritative sources conflict, an essential capability/credential cannot be obtained through accepted policy, or progress would require weakening an invariant.

Otherwise execute the smallest evidence-producing vertical slice already authorized by the Blueprint/Plan.
