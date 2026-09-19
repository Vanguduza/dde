# EDR-0019 — DDE Cross-System Operational Intelligence and Execution Hardening

> **ACCEPTED 2026-09-19 by explicit project-owner instruction:** *"Review and integrate this document into dde fully using your best recommendations where owner decisions are needed"*, supplied together with the owner-exported artifact `DDE_DIAL_HERMES_VAN_CROSS_SYSTEM_INTEGRATION_BLUEPRINT_2026-09-19.md`. This EDR is the repository-readable acceptance record. The authoritative durable Project Truth row must be provisioned through the ordinary TruthService acceptance path in service-capable environments; CI/provisioning tests must prove that row before any behaviour below is considered enabled in production.

- **slug:** `EDR-0019`
- **status:** `accepted (2026-09-19)`
- **supersedes/amends:** additive. Amends nothing. Extends AD-048/AD-050 and EDR-0015/EDR-0018 without widening their egress or source authority.
- **scope:** DDE-native contracts, persistence and governance for twelve operational-intelligence and execution-hardening capabilities. Contract and persistence phases only; no runtime service is authorized as complete by this record.

## Source artifact and the repository firewall

`AGENTS.md` forbids DDE work from cloning, fetching, inspecting, comparing, binding or importing `Vanguduza/dial-new`, `Vanguduza/dial` or any sibling runtime, and requires that cross-project transfer arrive as **an owner-supplied exported artifact admitted through normal source controls**. The integration blueprint is exactly that artifact. It was treated as a design/provenance input and nothing else:

- no DIAL, Hermes or VAN repository was read, fetched or compared during this work;
- no DIAL/VAN runtime package, database, table, control API or Hermes profile is imported, referenced or depended upon;
- every capability below is re-derived as a DDE-native contract under DDE namespaces, bound to existing DDE authorities, and independently versioned.

The blueprint's own §2.2/§2.3 require the same thing. Where the blueprint and `AGENTS.md` agree, `AGENTS.md` governs.

## Decision

DDE adopts twelve capability patterns as **additive extensions of existing DDE authority seams**. No imported behaviour becomes a second authority for Project Truth, task identity, mission state, capability grants, workspace write ownership, verification, release state, VEKL qualification or evidence promotion. Each capability terminates in an existing DDE Core authority.

| Epic | Capability | Terminates in |
| --- | --- | --- |
| A | Live mission steering at a safe boundary | Mission/Task authority, write-ownership leases, TruthService |
| B | Provider readiness and execution placement evidence | Existing routing authority, `provider_capacity_snapshots` |
| C | Open-world discovery candidate lifecycle | Source Intelligence (`source_records`/`source_admissions`), `vekl_resources` |
| D | Ahead-of-work research missions with measurable coverage | VEKL admission, `vekl_research_findings` |
| E | Research Observatory delta reporting | Projection over Epic D; no new truth |
| F | Verified external action postconditions | `external_effects`, verification/evidence authority |
| G | Capability readiness and external gates | Capability authority, evidence freshness |
| H | Epistemic context facts | ContextPackage compiler (DDE-080) |
| I | Operator attention plane | Existing governance `attention_items` |
| J | Governed automation runtime | `CapabilityLease`/`ExternalEffect`/verifier law |
| K | Browser intelligence capability | Capability lease law; never verification authority |
| L | Development capability bootstrap/certification | Environment/capability evidence |

### Mission numbering

`DEV_PLAN_REV3.md` locks DDE-068 through DDE-083 and states they must not be renumbered. This programme therefore creates **no new mission number**. It is an overlay on locked missions, following the AD-050 / EDR-0018 precedent: DDE-069 (Studio projection), DDE-075, DDE-076, DDE-077, DDE-080, DDE-081, DDE-082 and DDE-083 retain ownership of their surfaces.

## Owner decisions taken under this acceptance

The instruction delegated the owner calls the blueprint left open. Each was decided against observed repository state, not against the blueprint's description of that state. Where the blueprint's recommendation was **rejected**, the reason is a conflict with something already in DDE.

### 1. Base commit — build after `0040`, not beside it *(blueprint §16.1, followed)*

Work is based on `feat/vekl-automation-corpus-runtime-20260916`, measured at 42 commits ahead of and 0 behind `main`. That branch owns migration `0040` and the domain-neutral `SourceRecord`/`SourceArtifact`/`SourceAdmission` base that Epic C's admission bridge requires. Basing on `main` would have produced a second Alembic head at `0039` and a parallel Source Intelligence surface.

