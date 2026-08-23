# System audit — pre-DDE-038 (2026-08-22)

**Scope.** Independent pre-resume review of DDE after missions DDE-001..037 (Stages 0–4
intelligence slice). Six accepted EDRs document honest deferrals. This audit maps
gaps before the mission chain resumes at DDE-038.

**Method.** Read `AGENTS.md`, mission-chapter-gate rule, `docs/blueprint/REV_2_0.md` §18,
all seven EDR pre-images in `docs/truth/edr/`, gap-closure record, and traced production
call sites for unwired seams. Evidence cites file paths; no code was modified for this
audit (routing fixes are a separate task in the same session).

---

## Executive summary

DDE has a **real, test-backed spine** (mission kernel → context → routing → execution →
verification → integration → recovery) through DDE-037, but **cannot yet run a full
mission end-to-end unattended** for a real user. The largest blockers are: no production
outbox dispatcher / background schedulers, execution spine not wired from Gateway to
WorkerManager, warm-pool release and index lifecycle unscheduled, and credential broker
holding no real vendor credentials. Seven accepted EDRs honestly defer learning,
promotion gates, attribution consumers, and ProductEnvironment — but several deferrals
**silently weaken shipped guarantees** if treated as done (semantic retriever gating is
fixed; promotion gates 2–5 and routing gate-5 health are not).

**Top 5 highest-leverage improvements** (detail in §8):

1. Wire Gateway → execution spine (ContextService.compile + WorkerManager.dispatch) as one
   durable mutation path.
2. Run OutboxDispatcher as a production process; add schedulers for index build, warm-pool
   top-up, and merge-queue drain.
3. Close EDR-0003 gates 2–5 or block context-policy promotion until replay exists.
4. Implement real gate-5 capacity signal (Worker Manager health/quota) before degraded-default
   or routing telemetry can be trusted.
5. Land credential broker Path B for DeepSeek/Hermes (EDR-0001) so routable profiles can
   actually execute.

---

## 1. Blueprint coverage map (DDE-038 onward)

Source: `docs/blueprint/REV_2_0.md` §18.3. Missions DDE-001..037 are **built** (with EDR
deferrals noted). Everything below is **not yet built**.

### Stage 4 — Intelligence (remaining)

| Mission | Chapter | Blocked by / makes inert |
|---|---|---|
| **DDE-038** ProductEnvironment lifecycle | Ch.11.6 | EDR-0007 (mission oracle lacks ProductEnvironment e2e); blocks realistic acceptance oracles |
| **DDE-039** Domain invariant engine | Ch.11.5 | Independent; verification runner ready (`engine/verification/checks.py`) |
| **DDE-040** Model-assisted planning + templates | Ch.4.3 | Task planner is template-only (`engine/missions/planner.py`); no LLM planning |
| **DDE-041** Control-plane overhead budget | Ch.16.4 | No UsageRecord writer (EDR-0005); cost instrumentation incomplete |

**Partially inert subsystems waiting on S4 tail:** promotion gates 2–5 (EDR-0003) block
context policy promotion; mission oracle wrong-product path lacks merge-to-main gate
(EDR-0007); routing gate 5 is pass-through (`engine/routing/rules.py` —
`AVAILABILITY_NOT_TRACKED`).

### Stage 5 — Capability breadth (DDE-042..050)

MCP server (DDE-042) **blocked** until Gateway + lease enforcement + durable runs exist
(blueprint Ch.1 note). Browser, vision, security, Donor Lab, Android capabilities — all
unbuilt. **Visual workload class** exists in policy but is unreachable from classifier
(`engine/routing/policy.py` docstring; DDE-044).

### Stage 6 — Clients and tenancy (DDE-051..056)

Multi-tenant authority, web dashboard, Android client, messaging adapters, client parity
fixture — all unbuilt. RLS columns exist (`schemas/sql/0001_stage1.sql`) but production
multi-tenant ops story is untested at scale.

### Stage 7 — Adaptive and hardened (DDE-057..064)

ExperienceRecord, routing learner, adaptive context, Flight Lab, chaos suites, DR drills,
load testing, production readiness review — all unbuilt. **Routing telemetry** writes
(`engine/telemetry/service.py`) but **no consumer** feeds gate 5 or Ch.6.8 exclusion
(EDR-0004, EDR-0005).

---

## 2. EDR debt analysis

All seven EDRs are **accepted into Project Truth** (2026-08-22). Markdown pre-images in
`docs/truth/edr/` may lag the `edrs` table — table outranks file.

