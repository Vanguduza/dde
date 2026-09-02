# DDE Architecture Decisions — Rev 3 Consolidated Index

**Status:** CONTROLLED HUMAN-READABLE DECISION INDEX  
**Effective:** 2026-09-02  
**Architecture authority:** `docs/truth/BLUEPRINT_REV3.md`  
**Plan authority:** `docs/truth/DEV_PLAN_REV3.md`  
**Authority note:** accepted Project Truth EDR rows outrank this file. This index is not a competing blueprint.

---

## 0. Decision classes

- **ACCEPTED-EDR** — authoritative decision exists in Project Truth/EDR records.
- **REV3-LOCKED** — locked by the consolidated Rev 3 Blueprint.
- **PLANNED** — accepted target direction awaiting implementation/evidence.
- **DEFERRED/HISTORICAL** — not current implementation authority.

A material contract change requires the appropriate EDR/change-control path.

---

## 1. Retained Rev 3 decision index

The initial Rev 3 index is retained conceptually and normalized to the consolidated Blueprint. Where earlier wording implied a fixed model role, the consolidated decision below controls.

| ID | Decision | Status |
|---|---|---|
| AD-001 | DDE, not any model/harness, owns authoritative state | REV3-LOCKED |
| AD-002 | Project Truth outranks human-readable documents | REV3-LOCKED |
| AD-003 | Blueprint Rev 3 supersedes Rev 2 for forward development | REV3-LOCKED |
| AD-004 | `schemas/**` remains contract SSOT for generated contracts | REV3-LOCKED |
| AD-005 | Interfaces use Gateway/Core boundaries; no direct table access | REV3-LOCKED |
| AD-006 | Vendor/provider code lives behind adapters | REV3-LOCKED |
| AD-007 | Worker environments receive no ambient long-lived credentials | ACCEPTED-EDR / REV3-LOCKED |
| AD-008 | Network egress is deny-by-default and capability-admitted | ACCEPTED-EDR / REV3-LOCKED |
| AD-009 | Side effects require durable identity/idempotency/reconciliation | REV3-LOCKED |
| AD-010 | Mission completion is evidence-backed, never self-reported | REV3-LOCKED |
| AD-011 | Production call-site wiring is part of Definition of Done | REV3-LOCKED |
| AD-012 | Planning output is untrusted until validated/promoted | REV3-LOCKED |
| AD-013 | Strategic orchestration is a dynamic role; Fable is preferred occupant when certified/available | REV3-LOCKED target |
| AD-014 | Hermes is persistent context/research/experience intelligence, not authority | REV3-LOCKED |
| AD-015 | Premium reasoning capacity is an escalation/resource choice, not universal default work | REV3-LOCKED |
| AD-016 | Lower-cost workers are valid when hard gates and verification support them | REV3-LOCKED |
| AD-017 | High-risk implementation receives independent review/oracle coverage | REV3-LOCKED |
| AD-018 | Routing uses eligibility/hard gates before optimization | REV3-LOCKED |
| AD-019 | Learned routing promotes through evaluation/canary/rollback | REV3-LOCKED |
| AD-020 | Repository/Core artifacts, not chat history, carry durable project memory | REV3-LOCKED |
| AD-021 | Context is task-specific, provenance-aware and budgeted | REV3-LOCKED |
| AD-022 | Donor discovery is evidence/reference, not adoption authority | ACCEPTED-EDR / REV3-LOCKED |
| AD-023 | Frontend Studio uses conformance by construction | REV3-LOCKED |
| AD-024 | Frontend quality includes distinctiveness, not only correctness | REV3-LOCKED |
| AD-025 | Visual verification is a real DDE verification capability | ACCEPTED direction / PLANNED implementation |
| AD-026 | VLM critique is rank-9 evidence with bounded revision | ACCEPTED-EDR |
| AD-027 | External design skills inform DDE encodings; they are not product oracles | REV3-LOCKED |
| AD-028 | DDE Code shows honest empty/unavailable/degraded states | REV3-LOCKED |
| AD-029 | DDE Code is a professional manufacturing control-plane product | REV3-LOCKED |
| AD-030 | Web Frontend Studio quality closes before broad multi-target expansion | PLANNED |
| AD-031 | One design authority, many platform renderers | REV3-LOCKED direction |
| AD-032 | Cost/quota/context/provider health are first-class routing/observability inputs | REV3-LOCKED |
| AD-033 | Deterministic mechanisms replace model calls where possible | REV3-LOCKED |
| AD-034 | Rev 3 controlled docs are repository memory, with Blueprint/Plan as primary forward authorities | REV3-LOCKED |

---

## 2. Consolidated operational-hardening decisions

### AD-035 — Project identity precedes configuration

**Status:** REV3-LOCKED

No project configuration may be provisioned until `RuntimeRoot`/`ProjectIdentity` is positively resolved and authorized. Wrong/unrelated roots fail closed.

### AD-036 — Models occupy roles; models are not roles

**Status:** REV3-LOCKED

Strategic-orchestrator occupancy and ordinary worker eligibility are independent runtime concepts.

Target default:

```text
Fable available   → Fable strategic occupant; Opus ordinary candidate
Fable unavailable → Opus temporary occupant; Opus removed from ordinary pool
Fable restored    → Fable strategic occupant; Opus returns to ordinary pool
```

This supersedes any interpretation of older AD-013/015 wording as fixed permanent model jobs.

### AD-037 — Routing learns from independently verified outcomes

**Status:** REV3-LOCKED