### 2. Source trust vocabulary — **blueprint recommendation rejected** *(§6.3)*

The blueprint proposes a new six-value trust vocabulary (`PROJECT_LOCAL`, `FIRST_PARTY_OFFICIAL`, `MAINTAINER_PRIMARY`, `WELL_CORROBORATED_SECONDARY`, `COMMUNITY_SIGNAL`, `UNKNOWN`). DDE already carries a canonical source-trust vocabulary on `vekl_resources.source_trust`: `S1_NORMATIVE … S8_UNTRUSTED`. Introducing a second vocabulary would create a second trust authority — the precise failure the blueprint's own §2.1 and §29 forbid.

**Decision:** discovery and qualification reuse `S1..S8` unchanged. The blueprint's instruction to "use DDE-native source trust vocabulary" is honoured by using the one that exists. `T0_DIAL_PROJECT` is not introduced, as the blueprint also requires.

### 3. Discovery lifecycle — scoped to pre-admission *(§6.3, narrowed)*

`vekl_resources.lifecycle_state` already exists and is **already independent of** `source_trust`, so DDE already implements the blueprint's two-axis law for qualified resources. The genuine gap is that *pre-admission candidates* have no lifecycle at all.

**Decision:** `DiscoveryCandidate.lifecycle_state` covers the pre-admission stages only and terminates by bridging into `SourceRecord`/`SourceAdmission`/`VEKLResource`, where the existing resource lifecycle takes over. The two-axis law is restated as an invariant, not as a duplicated enum.

### 4. `ExternalEffect` status — **blueprint recommendation rejected** *(§9.2)*

The blueprint proposes replacing the effect status enum with `PREPARED/SENT/ENGINE_REPORTED_SUCCESS/VERIFYING/VERIFIED/PARTIAL/UNVERIFIABLE/FAILED/UNKNOWN`. The existing enum is `PREPARED/SENT/CONFIRMED/FAILED/UNKNOWN/RECONCILING/RECONCILED` and is load-bearing in `engine.recovery`: `CONFIRMED`, `RECONCILING` and `RECONCILED` carry reconciliation law that the proposed enum deletes. Mutating it is a breaking change to recovery semantics.

**Decision:** `status` is left untouched and keeps its transport/recovery meaning. A separate, additive **postcondition axis** is introduced (`postcondition_policy`, `postcondition_state`, `postcondition_verified_at`) plus an `ExternalEffectVerification` observation record. The blueprint's §9.2 explicitly permits "add **or project**"; this takes the projection path. The completion law is preserved in full: a task depending on an external mutation may not reach `COMPLETED` while a required postcondition is `REQUIRED_PENDING`, `VERIFYING`, `UNVERIFIABLE` or `REFUTED`.

Note that the blueprint's §9.4 names a task state `COMPLETE_EVIDENCED`. The real `tasks.status` enum has no such value; the law is bound to `COMPLETED`.

### 5. Steering holds — **blueprint recommendation rejected** *(§4.3 step 4)*

The blueprint marks affected tasks `STEERING_HELD`. `tasks.status` is a core state machine with seventeen values and no such state.

**Decision:** no value is added to `tasks.status`. The hold is recorded on `SteeringImpact.hold_state`, which the scheduler consults for eligibility. This keeps the core task state machine unwidened while the steering runtime does not yet exist. *Alternative for a later owner call:* if operator projections prove that holds must be visible directly on the task row, adding `STEERING_HELD` to `tasks.status` is a task-state-machine change requiring its own change-control record.

### 6. Attention — **blueprint table set rejected** *(§17.6)*

The blueprint proposes `attention_candidates`, `attention_items`, `attention_actions`, `attention_preferences`. DDE **already has** `attention_items`, owned by `engine.governance`, as the durable attention write that Mission Control projects.

**Decision:** `attention_items` is untouched and remains the attention authority. Only the missing layer is added — `AttentionCandidate` (scoring, dedupe key, budget disposition) and `AttentionPreference` (budget, quiet hours). `attention_actions` is dropped: acknowledgement already exists on `attention_items`, and the audit trail already exists in `audit_events`.

### 7. Provider readiness — additive, and Epic B is partly blocked *(§5.2, corrected)*

The blueprint instructs Epic B to "extend existing fleet contracts" and names `HarnessInstallation`, `HarnessRuntimeCapabilities`, `ModelControlCapabilities`, `WorkerConfiguration`, `WorkerProfileCertification`, `TaskExecutionDescriptor` and `ExecutionStrategy`. **None of these exist as contracts.** They are Blueprint Rev 3 designs owned by the unimplemented DDE-076/DDE-077; `IMPLEMENTATION_STATE.md` carries no rows for either. `ChangePacket` and `WorkspaceLease`, listed in the blueprint's §0 as existing DDE strengths, are likewise unbuilt.