| EDR | Deferred scope | Unblocks | Est. size | Weakens guarantee if ignored? |
|---|---|---|---|---|
| **0001** Subscription credentials (Claude primary) | Path B broker + device flow | DDE-019 follow-on, real Claude/DeepSeek workers | L | **Yes** — routable profiles cannot execute with real creds |
| **0002** Semantic retriever default gating | Eval corpus + uplift (DDE-032) | Flip `semantic_retrieval_enabled` safely | M | **Was yes** — fixed by gating; verify `engine/context/service.py` |
| **0003** Promotion gate 1/5 only | Gates 2–5 need replay + attribution + cost | Context policy promotion | M | **Yes** — promotion can pass with 1/5 gates |
| **0004** Attribution 2/3 rules | Denied-request rule, model fallback, Ch.6.8 consumer | EDR-0003 gate 2, routing learning | M | **Yes** — router may learn from context failures |
| **0005** Telemetry without predictions | Route Critic, exploration, actual cost | DDE-057/058, gate 5 health | M | **Yes** — `predicted_*` always null on RouteDecision |
| **0006** RSM 3/7 fixture classes | budget/modality/environment scenarios | Adversarial routing fixtures | S | No — fixture generator honest about scope |
| **0007** Mission oracle partial | ProductEnvironment e2e, merge-to-main, auto-replan | DDE-038, Ch.10.8 completion | M | **Yes** — WRONG_PRODUCT may not trigger replan in production path |

**Dependency chain:** EDR-0004 → EDR-0003 gate 2 → EDR-0003 gates 3–5 → safe context
promotion → EDR-0002 flip → EDR-0005 predictions → EDR-0004 Ch.6.8 consumer → DDE-057/058.

---

## 3. Cross-subsystem integration gaps (built but unwired)

| Seam | Evidence | Impact |
|---|---|---|
| **Failure attribution → Context Critic** | `engine/context/critic.py` accepts `previously_context_attributed_failure`; `engine/context/service.py` passes caller-supplied flag; **no production caller** wires attribution output | Repair-task critic trigger inert |
| **Attribution → routing exclusion (Ch.6.8)** | EDR-0004; `engine/attribution/service.py` writes outcomes; **no router consumer** | Context-attributed failures could teach router incorrectly (when learning lands) |
| **Telemetry outcomes → gate 5 / learner** | `engine/telemetry/repository.py` `list_for_route_decision`; **no caller** in `engine/routing/` | Gate 5 pass-through; no health eviction |
| **Knowledge derived-edge recompute → merge queue** | `engine/knowledge/service.py` — recompute not wired to integration post-merge | Stale derived edges after merge |
| **Warm-pool `release()` → TaskAttempt finalization** | `engine/environments/service.py` has `release()`; `engine/workers/service.py` acquires but **no `release()` call site** in worker finalization | Pool leak under parallel missions |
| **Index build / incremental triggers** | `engine/context/index_service.py` — no scheduler; **zero production callers** of `build_index`/`reindex_incremental` outside tests | Semantic index never builds in ops |
| **ContextService.compile in execution path** | `engine/execution/service.py` is stub-level; Gateway commands don't invoke compile+dispatch loop | Context packages not assembled for real runs |
| **OutboxDispatcher in production** | `engine/events/dispatcher.py` exists; **only tests** instantiate `OutboxDispatcher` | Events never drain in live Gateway |
| **Credential broker → adapters** | `engine/capabilities/broker/service.py` — no real vendor creds; adapters use stubs | Workers cannot call models |
| **Integration post-merge step 5** | `engine/integration/service.py` docstring — reindex/release deferred | Merge completes without index refresh |
| **Mission workflow recovery** | `engine/recovery/workflow.py` — partial; replan dispatch exists (`engine/recovery/dispatch.py`) but not full mission driver | Recovery matrix rows not auto-applied |

---

## 4. Operational readiness

### How to run today

| Entry | Status | Evidence |
|---|---|---|
| **Gateway REST/WS** | Partial | `engine/gateway/api.py` — sessions, commands, missions; requires Postgres + Redis |
| **CLI** | Working for read/trace | `interfaces/cli/__main__.py` — `mission create|status|trace`, `task list`; `--json` added (gap-closure §2.3) |
| **dde-studio** | Health + Gateway client | `interfaces/dde-studio/shared/gatewayClient.ts`; fleet lists empty (no list endpoint — DDE-027 gap) |
| **Outbox / workers** | Not runnable as product | No `OutboxDispatcher` in `engine/gateway/app.py` lifespan |
| **Background schedulers** | **None** | No APScheduler/cron/asyncio periodic jobs in `engine/` |
| **Deployment** | devcontainer + docker-compose | Windows local improved (`justfile` `set windows-shell`, `just test-unit`) |
| **Secrets** | Config.toml / env | `packaging/windows/config.example.toml`; broker not wired |
| **Migrations** | Alembic | `migrations/versions/` — 0009+; reversible discipline in mission chain |
| **Observability** | structlog in modules; **no OTel exporter wired** | Grep: no `BatchSpanProcessor` in `engine/` |
| **Backup / DR** | **Undocumented in repo** | Ch.17.5 / DDE-062 not built; no `pg_dump` scripts |
| **Multi-tenant RLS** | Schema + tests | DDE-022 suite; bypass roles must stay out of production paths |

