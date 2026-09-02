# DDE Rev 3 — Canonical Resume Prompt (Consolidated)

Use this prompt when starting or resuming a DDE engineering session, coding agent, Claude Code/Cursor run, Hermes session or equivalent worker.

**This file is a bootstrap helper, not architecture authority.** The repository/Core is the memory source; historic chat is not required.

---

## Prompt

You are resuming development of **DDE — Development & Engineering Engine** in `Vanguduza/dde`.

Continue from the **actual current repository state** toward the consolidated Rev 3 architecture. Do not reconstruct the project from assumptions, model memory or historic chats.

### 1. Establish project identity and authority before touching code

Read in this order:

1. `AGENTS.md`
2. `docs/truth/BLUEPRINT_REV3.md`
3. `docs/truth/DEV_PLAN_REV3.md`
4. `docs/truth/IMPLEMENTATION_STATE.md`
5. `docs/truth/ARCHITECTURE_DECISIONS.md`
6. relevant accepted EDR pre-images under `docs/truth/edr/**`
7. relevant mission charter/chapter gate/specialist planning docs.

Accepted Project Truth/EDR records outrank all markdown. The two primary human-readable forward authorities are:

```text
docs/truth/BLUEPRINT_REV3.md
docs/truth/DEV_PLAN_REV3.md
```

`IMPLEMENTATION_STATE.md` is a projection of evidence, not target architecture. `ARCHITECTURE_DECISIONS.md` is an index. Legacy Rev 2 and standalone Rev 3 addenda are historical/reference where they conflict with the consolidated Blueprint/Plan.

Before accepting work, resolve/verify the intended project root. Do not provision DDE/Dial configuration into an unrelated project.

### 2. Verify repository state instead of trusting summaries

Before implementation:

- inspect branch and HEAD;
- inspect recent commits affecting the target gate/mission;
- inspect relevant schemas/contracts/code/tests;
- check whether `IMPLEMENTATION_STATE.md` is still accurate;
- run focused baseline tests where feasible;
- consult `docs/planning/gap-closure-record.md` before re-implementing closed infrastructure;
- identify prior evidence that remains valid and avoid blanket re-audit.

If the repo has advanced, update current state from evidence and continue from the first genuinely incomplete dependency.

### 3. Default next work — REV-3A, not DDE-068

Unless repository evidence shows REV-3A already passed, the next gate is:

**REV-3A — Operational Safety Gate**

Sequence:

```text
REV-3A.1 ProjectIdentity/bootstrap
→ REV-3A.2 StrategicOrchestratorLease safety
→ REV-3A.3 ContextBudget/ContinuationPackage
→ REV-3A.4 ChangePacket/rejection/staging guard
→ REV-3A.5 EvidenceValidity/delta audit
→ REV-3A chapter gate
→ DDE-068
```

Do not skip REV-3A to start visual/design/orchestration work unless current repository evidence proves the gate already passed.

### 4. REV-3A.1 first slice

Start by auditing current launch/config/bootstrap behavior and implementing the smallest production path for:

```text
ProjectIdentity
RuntimeRoot
SessionBootstrapContract
EffectiveExecutionConfiguration
BootstrapReceipt
```

Required proof:

- approved root resolves expected project;
- wrong/unapproved root fails closed;
- unrelated project cannot inherit DDE/Dial config;
- effective configuration is reconstructable from recorded sources/hashes;
- a session without a PASS receipt is not treated as healthy.

### 5. Models occupy roles; models are not roles

Never hard-code architecture as:

```text
Fable = strategy
Opus = specialist
Codex = coding
Sonnet = general implementation
```

Those are at most initial priors.

Target strategic occupancy semantics:

#### Fable available

```text
Fable = strategic-orchestrator occupant
Opus/Sonnet/Haiku/Codex/DeepSeek/etc remain ordinary eligible candidates
```

#### Fable unavailable and Opus selected as fallback

```text
Opus = temporary strategic-orchestrator occupant
Opus removed from ordinary worker pool while occupying
remaining certified workers continue bounded work
```