**Decision:** `ProviderReadinessSnapshot` and `ExecutionPlacementDecision` are self-standing and forward-compatible, referencing a descriptor by an untyped `*_ref` until DDE-076/077 land the real contracts. Readiness is explicitly **not** capacity: `provider_capacity_snapshots` remains the availability/quota authority and is referenced, not restated. The deeper fleet integration the blueprint describes is **blocked on DDE-076/077** and is recorded as such rather than claimed.

### 8. Research findings — reuse, not duplicate *(§7.2, narrowed)*

`vekl_research_findings` already exists as the typed, source-admitted, never-authoritative research result. The blueprint's `ResearchFinding` and `ResearchEvidence` would duplicate it.

**Decision:** Epic D adds only the mission/coverage/packet/cursor machinery that is genuinely absent. Findings continue to be written as `vekl_research_findings`; packets reference them.

### 9. Scope landed under this record

Blueprint Phase 0 (reconcile), Phase 1 (contracts) and Phase 2 (persistence) only. Phases 3–10 — the discovery, research, readiness, verified-action, steering, automation, browser, attention, Studio and adversarial-certification *runtimes* — are **not** authorized as complete by this EDR and are not implemented. `AGENTS.md` is explicit that schemas, stubs and tests are not completion and that a real production call site is required. No call site exists yet, and `IMPLEMENTATION_STATE.md` records that plainly.

## Non-authority law

Nothing in this programme grants authority by existing:

- a `DiscoveryCandidate` carries no Project Truth, implementation, execution or capability authority, and a passing sandbox trial advances lifecycle only — it may never raise `source_trust`;
- a `ResearchMission` is advisory: it may not reorder the TaskGraph, create implementation tasks, expand product scope or amend Project Truth, and a research/Project-Truth implementation conflict remains rejected, escalable only through the existing governed `VEKLTruthChallenge` path;
- `READY` is refused for any provider or capability gate without a live probe, attested identity and a still-fresh evidence pointer; a provider may never assert its own readiness, and a configured credential is never sufficient;
- an automation runtime is a target-runtime effect under `CapabilityLease`/`ExternalEffect`/verifier law — never a WorkerAdapter, never a task orchestrator; it cannot mint grants, authorize capabilities, change task scope or mark a DDE task verified;
- semantic browser output can never satisfy release, accessibility, pixel or security verification, which remain independent DDE verifier duties;
- `MODEL_INFERENCE` and `UNTRUSTED_EXTERNAL` context facts are never presented to a model as settled project fact and are never persisted as fact without explicit promotion;
- an owner steer executes under ordinary DDE authority only: it cannot write around `TruthService`, cannot mutate Project Truth without ordinary accepted authority, cannot silently discard an active change set, and cannot race an active repository writer.

## Anti-false-negative admission law

Qualification emits a bounded disposition plus an explicit `authority_ceiling` and `allowed_uses`/`forbidden_uses`, so material that cannot satisfy the strongest admission bar is retained at a truthful authority level instead of being discarded. `REJECTED` is reserved for material that is malicious, irrelevant, legally unusable or unrecoverably unverifiable. `ANTI_PATTERN` and `FAILURE_SIGNATURE` knowledge stays retrievable and may never fill a positive implementation, reuse or execution slot — extending the AD-050 guidance-polarity rule rather than creating a second one.

## Security law

Principal separation, run-scoped grants with no ambient secrets, sanitized and recorded research egress, prompt-injection containment for all discovered and browsed content, and per-project browser profile isolation with no model-visible or exportable cookie material. Discovered and browsed content is untrusted: it may not alter task authority, grant tools, change Project Truth or policy, request secrets, or invoke privileged actions. Every new project-bound table carries `tenant_id`/`project_id` and forced row-level security under the existing tenant/project predicate.

## Consequences

This EDR makes DDE able to answer, from evidence rather than assertion: which provider is actually ready, which research dimensions are still missing, why each resource was admitted/held/rejected, which capability is degraded and what still works, whether an external action actually happened, and whether an owner steer is waiting on an active writer. It does not grant additional agent autonomy; the gain is operational truthfulness.

It does not make any runtime behaviour live, does not widen ordinary worker egress, does not admit any new source host, and does not make DIAL, Hermes or VAN a DDE dependency.