### Biggest practical blockers (P0)

1. No production event dispatcher → side effects after commit may stall.
2. No Gateway-orchestrated mission run loop (plan → route → execute → verify → integrate).
3. No real worker credentials → adapters fail-closed or scripted only.
4. No schedulers → indexes, warm pools, merge queue concurrency=1 manual only.

---

## 5. Test / verification posture

| Metric | Value | Notes |
|---|---|---|
| Test functions | ~561 | `tests/**` |
| Contract tests | Dedicated `tests/contract/` | Schema drift guarded (`tests/contract/test_drift.py`) |
| Schema objects | ~80+ JSON in `schemas/objects/` | Generated contracts in `engine/contracts/` |
| Golden mission | Referenced in blueprint §18 | Exercised in integration/recovery suites |
| Unit fast path | `just test-unit` | 179 passed / 239 deselected (gap-closure, Windows) |
| Concurrency | Partial | Known SELECT-then-INSERT race noted historically in `assert_edge` |
| Flaky suites | `test_events_recovery`, CLI recovery order-dependent | Recovery folder |
| Load / perf | **Absent** | DDE-063 |
| Gate-5 / degraded-default | Unit tests in `tests/unit/test_routing_adoption_features.py` | Must distinguish gate 3 vs gate 5 (blueprint fidelity) |

**Risk:** High test count with **low end-to-end coverage** of the Gateway → worker → verify
path. Contract tests validate shapes; they do not prove the spine is wired.

---

## 6. Security / trust boundaries

| Control | Status | Evidence |
|---|---|---|
| T1 lease enforcement | Real for scripted adapter | `engine/workers/scripted_adapter.py`, `engine/capabilities/lease_service.py` |
| T2 containment | Shell adapters fail-closed | `adapters/claude/adapter.py`, `adapters/cursor/adapter.py` |
| Ambient credential filtering | Ch.7.2 fixtures in tests | DDE-018 |
| Broker secret material | **No real creds** | `engine/capabilities/broker/service.py` |
| RLS | Enforced in tests | DDE-022; `tests/support/db.py` |
| Claude approval gating | Adapter-level | Subscription path deferred (EDR-0001) |
| Kill switch / budget | **Landed later on 2026-08-22** (see note below) | commits `1de8b72`, `4d7cf1a`, `0df07eb`, `0464933` |
| Audit hash chain | Ledger exists | `engine/audit/ledger.py`; external pin not implemented |

> **Same-day amendment (2026-08-22, post-audit landings).** The kill-switch and
> budget row above was true at audit time and is now superseded: kill flag at
> broker admission (`1de8b72`), journaled refusals + lease sweep on arm
> (`4d7cf1a`), durable CommandLedger stop record surviving restarts
> (`0df07eb`), persisted attempt budgets + dispatch-time `BUDGET_EXCEEDED`
> classification (`0464933`), and self-grading guardrails classifying
> `SCOPE_VIOLATION` (`e730a9e`). The blueprint chapters (Ch.7.1, Ch.9.2,
> Ch.12.3, Ch.14) carry the corresponding specification.


**Realistic threat model at current stage:** Insider with DB access bypasses RLS if granted
BYPASSRLS role; worker with T2 lease and no egress proxy (partial) could exfiltrate;
**lethal trifecta** possible if untrusted content and git push share a worker path without
lease conflict rules.

---

## 7. Architecture / code health

| Area | Assessment |
|---|---|
| Module boundaries | **Clean** — `engine/core` contract-only; adapters isolated; interfaces consume Gateway |
| Generated contracts | Enforced by `generate_contracts --check` |
| Docstring overclaim | Historical issue (DDE-020); mission-chapter-gate rule mitigates |
| State machines | Enums in `engine/recovery/states.py`, `engine/missions/` — transitions enforced in services, not all paths audited |
| Error taxonomy | Ch.15.4 `DdeError` used at boundaries |
| Dead code | `visual_analysis` workload reachable only by explicit override |
| POLICY_VERSION | Stable `deterministic-v1`; adoption features opt-in at `evaluate()` — production `RouterService.route()` unchanged |

---

## 8. Prioritized gap register

### P0 — Blocks real use