#### Fable restored

At a safe atomic checkpoint:

```text
Fable reacquires strategic lease
Opus releases lease
Opus returns to ordinary eligible worker pool
```

No premium-model creep. No stale fallback state.

### 6. Worker routing discipline

For each bounded task:

```text
TaskExecutionDescriptor
→ required capabilities
→ hard gates
→ eligible WorkerConfigurations
→ verified experience + current provider state
→ expected verified-outcome ranking
→ RouteDecision
```

Hard gates include certification, environment/security compatibility, write scope, platform support, provider health/quota, verification independence, policy and context sufficiency.

Select the cheapest certified configuration sufficiently likely to achieve the required verified outcome; a premium worker may win when reliability/rework/latency/risk justifies total effective cost.

Initial model affinities decay as verified empirical evidence accumulates.

### 7. Hermes discipline

Use Hermes for:

- context/repository scouting;
- research and provenance;
- continuation/recovery preparation;
- failure-memory retrieval;
- execution-experience retrieval;
- routing-insight candidates;
- workflow/playbook candidate discovery;
- operator assistance.

Hermes may remember, correlate and propose. DDE evaluates and governs.

Hermes memory never directly:

- rewrites Project Truth;
- promotes routing policy;
- merges/releases;
- replaces raw DDE telemetry;
- certifies itself.

### 8. Context is a runtime resource

Do not spend a session until little context remains and then start the highest-risk work.

For each significant/high-risk task, estimate safe remaining context. If below threshold:

```text
CHECKPOINT_REQUIRED / UNSAFE_FOR_HIGH_RISK_WORK
→ write ContinuationPackage
→ checkpoint workspace/change state
→ resume in fresh WorkerSession
```

A `ContinuationPackage` contains authoritative requirements/decisions, branch/base/head, working tree state, active ChangePacket, completed steps, unresolved findings, next exact action, required evidence and forbidden rework.

Do not replay entire historic chat as the default resume strategy.

### 9. ChangePacket and staging discipline

Every controlled code mutation belongs to an explicit ChangePacket/workspace.

Rejected work must be dispositioned:

```text
REJECTED
→ identify packet mutations
→ quarantine/revert/isolate
→ verify accepted baseline
→ record disposition
```

Do not leave rejected work as anonymous dirty state.

Normal controlled staging is explicit/hunk/path scoped and checked against the packet. Unexpected staged paths block the commit.

Do not use `git add -A` for an ordinary feature packet. It requires an explicit bulk-maintenance packet/override.

### 10. Evidence inheritance and delta-only auditing

Do not choose between “trust forever” and “re-audit everything”.

Previously verified evidence remains valid when no dependency/invariant it proves has changed.

A changed invariant should invalidate only dependent evidence and generate a bounded delta audit.

Do not reopen DDE-065/066/067 merely because Rev 3 documentation expanded.

### 11. DDE-068 after REV-3A

When REV-3A passes, DDE-068 is the next numbered product mission.

It must deliver a real visual verification path:

- real ProductEnvironment renderer;
- screenshot/structure/accessibility evidence;
- deterministic design checks including remaining combination/silhouette/density/reduced-motion rules;
- VLM/independent screenshot critique as evidence;
- bounded repair <= 3 cycles;
- evidence persistence;
- real promotion/quality gate consuming the verdict.

A fixture, mock, CI screenshot or badge alone is not completion.

### 12. Frontend Studio consolidated design law

Frontend Studio is a professional product-engineering workbench:

```text
Brief → Explore → References → Build → Motion → Verify → Ship
```

Claude `/design` is a first-class specialist capability behind a DDE-owned `DesignGateway`, not an architectural dependency on slash-command syntax.

For material UI work:

```text
DesignGateDecision
→ DesignGateway
→ DesignArtifact candidates
→ Try-Live isolated implementation
→ real LIVE candidate
→ refine/branch/compare
→ PROMOTE exact design/code pair
→ independent verification
```

Semantic law:

- `DESIGN` = provider artboard/artifact;
- `LIVE` = actual application code running from candidate workspace;
- `VERIFIED` = live candidate that passed applicable gates.

Never label an artboard LIVE.

Known design-token/component edits compile deterministically without spending model calls. Ambiguous/aesthetic edits may use the provider. Design provider output cannot mutate accepted/main code directly.

### 13. Execution graph / Opal-derived UX law

DDE may implement natively:

- real execution graph;
- node inspector;
- replay/reroute/fork/compare;
- workflow/playbook registry;
- policy-compiled visual Workflow Composer.

Do **not** make Opal a DDE runtime dependency.

The graph must be projected from real DDE task/session/event/evidence state. The composer must compile to the same validated workflow engine; it cannot create a second orchestrator or source of truth.

### 14. Runtime capability and update discipline

Do not assume the installed harness supports a documented feature. Discover/certify exact version-specific capabilities.

Do not blindly auto-update Hermes, Claude Code, Codex harnesses, DeepSeek, MCPs, skills or plugins. Executable updates must eventually follow the ToolUpdateManager certification/canary/rollback path. Until that path is implemented, keep known-good versions pinned/controlled.

### 15. Security invariants

Never:

- pass long-lived credentials into model-generated execution;
- add direct interface-to-Core-table access;
- import vendor SDKs into Core;
- widen egress/filesystem/autonomy silently;
- execute unclassified donor code;
- retry uncertain external effects without idempotency/reconciliation;
- export sensitive personal/project data for convenience;
- dump the whole repository into a design/model provider when exact scoped context is sufficient.

### 16. Vertical-slice implementation rule

For every slice:

1. map exact Blueprint/EDR clauses;
2. inspect existing owner/call sites first;
3. change schemas/contracts first when required;
4. create failing contract/invariant test where practical;
5. implement domain/service behavior;
6. wire real production call site;
7. wire Gateway/API/UI if applicable;
8. implement typed failure/cancel/retry/recovery/reconciliation;
9. wire telemetry/evidence;
10. run focused tests;
11. run repository-required checks;
12. perform chapter-gate production-call-site audit;
13. update `IMPLEMENTATION_STATE.md` only from evidence.

A green `just check` is necessary but is not chapter sign-off.

### 17. Completion questions

Before calling any feature complete, answer:

- Where is authoritative state?
- What is the schema/contract?
- Which service writes it?
- Which production path reads/uses it?
- What state transition occurs?
- What happens on failure/cancel/retry/recovery?
- Which capability/credential/egress boundary applies?
- What evidence proves it?
- Which UI/API path exposes it?
- Which previous evidence was inherited or invalidated?

If an applicable answer is missing, the feature remains partial.

### 18. Stop/block conditions

Stop and raise the smallest genuine blocker when:

- accepted EDR/Project Truth decision is required;
- two authoritative sources conflict;
- a required provider/capability is unavailable and no policy-safe generic path exists;
- required credential cannot be obtained through accepted broker path;
- implementation would require weakening authority/security/recovery invariants.

Otherwise continue with the smallest evidence-producing slice. Do not ask the owner to reconfirm decisions already locked by Project Truth/Blueprint/Plan.

### 19. End-of-tranche protocol

At every meaningful tranche:

1. record branch/HEAD/commits;
2. run focused/full required tests;
3. inspect actual diff/production call sites;
4. record evidence inherited vs invalidated;
5. create/update chapter gate if applicable;
6. update `IMPLEMENTATION_STATE.md` with exact state changes, call sites, evidence, residuals and next work;
7. update Blueprint/Plan only through deliberate change control when architecture/sequence changes;
8. never leave the only progress record in chat.

### 20. First response / first action

Report only evidence-backed current facts:

- current branch/HEAD;
- canonical Blueprint/Plan intact or not;
- actual current gate/mission state;
- why the target work is next;
- first vertical slice;
- genuine blocker if any.

Then execute. Do not spend the session rewriting the plan already present.

---

## End canonical resume prompt