Static model/harness affinities are bootstrap priors. DDE increasingly ranks exact `WorkerConfiguration` using verified success, first-pass success, cost, latency, rework, risk and human intervention.

### AD-038 — Hermes learns; DDE governs

**Status:** REV3-LOCKED

Hermes may retrieve/distill execution experience and propose `RoutingInsightCandidate`/workflow candidates. DDE telemetry and policy promotion remain authoritative.

### AD-039 — Mutable work belongs to a ChangePacket

**Status:** REV3-LOCKED

Every controlled mutation has explicit task/run/workspace/read/write scope and provenance.

### AD-040 — Rejected work must be dispositioned

**Status:** REV3-LOCKED

`REJECTED` requires quarantine/revert/isolation and baseline verification. Rejected mutations may not remain anonymous dirty state.

### AD-041 — Commit scope must match accepted packet scope

**Status:** REV3-LOCKED

Unexpected staged paths block controlled commits. Broad staging requires explicit bulk-maintenance authorization.

### AD-042 — Evidence is inherited until specifically invalidated

**Status:** REV3-LOCKED

Previously verified work remains trusted unless a changed dependency/invariant invalidates its evidence. DDE uses delta-only audit/re-verification.

### AD-043 — Context is a runtime resource

**Status:** REV3-LOCKED

High-risk work may not begin when the active session is `UNSAFE_FOR_HIGH_RISK_WORK`. DDE checkpoints and resumes through `ContinuationPackage`.

### AD-044 — Passive reset metadata is preferred over expensive probes

**Status:** REV3-LOCKED

Provider availability probing includes probe economics. Reliable passive reset signals outrank unnecessary expensive active probes.

### AD-045 — Installed/certified capability beats assumed/documented capability

**Status:** REV3-LOCKED

Production routing/lifecycle logic relies on exact installed, certified runtime capabilities; vendor documentation alone is insufficient proof.

### AD-046 — Executable updates require certification

**Status:** REV3-LOCKED

Hermes, Claude Code, Codex harnesses, DeepSeek, MCPs, skills, plugins and other executable components may not silently replace active certified versions. Update candidates are quarantined, certified, canaried and promoted with rollback.

---

## 3. Consolidated Frontend Studio / design / workflow decisions

### AD-047 — Claude Design is a provider capability behind DDE DesignGateway

**Status:** REV3-LOCKED target

Claude `/design` is a first-class Frontend Studio specialist capability, but DDE binds to `DesignProvider`/`DesignGateway`, not to slash-command syntax or provider-owned runtime state.

### AD-048 — Provider artboards are DESIGN; only code-backed runtime is LIVE

**Status:** REV3-LOCKED

`DESIGN`, `LIVE` and `VERIFIED` are semantic states. A provider canvas/artboard cannot be presented as implemented software.

### AD-049 — Material UI work uses a governed design gate

**Status:** REV3-LOCKED target

Material design work produces versioned `DesignArtifact` candidates and an immutable promoted design/code pair before merge eligibility. Small deterministic changes may bypass only by auditable policy.

### AD-050 — Try-Live work is isolated and non-authoritative until promotion

**Status:** REV3-LOCKED target

Design candidates can be implemented in `LiveEditWorkspace` for real rendering/iteration, but may not mutate accepted/main state directly.

### AD-051 — Frontend Studio supports deterministic, contextual-AI and divergent-design lanes

**Status:** REV3-LOCKED target

Known token/component changes compile deterministically; ambiguous visual refinements may use DesignGateway; major/new work may generate divergent candidates.

### AD-052 — Execution Graph is a projection of real runtime truth

**Status:** REV3-LOCKED target

No manually maintained duplicate graph. Nodes derive from DDE workflow/task/session/event/evidence state.

### AD-053 — Node replay/reroute/fork/compare preserve lineage and policy

**Status:** REV3-LOCKED target

Operator debugging controls create governed runtime operations, not hidden mutations.

### AD-054 — Reusable workflows/playbooks express capabilities, not fixed model macros

**Status:** REV3-LOCKED target

Playbooks are versioned/evidence-promoted. Provider choice remains dynamic unless a real capability requirement constrains it.

### AD-055 — Workflow Composer is a compiler front-end, not a second orchestrator

**Status:** REV3-LOCKED target

Visual graphs compile to the same validated DDE workflow/runtime and cannot bypass mandatory gates, capability checks or Project Truth authority.

### AD-056 — Opal is inspiration, not a runtime dependency

**Status:** REV3-LOCKED

DDE adopts the high-value usability/inspectability patterns natively. It does not move authoritative orchestration into Google Opal or another external no-code runtime.

---

## 4. Sequencing decision

### AD-057 — REV-3A Operational Safety Gate precedes DDE-068

**Status:** REV3-LOCKED plan sequencing

Do not renumber DDE-068…DDE-083. After the consolidated truth change, implement REV-3A first: project identity, role occupancy, context continuation, ChangePacket/rejection/staging and evidence-validity safety.

---

## 5. Known open/partial historical EDRs

The DDE-067 gate previously recorded EDR-0002, EDR-0003, EDR-0005, EDR-0027 and EDR-0033 as open/unchanged at that handoff. Do not infer resolution from this index. Read the actual Project Truth/EDR record before affected implementation.

---

## 6. Change protocol

1. Identify the actual contract/decision conflict.
2. Check accepted Project Truth/EDR state.
3. If Project Truth/core authority/security changes, use EDR/change control.
4. Synchronize Blueprint/Plan only after the decision is accepted.
5. Update this index as a readable projection.
6. Never let this file outrank accepted EDRs or the consolidated Blueprint.