| ID | Gap | Evidence | Why it matters | Smallest next step |
|---|---|---|---|---|
| P0-1 | No production mission execution loop | `engine/gateway/commands.py`, stub `engine/execution/service.py` | User cannot run a mission to completion | Charter DDE-038 prep: wire one command handler through route→worker→verify |
| P0-2 | Outbox never drained in Gateway | `engine/events/dispatcher.py`; only tests call it | Committed events stall; recovery broken | Add dispatcher task to Gateway lifespan |
| P0-3 | No real worker credentials | EDR-0001; `engine/capabilities/broker/` | Routable profiles inert | Implement DeepSeekApiKeyProvider + lease bind |
| P0-4 | No background schedulers | Grep: no scheduler in `engine/` | Indexes, pools, merge queue don't run | Minimal asyncio periodic runner for outbox + one index job |
| P0-5 | Warm pool never released | `engine/workers/service.py` — no `release()` | Resource exhaustion under load | Call `environments.release()` in attempt finalization |

### P1 — Weakens guarantees

| ID | Gap | Evidence | Why it matters | Smallest next step |
|---|---|---|---|---|
| P1-1 | Promotion gates 2–5 open | EDR-0003 | False promotion confidence | Defer promotion API or implement gate 2 replay |
| P1-2 | Gate 5 pass-through | `engine/routing/rules.py` | Degraded-default/health misleading | Wire telemetry cooldown or document EDR until DDE-011 signal |
| P1-3 | Attribution not feeding critic | `engine/context/service.py` | Critic trigger 5 inert | Pass attribution lookup in repair compile path |
| P1-4 | Mission oracle incomplete | EDR-0007 | WRONG_PRODUCT may not replan | Wire `transition_mission(REPLANNING)` on oracle fail |
| P1-5 | Semantic/index lifecycle unscheduled | `engine/context/index_service.py` | Retrieval quality stale | Schedule `reindex_incremental` on merge hook |
| P1-6 | Routing telemetry no consumer | EDR-0005; `engine/telemetry/` | Learning prep incomplete | Read outcomes in gate 5 stub |
| P1-7 | ProductEnvironment absent | DDE-038 not started | Acceptance not realistic | Start DDE-038 schema + service skeleton |

### P2 — Quality / velocity

| ID | Gap | Evidence | Why it matters | Smallest next step |
|---|---|---|---|---|
| P2-1 | No OTel export | No exporter in `engine/` | Ops blind in production | Add optional OTLP in Gateway settings |
| P2-2 | No backup/restore runbook | Ch.17.5 deferred | DR unknown | Document pg_dump for Project Truth |
| P2-3 | Load testing absent | DDE-063 | Capacity unknown | Baseline pytest-benchmark on routing/context |
| P2-4 | Studio fleet lists empty | No list API (DDE-027) | UX incomplete | Add `GET /v1/missions` when Gateway ready |
| P2-5 | Windows installer packaging unmerged | `packaging/windows/` untracked | Distribution friction | Separate commit after CI green |
| P2-6 | MCP deferred correctly | Ch.1 note | Premature MCP adds risk | Wait for DDE-042 gate |

---

## 9. Top 5 highest-leverage improvements

1. **Production execution spine** — One Gateway command that routes, dispatches a worker,
   runs verification, and records evidence (`engine/gateway/commands.py` →
   `engine/workers/service.py` → `engine/verification/runner.py`).

2. **Durable event dispatch** — Run `OutboxDispatcher` inside Gateway process with health
   check; unblocks all async side effects.

3. **Credential broker for DeepSeek/Hermes** — Close EDR-0001 Path B so OpenRouter/model
   routing selects a profile that can actually run (pairs with routing model selection in
   `engine/routing/registry.py`).

4. **Honest promotion gate or hard block** — Until EDR-0003 gates 2–5 exist, reject
   `promote_context_policy` mutations at the service boundary.

5. **Scheduler minimalism** — Single `engine/scheduler/runner.py` with index incremental +
   outbox drain + warm-pool top-up hooks; avoids "second orchestrator" forbidden pattern
   while making built subsystems operational.

---

## 10. Resume recommendation

**Do not treat DDE-037 as "product ready."** CI green and chapter PASS on substance allow
**DDE-038** to start under mission-chapter-gate discipline, but the P0 integration gaps
mean parallel "ops hardening" (outbox, scheduler, execution wiring) should accompany or
immediately follow DDE-038 unless the mission explicitly charters the spine.

**Concurrent agent work (2026-08-22):** CLI `--json`, Windows `just test-unit`, studio Gateway
client, and routing adoption features are sound after blueprint fidelity fixes (affinity
subordinate to `prefer[]`; degraded-default only on gate-5 capacity class). OpenRouter model
catalog added for Hermes/DeepSeek harness classes with DeepSeek API key credential tier.

---

*Audit author: system review subagent (resumed 2026-08-22). No Project Truth rows modified.*
