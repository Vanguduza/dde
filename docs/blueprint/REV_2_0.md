# DDE v1 — Master Technical Blueprint & Construction Plan

**Revision 2.0 — Execution-Ready Baseline**
**Date:** 19 August 2026
**Supersedes:** REV 1.3 Gap-Closure Construction Baseline (all REV 1.3 content is preserved, corrected, or superseded explicitly in [Chapter 20](#chapter-20--change-control-and-traceability-to-rev-13))
**Target deployment:** cloud-first, self-hostable, model-agnostic, MCP-first
**Document status:** Authoritative construction baseline. Buildable without inventing missing contracts.
**Amended:** 22 August 2026 — safety-envelope mechanisms landed and specified in place (stop authority, attempt budgets, guardrail classification), design-gate toolchain adopted (EDR-0008), queue-closure policies recorded (usage metering, batch approval, routing health eviction, T2 termination scope, oracle confidence semantics). Chapter-local notes marked *(amended 2026-08-22)*; nothing renumbered, nothing superseded. **23 August 2026 — intentional-stop classification wired at its real site and the resume path brought under the same armed-stop law** (Ch.12.3 matrix row + Ch.12.4 new-mutation rule; EDR-0010 accepted, EDR-0012 wiring). **24 August 2026 — UI template/component sourcing brought under donor governance** (Ch.13.8 amendment from the anti-generic-output research; distinctiveness gates staged in `docs/planning/gap-closure-record.md §6.5` and playbook §10).

---

> **EXECUTIVE ARCHITECTURAL DECISION (unchanged from REV 1.x)**
> DDE is a model-agnostic engineering control plane. It owns product truth, mission state, context policy, routing policy, capability governance, verification and evidence. External agent harnesses are *workers*. Editors, phones, browsers and chat channels are *clients*. This separation is the primary mechanism preventing agent sprawl and context drift.

> **WHAT CHANGED IN REV 2.0**
> REV 2.0 does **not** reduce v1 capability scope. Every capability declared in REV 1.3 remains in v1. What changed is that the plan is now *executable*: the two missing links of the manufacturing spine are specified (TaskGraph/Task Planner and the Integration & Merge Queue), enforcement is described in terms that can actually be implemented against third-party harnesses, the schema is made a single generated source of truth with tenancy applied throughout, adaptive routing is re-sequenced behind measurable gates without being removed, and the build order is restructured so a **complete vertical slice of the whole system runs end-to-end at Stage 1** and never stops running afterwards. See [Chapter 18](#chapter-18--staged-execution-plan) and [Appendix C](#appendix-c--review-findings--resolution-map).

---

## Table of contents

| Ch | Title | What it gives you |
|----|-------|-------------------|
| [1](#chapter-1--execution-guide-zero-to-a-running-dde-cloud-control-plane) | **Execution Guide** — zero to a running cloud control plane | Accounts, bootstrap, Cursor prompts, day-1 commands |
| [2](#chapter-2--architecture-and-authority) | Architecture and authority | Authority ranks, principles, canonical spine |
| [3](#chapter-3--canonical-object-model-and-schema-authority) | Canonical object model and schema authority | One generated schema, tenancy, IDs, partitioning |
| [4](#chapter-4--mission-planning-taskgraph-and-task-planner) | **Mission planning: TaskGraph and Task Planner** | NEW — closes the largest gap in REV 1.3 |
| [5](#chapter-5--context-intelligence) | Context Intelligence | Retrieval pipeline, index lifecycle, eval corpus |
| [6](#chapter-6--routing-intelligence) | Routing Intelligence | Deterministic v1 router, simulation, staged learning |
| [7](#chapter-7--execution-plan-environment-and-workspace) | Execution plan, environment and workspace | Two-tier enforcement, warm pools |
| [8](#chapter-8--worker-contract-and-certification) | Worker contract and certification | One normative adapter, tiered certification |
| [9](#chapter-9--capability-plane-and-admission) | Capability plane and admission | Side-effect taxonomy, dependency admission |
| [10](#chapter-10--integration-and-merge-queue) | **Integration and Merge Queue** | NEW — closes the second-largest gap |
| [11](#chapter-11--verification-acceptanceoracle-and-productenvironment) | Verification, AcceptanceOracle, ProductEnvironment | Executable proof obligations |
| [12](#chapter-12--recovery-effects-and-durability) | Recovery, effects and durability | Checkpoints, effect journal, retention |
| [13](#chapter-13--governance-approvals-and-autonomy-economics) | Governance, approvals and autonomy economics | Pre-authorization, attention budget, tenancy |
| [14](#chapter-14--security-identity-and-credentials) | Security, identity and credentials | Broker, principals, invariants |
| [15](#chapter-15--gateway-api-and-mcp) | Gateway, API and MCP | Transport, envelopes, tool classes |
| [16](#chapter-16--observability-slos-and-the-overhead-budget) | Observability, SLOs and overhead budget | Control-plane cost ceiling |
| [17](#chapter-17--operations-deployment-and-disaster-recovery) | Operations, deployment and disaster recovery | Scale invariants, RPO/RTO, WORM |
| [18](#chapter-18--staged-execution-plan) | **Staged execution plan** | Full scope, staged gates, always-demonstrable |
| [19](#chapter-19--contract-tests-and-flight-lab) | Contract tests and Flight Lab | The executable form of this document |
| [20](#chapter-20--change-control-and-traceability-to-rev-13) | Change control and traceability | What superseded what |
| [A](#appendix-a--reference-worker-portfolio) | Reference worker portfolio | All vendor-specific content, isolated |
| [B](#appendix-b--corrections-applied) | Corrections applied | Defects fixed from REV 1.3 |
| [C](#appendix-c--review-findings--resolution-map) | Review findings → resolution map | F1–F23 traceability |

---
---

# Chapter 1 — Execution Guide: zero to a running DDE cloud control plane

This chapter is written for one specific situation: **you have a Windows machine with Cursor Desktop and nothing else, and you want DDE running in the cloud.** It assumes no local Git, Docker, Python or GitHub CLI. Everything heavy runs in the cloud; your machine is a control surface.

Read this chapter top to bottom once. Then work through §1.4 and §1.5 with Cursor open.

## 1.1 What you are actually building first

Not a framework. Not an agent. You are building a **control plane that can prove it manufactured something**.

The Stage 1 target — the thing that must exist before anything else gets built — is one command that does this:

```
dde mission run "Add a /health endpoint that returns build SHA and DB status"
```

…and produces, durably and reproducibly: a Mission record, a TaskGraph, a compiled ContextPackage, a RouteDecision, an ExecutionPlan, an isolated workspace, a WorkerRun inside a sandboxed container, a diff, a passing test, an independent verification run, an evidence record, and a merged commit — all queryable afterwards, all reconstructable, all attributable.

Everything else in this document is depth added to that skeleton. If the skeleton is not running, nothing else matters.

## 1.2 Accounts and services to create

Create these before writing any code. All have free or near-free tiers sufficient for Stage 1–3. Links open the signup or docs page.

**Required for Stage 1**

| Service | Purpose | Link | Notes |
|---|---|---|---|
| GitHub | Source of truth, CI, Codespaces | [github.com](https://github.com) | Private repo. Enable Actions. |
| Cursor | Your IDE and primary development agent | [cursor.com](https://cursor.com) | Already installed. |
| Git for Windows | Local git (Cursor needs it) | [git-scm.com/download/win](https://git-scm.com/download/win) | The only mandatory local install. |
| Neon **or** Supabase | Managed PostgreSQL 16+ | [neon.tech](https://neon.tech) · [supabase.com](https://supabase.com) | Neon for branching; Supabase if you also want auth + storage. |
| Cloudflare R2 | Artifact and evidence object storage | [developers.cloudflare.com/r2](https://developers.cloudflare.com/r2/) | S3-compatible. Enable object lock later (§17.5). |
| Anthropic / DeepSeek / OpenAI keys | Worker model access | [console.anthropic.com](https://console.anthropic.com) · [platform.deepseek.com](https://platform.deepseek.com) | At least one to start. |

**Required by Stage 2–3**

| Service | Purpose | Link |
|---|---|---|
| Fly.io **or** Hetzner Cloud | Where DDE Core runs | [fly.io](https://fly.io) · [hetzner.com/cloud](https://www.hetzner.com/cloud) |
| Upstash Redis | Queue, cache, ephemeral locks | [upstash.com](https://upstash.com) |
| Grafana Cloud (free) | OpenTelemetry traces and metrics | [grafana.com/products/cloud](https://grafana.com/products/cloud/) |
| Langfuse Cloud (free) | LLM-specific tracing and cost | [langfuse.com](https://langfuse.com) |

**Deferred deliberately** — do not provision these in Stage 1: Temporal, a vector database service, Kubernetes, a secrets-manager appliance. See [§18.7](#187-explicitly-deferred-infrastructure).

## 1.3 The five environments — keep them separate in your head

Confusing these is the most common way this kind of project fails.

1. **Authoring environment** — Cursor Desktop on your machine. Edits code, drives agents. Never authoritative for anything.
2. **DDE Core** — the cloud control plane. Owns Project Truth, missions, events, evidence. The *only* authoritative state.
3. **ExecutionEnvironment** — disposable sandboxed containers where workers run. Isolated filesystem, deny-by-default network, no ambient credentials. See [Chapter 7](#chapter-7--execution-plan-environment-and-workspace).
4. **ProductEnvironment** — throwaway deployments of *the software DDE is building*, used to verify it. Distinct from #3. See [§11.6](#116-productenvironment).
5. **Worker providers** — model APIs and agent harnesses. Replaceable, never trusted, never authoritative.

## 1.4 Day 1 — bootstrap, step by step

### Step 1 — Install Git and sign in

Install [Git for Windows](https://git-scm.com/download/win) with defaults. Restart Cursor. Then in Cursor: `Ctrl+Shift+P` → `Git: Clone` will now work, and the built-in terminal will have `git`.

Sign in to GitHub from Cursor's Source Control panel, or run once in the terminal:

```powershell
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
```

### Step 2 — Create the repository from Cursor

Open a new Cursor window on an empty folder, e.g. `C:\Users\Admin\Documents\dde`. Paste the **Bootstrap Prompt** from [§1.6](#16-the-master-cursor-prompts) into the agent. It will create the repository skeleton, the devcontainer, CI, and the schema source of truth.

Then push:

```powershell
git init
git add -A
git commit -m "DDE-001: repository, devcontainer and CI foundation"
git branch -M main
```

Create the private GitHub repo in the browser, then:

```powershell
git remote add origin https://github.com/<you>/dde.git
git push -u origin main
```

### Step 3 — Move development into a Codespace

You have no Docker or Python locally, and you do not need them. Open your repo on GitHub → **Code** → **Codespaces** → **Create codespace on main**. The devcontainer created in Step 2 provisions Python 3.12, PostgreSQL, Redis and the toolchain.

Then connect Cursor to it: `Ctrl+Shift+P` → `Codespaces: Connect to Codespace`. You now edit in Cursor with a full Linux toolchain behind it. See [Cursor remote development docs](https://docs.cursor.com/).

> If you prefer not to use Codespaces, provision the smallest [Hetzner Cloud](https://www.hetzner.com/cloud) VM (CX22, ~€4/month), install Docker, and connect Cursor over SSH. Same result, lower cost, more setup.

### Step 4 — Provision Postgres and apply migration 001

Create a Neon project, copy the pooled connection string, and put it in the Codespace secret `DDE_DATABASE_URL`. Then, in the Codespace terminal:

```bash
uv sync                      # install dependencies
just db-upgrade              # alembic upgrade head
just contract-test           # schema contract tests must pass before anything else
```

If `contract-test` fails, stop. The schema is the one artifact everything else is generated from ([Chapter 3](#chapter-3--canonical-object-model-and-schema-authority)).

### Step 5 — Run the control plane locally in the Codespace

```bash
just dev                     # uvicorn + worker manager + outbox dispatcher
curl localhost:8000/healthz
curl localhost:8000/readyz
```

### Step 6 — First real mission

```bash
dde project init --name "DDE Self-Hosting" --repo https://github.com/<you>/dde
dde truth import ./docs/product-constitution.md
dde mission run "Add a /version endpoint returning build SHA" --autonomy assisted
dde mission trace <mission-id>          # the full spine, top to bottom
```

The mission is only successful when `dde mission trace` shows an evidence record produced by a verification run that the generating worker did not control. That is the Stage 1 exit gate ([§18.2](#182-stage-gates)).

### Step 7 — Deploy DDE Core to the cloud

```bash
fly launch --no-deploy            # generates fly.toml
fly secrets set DDE_DATABASE_URL=... DDE_REDIS_URL=... DDE_R2_ACCESS_KEY=...
fly deploy
```

From this point your machine is optional. Cursor, the Android client, and the CLI are all clients of the deployed control plane.

## 1.5 How to drive development with Cursor Desktop

DDE is built the way DDE builds: contract first, verified, traceable. Configure Cursor to enforce that.

### 1.5.1 Repository rules

Create `AGENTS.md` at the repo root (the Bootstrap Prompt does this). It is loaded automatically as persistent guidance. Its content is given in [§1.6.2](#162-agentsmd--persistent-repository-rules). See the [Cursor rules documentation](https://docs.cursor.com/context/rules).

### 1.5.2 Working rhythm

One DDE mission (`DDE-0xx`) = one branch = one PR = one Cursor agent session. Do not run two structural missions in the same branch; you will lose the ability to bisect.

For each mission:

1. Open a **new** Cursor chat (fresh context).
2. Paste the **Mission Prompt** ([§1.6.3](#163-mission-prompt--use-once-per-dde-mission)) with the mission ID and acceptance criteria filled in.
3. Let the agent write the contract test **first**, and confirm it fails.
4. Let it implement until the test passes and `just check` is green.
5. Review the diff yourself. This is the human verification gate until Stage 4 automates it.
6. Merge. Tag. Move on.

### 1.5.3 When to use Cursor cloud agents

Use [Cursor cloud agents](https://docs.cursor.com/) for missions that are wide but mechanical — schema propagation, adding a field across twelve modules, test scaffolding, migration writing. Keep interactive local sessions for anything that involves a design decision. Cloud agents are clients of your repo, never part of DDE's runtime.

### 1.5.4 MCP during bootstrap

Once DDE has an MCP server (`DDE-042`, Stage 5 — Ch.18.3), point Cursor at it so you can query missions and evidence from the editor. Until then, do not add MCP servers to Cursor for this project — they add context pressure with no benefit. Stage 5 is correct, not an earlier stage: Ch.15.6 requires every MCP tool call to pass through the same Mission Kernel, capability leases, certification and verification pipeline as a native call, so the MCP server cannot be safely exposed before the Gateway (`DDE-027`, S3), the capability/lease enforcement plane (`DDE-016`–`018`, S2) and durable run/approval semantics (S3) all exist under it. See the [MCP specification](https://modelcontextprotocol.io/).

## 1.6 The master Cursor prompts

Three prompts. Use the right one for the right job.

### 1.6.1 Bootstrap prompt — use once, in an empty folder

> Paste this entire block into a fresh Cursor agent chat.

```text
You are bootstrapping DDE (Development & Engineering Engine), a cloud-hosted software
manufacturing control plane. I am working on Windows with Cursor Desktop. I have Git
installed and nothing else — no Python, no Docker, no gh CLI locally. All heavy tooling
will run in a GitHub Codespace, so generate everything to be Linux/devcontainer-first.

Read DDE_v1_Master_Technical_Blueprint_REV_2_0_Execution_Ready.md in this folder before
you write anything. It is the authoritative specification. Where this prompt and the
blueprint disagree, the blueprint wins; tell me about the conflict instead of guessing.

TASK: create the DDE-001 repository foundation. Nothing more. Do not implement domain
logic, do not create endpoints beyond health checks, do not scaffold features that
Chapter 18 assigns to later stages.

Produce exactly this:

1. Python 3.12 project managed with uv.
   - pyproject.toml with: fastapi, uvicorn[standard], sqlalchemy[asyncio]>=2.0, asyncpg,
     alembic, pydantic>=2, pydantic-settings, typer, httpx, structlog,
     opentelemetry-sdk, opentelemetry-instrumentation-fastapi, redis.
   - dev group: pytest, pytest-asyncio, testcontainers, ruff, mypy, hypothesis,
     schemathesis, pytest-cov.
   - Strict settings: ruff (E,F,I,N,UP,B,S,ASYNC), mypy strict on engine/, no implicit Any.

2. Repository layout exactly as Chapter 3.6 of the blueprint specifies. Create the
   directories with __init__.py and a one-line module docstring stating the module's
   single responsibility. Do not put logic in them yet.

3. .devcontainer/devcontainer.json + docker-compose.yml providing: Python 3.12,
   PostgreSQL 16, Redis 7, ripgrep, git, just. Forward ports 8000 and 5432.

4. Alembic configured for async SQLAlchemy, with migration 0001 containing ONLY the
   Stage 1 tables listed in Chapter 3.3 of the blueprint. Every table must have:
   tenant_id, project_id (where Chapter 3.2 requires them), UUIDv7 primary keys stored
   as native uuid, created_at/updated_at timestamptz, and lock_version where Chapter 3.5
   requires optimistic locking. Add the row-level security policies from Chapter 13.4.

5. schemas/ directory as the single schema source of truth per Chapter 3.1:
   - schemas/*.json  — JSON Schema 2020-12 for every wire contract
   - a generator script that emits Pydantic models from them into engine/contracts/
   - a contract test that fails if generated code drifts from schemas/

6. justfile with: dev, test, contract-test, db-upgrade, db-revision, lint, typecheck,
   check (= lint + typecheck + test + contract-test), fmt.

7. .github/workflows/ci.yml running the CI pipeline in Chapter 17.4, with a real
   PostgreSQL service container. CI must fail if migrations do not apply cleanly to an
   empty database AND if generated contracts drift.

8. FastAPI app exposing only /healthz and /readyz per Chapter 17.3. /readyz must check
   database and Redis reachability and return 503 when either is down.

9. AGENTS.md exactly as specified in section 1.6.2 of the blueprint.

10. README.md: what DDE is, the five environments from Chapter 1.3, and the Codespace
    quickstart from Chapter 1.4.

11. docs/product-constitution.md — a starter Product Constitution stub with the section
    headings required by Chapter 2.4.

12. Move this blueprint to docs/blueprint/REV_2_0.md and leave it there — AGENTS.md and
    every mission prompt reference that path.

Rules while you work:
- Contract before code. Write the JSON Schema, then generate, then implement.
- No TODO comments. If something is out of scope, leave it out and list it in your summary.
- No placeholder or example implementations that "will be replaced later".
- Every file you create must be reachable from either the app, a test, or CI.
- Stop and ask me if a decision would bind the architecture in a way Chapter 3 or
  Chapter 18 does not already decide.

When finished, output: (a) the tree, (b) the exact commands I must run in the Codespace
in order, (c) anything in the blueprint you could not satisfy and why.
```

### 1.6.2 AGENTS.md — persistent repository rules

> This file lives at the repo root and is loaded into every agent session. Keep it under
> ~200 lines; it competes with real context.

```markdown
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
```

### 1.6.3 Mission prompt — use once per DDE mission

> Fill the four bracketed fields. Start a **new** chat for each mission.

```text
MISSION: [DDE-0xx — short title]
BLUEPRINT CHAPTERS: [e.g. Chapter 4, Chapter 10]
STAGE: [S0..S7]  — do not implement anything belonging to a later stage.

Read the named blueprint chapters and AGENTS.md before writing code. If the blueprint is
ambiguous for something you must decide, stop and ask; do not resolve it yourself.

ACCEPTANCE (this mission is done only when all are true):
- [criterion 1 — observable, not "code is written"]
- [criterion 2]
- [criterion 3]
- `just check` green; golden mission fixture still passes.

WORK ORDER — follow it strictly:
1. Restate the contract you are about to implement in your own words, and list every
   existing contract it touches. Wait for my confirmation if anything is load-bearing.
2. Write or update the JSON Schema in schemas/ first. Regenerate contracts.
3. Write the failing tests: one schema test, one state-transition test, one negative
   test, one recovery test (Chapter 19.1). Show me they fail.
4. Write the migration if state is involved. Verify it applies to an empty DB and
   reverses cleanly.
5. Implement the minimum that makes the tests pass.
6. Run `just check`. Fix what you broke.
7. Summarise: what changed, which blueprint sections are now implemented, which are
   still stubs, and any divergence you had to make.

CONSTRAINTS:
- Do not refactor unrelated code. Do not "improve" adjacent modules.
- Do not add a dependency without asking.
- Do not write TODOs — unfinished work goes in the summary, not the source.
- Do not mark work complete based on your own reading of the diff. Completion means
  tests pass.
```

## 1.7 Cost expectations

Stage 1–3 should cost under roughly USD 30/month in infrastructure (Neon free/launch tier, Upstash free, R2 pennies, Fly.io shared-CPU-1x, Grafana free). Model spend dominates everything else and is the thing to instrument first — which is why the control-plane overhead budget in [§16.4](#164-control-plane-overhead-budget) is a Stage 2 gate rather than a nicety.

## 1.8 Quick link index

**Cursor** — [docs](https://docs.cursor.com/) · [rules](https://docs.cursor.com/context/rules) · [MCP](https://docs.cursor.com/context/mcp)
**Runtime** — [FastAPI](https://fastapi.tiangolo.com/) · [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/) · [Alembic](https://alembic.sqlalchemy.org/) · [Pydantic v2](https://docs.pydantic.dev/latest/) · [uv](https://docs.astral.sh/uv/) · [Typer](https://typer.tiangolo.com/)
**Data** — [PostgreSQL 16](https://www.postgresql.org/docs/16/index.html) · [Neon](https://neon.tech/docs) · [Supabase](https://supabase.com/docs) · [Upstash Redis](https://upstash.com/docs/redis) · [Cloudflare R2](https://developers.cloudflare.com/r2/)
**Testing** — [pytest](https://docs.pytest.org/) · [Testcontainers](https://testcontainers-python.readthedocs.io/) · [Hypothesis](https://hypothesis.readthedocs.io/) · [Schemathesis](https://schemathesis.readthedocs.io/)
**Isolation** — [Docker](https://docs.docker.com/) · [gVisor](https://gvisor.dev/docs/) · [Firecracker](https://firecracker-microvm.github.io/)
**Source intelligence** — [ripgrep](https://github.com/BurntSushi/ripgrep) · [Tree-sitter](https://tree-sitter.github.io/tree-sitter/) · [ast-grep](https://ast-grep.github.io/) · [Semgrep](https://semgrep.dev/docs/)
**Supply chain** — [Gitleaks](https://github.com/gitleaks/gitleaks) · [Trivy](https://trivy.dev/) · [Syft](https://github.com/anchore/syft) · [Grype](https://github.com/anchore/grype) · [OSV](https://osv.dev/)
**Observability** — [OpenTelemetry](https://opentelemetry.io/docs/) · [Grafana Cloud](https://grafana.com/docs/grafana-cloud/) · [Langfuse](https://langfuse.com/docs) · [Sentry](https://docs.sentry.io/)
**Verification** — [Playwright](https://playwright.dev/python/) · [Maestro](https://maestro.mobile.dev/)
**Deployment** — [Fly.io](https://fly.io/docs/) · [Hetzner Cloud](https://docs.hetzner.com/cloud/) · [GitHub Actions](https://docs.github.com/actions) · [Codespaces](https://docs.github.com/codespaces)
**Protocols** — [MCP](https://modelcontextprotocol.io/) · [JSON Schema 2020-12](https://json-schema.org/draft/2020-12/release-notes) · [CloudEvents](https://cloudevents.io/)
**Deferred by decision** — [Temporal](https://docs.temporal.io/) · [LangGraph](https://langchain-ai.github.io/langgraph/) · [OpenHands](https://docs.all-hands.dev/)

---
---

# Chapter 2 — Architecture and authority

## 2.1 Purpose and non-goals

DDE converts human product intent into traceable, verified software while composing models, agents and tools per mission. It is **not** a model provider, **not** an IDE, **not** a replacement for Git/CI/databases, and **not** fully autonomous — human authority is mandatory for designated decisions.

DDE assumes neither a perfect router nor a perfect context compiler. Both are adaptive subsystems wrapped in deterministic policy, provenance, critics, evaluation, checkpoints and rollback.

## 2.2 Authority ranks

> **Correction (REV 1.3 §7):** the old wording — "lower levels may inform higher levels" — parsed backwards against its own numbering. Restated below as *precedence ranks*, where **rank 0 has the highest precedence**.

| Rank | Artifact class | Can be changed by |
|---|---|---|
| 0 | Human-approved governance decisions | Human authority only |
| 1 | Product Constitution | Rank-0 decision through change control |
| 2 | Approved PRD | Rank-0/1 |
| 3 | Approved Requirements | Rank-0/1/2 |
| 4 | Accepted EDRs | Supersede only, never rewrite |
| 5 | Approved business rules | Rank ≤4 |
| 6 | Approved architecture | Rank ≤5 |
| 7 | Task specification | Planner within mission scope |
| 8 | Verified implementation and evidence | Produced, never asserted |
| 9 | External evidence and donor material | Ingested, never promoted automatically |
| 10 | Agent hypotheses and suggestions | Freely produced, never authoritative |

**Precedence rule.** A lower-precedence artifact (higher rank number) may *inform* a higher-precedence one, but may never modify it. Modification requires a governed change path that terminates in a rank-0 decision. This single rule is the primary defence against donor contamination, stale model memory and conversational drift.

## 2.3 Architectural principles

| Principle | Meaning |
|---|---|
| Intent before implementation | Every mission begins with a durable objective, success definition, constraints and scope. |
| Truth before memory | Project Truth outranks agent memory, conversation history and model opinion. |
| Models are workers | Models are replaceable resources behind stable adapter contracts. |
| Capabilities are governed, not owned | Workers request capabilities; DDE grants scoped, expiring authority. |
| Context is compiled | Workers receive task-specific state, never an undifferentiated project dump. |
| Routing is evidence-driven | Selection uses policy, capability fit, history, cost and risk — in that order of precedence. |
| Verification is independent | The system that generates a change must not be its only judge. |
| Evidence is durable | Findings become artifacts linked to missions, requirements and decisions. |
| External information is evidence | Donor repositories, web content and model output never become truth automatically. |
| Autonomy is bounded | Every autonomous task has scope, permissions, budgets, stop conditions and escalation paths. |
| Complexity must earn its place | Every component is measured; scaffolding is removed when models make it unnecessary. |
| Design for replacement | Tools, workers, storage and model providers are swappable behind contracts. |
| Learn without drifting | Learning changes policies through controlled promotion, never product intent. |
| Cost is measured per verified outcome | Optimise for verified results, not token price. |
| **Every stage ships a working system** | *(new in REV 2.0)* No stage may leave the golden mission unable to run end to end. |

## 2.4 Project Truth artifacts

**Product Constitution** — purpose, target users, non-negotiable constraints, core workflows, UX principles, security principles, architecture principles, explicit exclusions, governance rules. Versioned; changes only through change control.

**Requirement** — stable, testable statement of intended behaviour with constraints and acceptance conditions.

**EDR (Engineering Decision Record)** — context, alternatives, decision, rationale, consequences, affected requirements, approval. Accepted EDRs are immutable; they are superseded, never rewritten.

**Feature DNA** — canonical cross-cutting representation of a feature: purpose, actors, requirements, workflow, states, business rules, algorithms, data model, APIs, UI structure, permissions, events, donor sources, EDR dependencies, security requirements, acceptance tests.

## 2.5 The canonical manufacturing spine

> **This is the normative chain. REV 1.3 stated it four times with three different shapes; this is the only version.**

```
Project Truth
    ↓
Mission
    ↓
TaskGraph                    ← Ch.4  (NEW in REV 2.0)
    ↓
Task
    ↓
ContextPackage               ← Ch.5
    ↓
RouteDecision                ← Ch.6
    ↓
ExecutionPlan                ← Ch.7
    ↓
TaskAttempt → WorkerRun      ← Ch.8, executing inside ExecutionEnvironment + Workspace
    ↓
Artifacts + WorkerEvents + Checkpoints
    ↓
Verification (AcceptanceOracle + tests + invariants)   ← Ch.11
    ↓
Integration (merge queue)    ← Ch.10 (NEW in REV 2.0)
    ↓
Evidence → Outcome → ExperienceRecord
    ↓
Evaluation → controlled policy improvement
```

Subordinate runtime bindings — WorkerSession, CapabilityLease, ExecutionEnvironment, Workspace, ProductEnvironment — never become alternative sources of mission or task truth.

## 2.6 Boundary rules

- **Mission Kernel** owns mission and task state. It does not execute tools.
- **Task Planner** owns graph structure. It does not select workers.
- **Context Intelligence** produces versioned ContextPackages. Workers never redefine project truth.
- **Routing Intelligence** produces a RouteDecision. It does not start a worker and does not know about infrastructure.
- **Execution Planner** converts a RouteDecision into an ExecutionPlan. It is deterministic wherever possible.
- **Worker Manager** resolves a plan into a WorkerRun and invokes an adapter. It does not reason about the task.
- **Capability Plane** grants scoped authority through leases. Selection never implies credentials.
- **Integration Manager** owns the path from a verified workspace to the mainline. Workers never push to a protected branch.
- **Verification** consumes artifacts independently of the generating worker.
- **Experience** is observational. It influences policy only through evaluation and controlled promotion.

## 2.7 What is intentionally not built

No generic agent layer above WorkerRun. No crew-of-agents coordinator. No agent-to-agent conversation fabric for core state transitions. No second task graph runtime. No separate memory system that can outrank Project Truth. No mandatory workflow engine in v1. No microservice split without measured need.

---
---

# Chapter 3 — Canonical object model and schema authority

> **Closes F10 and F11.** REV 1.3's addendum mandated tenancy and RLS but the DDL sketches carried neither, and several contracts appeared in two incompatible versions. REV 2.0 removes the possibility of that class of drift by making the schema a generated artifact.

## 3.1 One schema source of truth

`schemas/` is authoritative. Everything else is generated and verified in CI.

```
schemas/
├── objects/            # JSON Schema 2020-12, one file per durable object
├── events/             # one file per event type, versioned
├── api/openapi.yaml    # generated from objects/ + route definitions
└── sql/                # generated DDL fragments consumed by Alembic
```

**Generation pipeline** — `just contracts`:

```
schemas/objects/*.json
   ├─→ engine/contracts/*.py        (Pydantic v2 models)
   ├─→ schemas/sql/*.sql            (table DDL fragments)
   ├─→ schemas/api/openapi.yaml     (request/response bodies)
   └─→ docs/blueprint/generated/*.md (the object tables in this document)
```

**Rules.**
1. Generated files are committed, never hand-edited. CI fails on drift.
2. A contract change is a schema change plus a migration plus a contract test. Any two without the third is rejected.
3. Additive fields are preferred. A breaking change requires a new schema version and a compatibility test against the previous version.
4. The object tables in Chapters 4–15 of this document are generated from `schemas/objects/`. If prose and schema disagree, the schema wins and the prose is regenerated.

## 3.2 Tenancy and scoping columns — mandatory

Every durable record that can be referenced across a boundary carries scope columns. This is not optional and is not enforced by application code alone.

| Column | Applies to | Enforcement |
|---|---|---|
| `tenant_id` | every table except global registries (`capabilities`, `worker_profiles`, `policies`) | FK + RLS predicate |
| `project_id` | every mission-scoped and runtime table | FK + RLS predicate |
| `mission_id` | every runtime/execution table | FK |

Global registries are tenant-agnostic by design but carry `visibility` (`global` / `tenant`) and a nullable `owner_tenant_id`; a tenant-scoped capability is invisible to other tenants at the query layer.

**Row-level security** is enabled on every tenant-scoped table with a `USING (tenant_id = current_setting('dde.tenant_id')::uuid)` predicate. The application sets `dde.tenant_id` and `dde.project_id` per transaction from the authenticated principal, never from a client-supplied target identifier. A missing setting fails closed — an unset GUC yields no rows.

## 3.3 Stage 1 table set

Migration `0001` creates exactly these. Everything else arrives in the stage that needs it ([Chapter 18](#chapter-18--staged-execution-plan)).

```
tenants, projects, principals, principal_grants
requirements, edrs, product_constitution_versions
missions, task_graphs, task_graph_edges, tasks
context_packages, route_decisions, execution_plans
execution_environments, workspaces
task_attempts, worker_runs, worker_events
artifacts, verification_runs, evidence
events, outbox, command_idempotency
audit_events
```

## 3.4 Identity

> **Decision (REV 1.3 left this open as "UUID/ULID"):** **UUIDv7**, generated in the application, stored as native PostgreSQL `uuid`.

Rationale: time-ordered so B-tree index locality matches insertion order for the append-heavy tables (`worker_events`, `events`, `artifacts`); 128-bit and native, so no `text` primary keys; sortable without a separate sequence; unlike ULID it needs no custom type.

Human-facing identifiers (`MISSION-ERP-000421`, `REQ-AP-019`, `EDR-031`) are a **separate, unique, immutable `slug` column**. They are never primary keys and never appear in foreign keys.

## 3.5 Concurrency control

| Mechanism | Where | Purpose |
|---|---|---|
| `lock_version integer` optimistic lock | `tasks`, `workspaces`, `execution_environments`, `missions`, `task_graphs` | Detect concurrent mutation; `VERSION_CONFLICT` error on mismatch |
| PostgreSQL advisory lock, key = `mission_id` | Mission scheduler/planner | **At most one planner acts on a mission at any instant** |
| Advisory lock, key = `project_id` | Integration/merge queue | Serialise mainline advancement (Ch.10) |
| `SELECT … FOR UPDATE SKIP LOCKED` | Outbox dispatcher, task dispatcher | Safe multi-worker draining |

> **Scale invariant (closes F18).** All control-plane writes occur against one PostgreSQL database and a transaction may span module boundaries. Modules are Python packages, not services; they must not assume network isolation or open independent transactions. This is what makes the transactional outbox correct. Any future service extraction must first prove it can preserve this invariant or replace it with an explicit distributed protocol — that is an EDR, not a refactor.

## 3.6 Repository layout

```
dde/
├── engine/
│   ├── core/            # shared kernel: ids, errors, clock, unit-of-work
│   ├── truth/           # constitution, requirements, EDRs   (sole writer)
│   ├── missions/        # mission kernel + state machine
│   ├── planning/        # TaskGraph + Task Planner            (Ch.4)
│   ├── context/         # DCE: retrieval, assembly, critic    (Ch.5)
│   ├── routing/         # router + policies + simulation      (Ch.6)
│   ├── execution/       # execution planner                   (Ch.7)
│   ├── environments/    # environment registry + provisioning (Ch.7)
│   ├── workspaces/      # worktree lifecycle                  (Ch.7)
│   ├── workers/         # worker manager + registry           (Ch.8)
│   ├── capabilities/    # registry, leases, proxy, broker     (Ch.9, 14)
│   ├── integration/     # merge queue + write scopes          (Ch.10)
│   ├── verification/    # oracle, runners, product envs       (Ch.11)
│   ├── recovery/        # checkpoints, effects, replay        (Ch.12)
│   ├── governance/      # approvals, policy, autonomy budget  (Ch.13)
│   ├── events/          # event store + outbox dispatcher
│   ├── projections/     # mission control read models
│   ├── learning/        # experience records + promotion      (Ch.6.8)
│   ├── knowledge/       # knowledge graph                     (Ch.5.10)
│   ├── audit/
│   ├── contracts/       # GENERATED — do not edit
│   └── gateway/         # transport boundary                  (Ch.15)
├── adapters/            # worker/capability/provider implementations
├── interfaces/          # cli, api, mcp, websocket, dashboard, android
├── schemas/             # SOURCE OF TRUTH
├── migrations/
├── evals/               # context, routing, security, chaos, golden mission
├── tests/               # unit, contract, integration, recovery
├── infra/
└── docs/
    ├── blueprint/
    └── truth/
```

## 3.7 Append-only data, partitioning and retention

> **Closes F17.** `worker_events` and `events` serve two workloads with opposite retention needs: a hot bounded replay window, and a permanent audit ledger.

| Table | Strategy |
|---|---|
| `events` | Declarative partitioning by month on `occurred_at`. Hot partitions in Postgres; partitions older than the retention window detached and exported to R2 as Parquet, catalogued in `event_archives`. |
| `worker_events` | Partitioned by month. Default retention 90 days hot. Events referenced by an unresolved checkpoint or an open evidence record are exempt from detach until released. |
| `audit_events` | Never detached. Hash-chained (`prev_hash`, `entry_hash`) so tampering is detectable. Separate table from `events` precisely because retention differs. |
| `artifacts` | Metadata in Postgres, bytes in R2, content-addressed by SHA-256. Lifecycle policy by artifact class; evidence-linked artifacts are WORM (§17.5). |
| `command_idempotency` | `expires_at` **must exceed** max retry window + max client reconnect window + max mission pause duration. Default 30 days. Expiring a key earlier permits a duplicate mutation, so this value is a policy-versioned constant, not a tuning knob. |

Replay reads only from the hot window. If a replay requires a detached partition, DDE returns `EVENT_WINDOW_EXPIRED` and recovers from the checkpoint plus durable attempt results instead — it never silently reconstructs from partial history.

## 3.8 Object ownership matrix

One authoritative owner per mutable state. One creation authority. No exceptions.

| Object | Owner module | Created by | Mutable after creation | Transaction boundary |
|---|---|---|---|---|
| Project Truth | `truth` | Human governance | Only through governed change | Truth |
| Mission | `missions` | Mission command | Yes, until terminal | Mission |
| **TaskGraph** | `planning` | Task Planner | Versioned; prior versions immutable | Graph |
| Task | `missions` | Task Planner | Lifecycle only | Task transition |
| ContextPackage | `context` | DCE | Versioned; prior versions immutable | Context |
| RouteDecision | `routing` | Router | Immutable | Routing |
| ExecutionPlan | `execution` | Execution Planner | Definition immutable; status mutable | Plan |
| TaskAttempt | `missions` | Attempt creator | Append-only | Attempt commit |
| WorkerRun | `workers` | Worker Manager | Lifecycle only | Run |
| WorkerSession | `workers` | Worker Manager | Yes | Session |
| ExecutionEnvironment | `environments` | Provisioner | Status/config versioned | Environment |
| Workspace | `workspaces` | Execution Planner | Revision changes | Workspace |
| **WriteScopeLease** | `integration` | Task Planner | Status only | Integration |
| CapabilityLease | `capabilities` | Lease manager | Status only; scope immutable | Lease |
| Credential handle | `capabilities/broker` | Credential Broker | Status only | Broker |
| Artifact | `verification` | Worker or capability | Immutable after commit; metadata only | Artifact commit |
| VerificationRun | `verification` | Verification planner | Append-only result | Verification |
| **ProductEnvironment** | `verification` | Verification planner | Lifecycle only | Product env |
| Evidence | `verification` | Verification | Append-only | Evidence |
| ExternalEffect | `recovery` | Capability adapter | Status only | Effect |
| ExperienceRecord | `learning` | Outcome processor | Promotion state only | Learning |
| Approval | `governance` | Authorized principal | Decision immutable; lifecycle mutable | Approval |
| Event | `events` | Owning aggregate transaction | Never | Outbox |

## 3.9 Creation order

```
1  Mission committed
2  TaskGraph v1 committed                          (Ch.4)
3  Task nodes materialised from the graph
4  WriteScopeLeases reserved for schedulable tasks  (Ch.10.3)
5  ContextPackage version compiled                  (Ch.5)
6  RouteDecision committed                          (Ch.6)
7  ExecutionPlan validated and committed            (Ch.7)
8  TaskAttempt created (worker_run_id NULL)
9  Workspace allocated, environment leased
10 WorkerRun created and attached to the attempt in the SAME transaction
11 CapabilityLeases issued, bound to the run
12 Worker starts — only after the run row is durable
13 Artifacts / events / checkpoints append to the run
14 VerificationRun consumes durable outputs         (Ch.11)
15 TaskAttempt finalised
16 Integration proposal enters the merge queue      (Ch.10)
17 Task state changes only after verification + integration outcome
```

Step 10 resolves the circular-create ambiguity: `task_attempts.worker_run_id` **does not exist**. The relationship is carried solely by `worker_runs.task_attempt_id`, which makes the cardinality unambiguous.

> **Cardinality decision (closes F11).** `TaskAttempt : WorkerRun` is **1:N**. An attempt survives environment replacement, worker crash and session loss; each recovery creates a new run within the same attempt. `worker_runs.attempt_number` is removed — run ordinality is `worker_runs.sequence` within the attempt, and attempt ordinality is `task_attempts.sequence` within the task. There is exactly one counter at each level.

## 3.10 Immutable definition, mutable lifecycle

ExecutionPlan, RouteDecision, ContextPackage, CapabilityLease, TaskGraph, AcceptanceOracle and Policy **definitions** are immutable. Runtime state lives in explicit lifecycle columns or associated runtime rows. A material change creates a new version with provenance to its predecessor; it never overwrites.

Each carries a content hash over its definition fields only (`plan_hash`, `decision_hash`, `assembly_hash`, `graph_hash`, `oracle_version`). Hashes exclude lifecycle columns, so a status change never invalidates a hash.

---
---

# Chapter 4 — Mission planning: TaskGraph and Task Planner

> **NEW in REV 2.0 — closes F1.** REV 1.3 specified every link of the manufacturing spine to field level except the one that turns a mission into work. There was no planner contract, no graph object, no granularity policy, no dynamic-discovery rule, and no definition of what `REPLANNING` does to running work. This chapter supplies all five.

## 4.1 Position and constraints

The Task Planner sits between the Mission Kernel and Context Intelligence. It answers exactly one question: **what units of work, in what dependency order, with what write scopes, would satisfy this mission's success definition?**

It does **not** choose workers (Ch.6), allocate environments (Ch.7), or decide how work merges (Ch.10) — though it reserves the write scopes that Ch.10 enforces.

## 4.2 TaskGraph object

```
TaskGraph
  graph_id            uuid  PK
  tenant_id, project_id, mission_id
  version             integer          -- monotonic per mission
  supersedes_id       uuid  NULL
  status              enum
  nodes[]             TaskNode
  edges[]             TaskEdge
  planning_mode       enum(template, model_assisted, human_authored)
  planner_policy_version  text
  rationale           text             -- why this decomposition
  open_questions[]    text             -- unresolved before execution
  graph_hash          text             -- over nodes+edges only
  created_by_principal, created_at
```

```
TaskNode
  task_id             uuid
  title, intent
  task_class          enum   -- see 4.4
  requirement_refs[]  -- traceability is mandatory, not optional
  feature_refs[]
  success_criteria[]           -- observable, becomes AcceptanceOracle input
  expected_write_scope[]       -- paths/modules this task may modify (Ch.10.3)
  expected_read_scope[]        -- hint to the DCE
  blast_radius        enum(none, local, module, cross_module, systemic)
  risk_class          enum(low, medium, high, critical)
  estimated_effort    enum(xs, s, m, l)   -- l is a decomposition failure; see 4.4
  autonomy_ceiling    smallint
  requires_approval   bool
  verification_profile_ref
```

```
TaskEdge
  from_task_id, to_task_id
  edge_type   enum(depends_on, produces_contract_for, verifies, repairs, blocks_on_decision)
  contract_ref  NULL   -- for produces_contract_for: the interface being fixed
```

**Invariants** (enforced in the database and by contract test):
- The graph is acyclic. A cycle is a planning failure, not a runtime failure.
- Every node traces to at least one requirement or is explicitly typed `task_class = enabling` with a parent node reference.
- Every node's `expected_write_scope` is non-empty for implementing classes, and scopes of concurrently schedulable nodes are disjoint (Ch.10.3).
- Every leaf path terminates in a `verifies` edge. A graph with unverified terminal work is rejected.
- `graph_hash` is stable across reordering — it hashes a canonical topological normal form.

## 4.3 Task Planner contract

```
TaskPlanner
  plan(mission, truth_view, repo_map, policy)      -> TaskGraph(status=DRAFT)
  validate(graph)                                  -> ValidationReport
  amend(graph, amendment, reason)                  -> TaskGraph(version+1)
  schedule(graph, capacity, leases)                -> [Task]  ready to execute
  replan(graph, trigger, in_flight_state)          -> ReplanDecision
```

**Determinism split.** `validate`, `schedule` and the write-scope allocation inside `plan` are **deterministic code**. Only decomposition itself — proposing nodes and edges — may use a model, and only in `model_assisted` mode. A proposed graph is not usable until `validate` passes; a model can never emit an executable graph directly.

**Planning modes.**

| Mode | When | Human gate |
|---|---|---|
| `template` | Mission matches a registered mission template (e.g. "add CRUD entity", "add endpoint", "fix failing test") | None |
| `model_assisted` | Novel mission | Graph approval required when any node is `risk_class ≥ high` or `blast_radius ≥ cross_module` |
| `human_authored` | Structural or architectural work | Implicit |

Mission templates are first-class registry objects with their own version and conformance tests. They are the mechanism by which planning gets cheaper and more predictable over time — the deterministic counterpart to routing's learned policy, and available from Stage 1.

## 4.4 Granularity policy

A task is correctly sized when **one worker run can plausibly complete and verify it inside one context window and one budget**. Concretely:

| Rule | Threshold | Enforcement |
|---|---|---|
| Write scope | ≤ 1 module, or ≤ 12 files | `validate` rejects |
| Success criteria | 1–5 observable criteria | `validate` rejects outside range |
| Estimated effort | `xs`/`s`/`m` only | `l` must be decomposed before commit |
| Verification | Must be independently verifiable without a sibling task completing | `validate` rejects |
| Interface tasks | Any task another task depends on must first fix its contract | `produces_contract_for` edge required |

`task_class` values: `discovery`, `specification`, `decision` (produces an EDR), `enabling` (scaffolding/migration), `implementation`, `integration`, `verification`, `repair`, `documentation`.

**Contract-first decomposition rule.** When task B depends on an interface produced by task A, the planner emits an explicit `produces_contract_for` edge and A's success criteria must include committing that interface to `schemas/`. This is what allows A and B to proceed in parallel after A's contract lands rather than serialising the whole chain — and it is the single highest-leverage decomposition rule in the system.

## 4.5 Dynamic discovery — graph amendment

Work reveals work. The Focus Guardian (§13.6) already routes unrelated discoveries to Findings; this section covers discoveries that are *in scope and blocking*.

```
GraphAmendment
  amendment_id, graph_id, proposed_by(run_id|principal)
  amendment_type  enum(add_task, split_task, add_edge, retire_task, widen_scope)
  justification, evidence_refs[]
  affected_task_ids[]
  requested_write_scope[]
```

Rules:
1. A worker may **propose** an amendment; it may never mutate the graph.
2. `add_task` and `add_edge` within the mission's declared scope and below the mission autonomy ceiling are auto-accepted by `validate` — this is the normal case and must not require a human.
3. `widen_scope` beyond the mission's `scope` array, or any amendment raising a node above the autonomy ceiling, requires approval.
4. Accepting an amendment produces `version + 1`. The prior version is retained; `supersedes_id` links them.
5. Amendment rate is a monitored metric. Sustained high amendment rate means decomposition quality is poor and is a promotion gate for planner templates (§4.10).

## 4.6 Replanning semantics

> The state `REPLANNING` existed in REV 1.3 with no definition. This is it.

`replan` is triggered by: repeated verification failure on a node, a `SPECIFICATION_FAILURE`, an accepted EDR that invalidates prior assumptions, a `DRIFT_FAILURE`, or an operator command.

`ReplanDecision` classifies **every in-flight and completed node**:

| Disposition | Meaning | Effect on in-flight run |
|---|---|---|
| `PRESERVE` | Node and its durable results remain valid | Run continues |
| `QUIESCE` | Node valid, but must checkpoint and stop before the new graph applies | Graceful pause → checkpoint → PAUSED |
| `SUPERSEDE` | Node replaced by new node(s); results remain as evidence | Cancel run, retain artifacts, mark attempt `SUPERSEDED` |
| `RETIRE` | Node no longer needed | Cancel run; workspace discarded; artifacts retained as evidence |
| `REVERT` | Node's merged output must be undone | Requires an explicit revert task in the new graph (Ch.10.7) |

Hard rules:
- Replanning **never** silently discards durable results. Every `SUPERSEDE`/`RETIRE` produces an evidence record explaining why.
- Replanning **never** rewrites merged history. Undo is a new task with a new commit, never a force-push (Ch.10.7).
- Replanning cannot proceed while any affected node holds an unreconciled `ExternalEffect` in `UNKNOWN` status (Ch.12.4). Reconcile first, then replan.
- Write-scope leases held by `RETIRE`/`SUPERSEDE` nodes are released only after their workspaces are discarded, preventing a new task from writing into a scope a dying run still holds.

## 4.7 Scheduling and concurrency

`schedule(graph, capacity, leases)` is deterministic and returns tasks that satisfy **all** of:

1. All `depends_on` predecessors are `COMPLETED` **and integrated** (Ch.10) — not merely verified.
2. All `produces_contract_for` predecessors have committed their contract.
3. A `WriteScopeLease` covering the node's `expected_write_scope` is obtainable without conflict.
4. Mission and tenant concurrency limits allow another run.
5. The node is not `blocked_on_decision` with an unresolved approval.

Concurrency is bounded at three levels — per mission (default 4), per project (default 8), per tenant (configurable) — because unbounded parallelism against one repository produces merge thrash, not throughput.

## 4.8 Graph and task state machines

```
TaskGraph:  DRAFT → VALIDATING → APPROVED → ACTIVE → COMPLETED
            DRAFT|VALIDATING → REJECTED
            ACTIVE → AMENDING → ACTIVE
            ACTIVE → REPLANNING → (new version ACTIVE, this one SUPERSEDED)
```

```
Task:  CREATED → BLOCKED → READY → CONTEXT_READY → ROUTED → PLANNED
       → EXECUTING → VERIFYING → INTEGRATING → COMPLETED
       VERIFYING     → REPAIR_REQUIRED → PLANNED
       INTEGRATING   → MERGE_CONFLICT  → PLANNED           (Ch.10.5)
       EXECUTING     → RETRYING → PLANNED
       EXECUTING     → REROUTING → ROUTED
       any           → BLOCKED_ON_DECISION → READY
       any           → SUPERSEDED | RETIRED                (via replan)
```

`INTEGRATING` is new in REV 2.0 and is the state in which most real autonomous systems fail silently. A worker **cannot** transition task state; only the Mission Kernel can, in response to verification and integration outcomes.

## 4.9 Blocking and failure propagation

- A node entering `BLOCKED_ON_DECISION` blocks only its transitive dependents. Independent branches continue — this is what makes overnight autonomy viable (§13.3).
- A node failing terminally marks dependents `BLOCKED`, and the mission enters `PARTIAL` rather than `FAILED` if any branch can still make progress.
- A mission is `COMPLETED` only when every non-retired node is `COMPLETED` **and integrated** **and** the mission-level AcceptanceOracle passes (§11.3). Node-level success does not imply mission success.

## 4.10 Planner evaluation

The planner is a measured subsystem like the router and the DCE.

| Metric | Meaning | Gate |
|---|---|---|
| Amendment rate | Amendments per completed mission | Rising rate blocks template promotion |
| Decomposition depth error | Nodes needing split after execution began | ≤ 15% for template promotion |
| Parallel efficiency | Wall-clock vs. sum of task durations | Tracked; informs concurrency limits |
| Merge conflict rate | Conflicts per integrated task | > 10% means write scopes are wrong, not that merging is hard |
| Traceability completeness | Nodes with requirement linkage | 100%, mandatory |
| Replan frequency | Replans per mission | High rate indicates specification quality problems upstream |

## 4.11 Acceptance tests

- A mission with two independent branches, one blocked on approval, continues the other branch to completion.
- Two tasks with overlapping `expected_write_scope` are never scheduled concurrently.
- A worker proposing an out-of-scope amendment is denied and the proposal is recorded as a Finding.
- Replanning during an in-flight run with an `UNKNOWN` external effect is refused until reconciliation completes.
- A graph containing a cycle, an unverified terminal node, or an untraceable node is rejected at `validate`.
- Superseding a node preserves its artifacts and produces an evidence record.

---
---

# Chapter 5 — Context Intelligence

> **Closes F15.** REV 1.3 specified the ContextPackage contract, provenance and promotion gates but not the mechanism: no chunking, no index lifecycle, no rank fusion, no eviction order, and no labeling protocol for the ground truth its promotion gate depends on.

## 5.1 Pipeline

```
Task + expected_read_scope
  ↓ Discovery        — resolve explicit refs, requirements, EDRs, feature DNA
  ↓ Candidate retrieval  — parallel retrievers (5.2)
  ↓ Fusion + ranking     — reciprocal rank fusion + authority weighting (5.3)
  ↓ Authority/freshness filter (5.5)
  ↓ Conflict adjudication (5.6)
  ↓ Assembly under budget (5.7)
  ↓ Coverage check (5.8)
  ↓ Context Critic — only when triggered (5.9)
  ↓ ContextPackage (versioned, hashed, provenance-bearing)
```

## 5.2 Retrievers

| Retriever | Implementation | Cost class |
|---|---|---|
| Explicit reference | Direct fetch by ID/path | free |
| Authority retriever | Requirements, EDRs, business rules linked in the knowledge graph | cheap |
| Lexical | ripgrep over the working tree, ranked by BM25 | cheap |
| Structural | Tree-sitter symbol index; definition, references, call/import neighbourhood | cheap |
| Dependency | Import graph closure at depth ≤ 2 from touched symbols | cheap |
| Semantic | pgvector over chunk embeddings | moderate |
| Graph | Knowledge-graph traversal from requirement → feature → symbol → test | cheap |
| Temporal | `git log`/blame on the write scope; recent change history | cheap |
| Documentation | Version-pinned external docs | moderate |
| Visual | Screenshot/DOM/style evidence for UI tasks | moderate |

**Stage 1 uses only the free and cheap retrievers.** Semantic retrieval arrives in Stage 3 and must demonstrate uplift on the eval corpus (§5.10) against a lexical+structural baseline before it is enabled by default. This ordering is deliberate: embeddings are the most expensive and least debuggable retriever, and in code retrieval they frequently lose to a well-scoped structural index.

## 5.3 Chunking and fusion

**Chunking.** Code chunks on syntactic boundaries via Tree-sitter — function, method, class, or top-level block — never fixed token windows. Each chunk carries `file_path`, `symbol_path`, `start_line`, `end_line`, `language`, `content_hash`, `commit_sha`. Documents chunk on heading boundaries. A chunk that exceeds the model-agnostic size ceiling is split at the next nested boundary, never mid-statement.

**Fusion.** Retrievers return ranked lists scored independently. Combine with reciprocal rank fusion, then apply multiplicative weights: authority rank (Ch.2.2), freshness, and write-scope proximity. Rationale: RRF needs no score calibration across heterogeneous retrievers, which matters because BM25, cosine similarity and graph distance are not comparable quantities.

Weights are a versioned `context_policy`, not constants in code.

## 5.4 Index lifecycle

| Concern | Rule |
|---|---|
| Build | Full index on project registration; incremental thereafter. |
| Incremental update | On every integrated commit, reindex only changed files and their structural dependents. Triggered by the integration manager (Ch.10), not by a timer. |
| Invalidation | Chunk identity is `(file_path, symbol_path, content_hash)`. A changed hash invalidates the chunk and every derived embedding. |
| Embedding model version | Stored on every vector row. A model change **does not** silently reindex: it creates a new `index_version`, backfills in the background, and switches only when the eval corpus shows no regression. Two index versions may coexist. |
| Staleness | Every ContextPackage records `index_version` and `index_lag_commits`. Compiling context against an index more than N commits behind the workspace base revision emits a warning and, above a policy threshold, blocks autonomous execution. |
| Deletion | Deleted files tombstone their chunks; they remain queryable as historical evidence but can never satisfy a current-state requirement. |

## 5.5 Freshness and authority

Every context item carries `source`, `authority_rank`, `relevance`, `confidence`, `freshness_at`, `scope`. Sources declare a freshness window by class: Project Truth (no expiry), code (current commit only), external documentation (version-pinned), donor evidence (immutable, never current-state), visual evidence (bound to a build).

A stale source may remain in the package **as historical evidence**, explicitly labelled, but it cannot satisfy a current-state coverage requirement.

## 5.6 Conflict adjudication

When two items of authority rank ≤ 6 contradict each other, the DCE **must not merge or silently prefer one**. The package enters `CONFLICTED` with a `ContextConflict` record naming both items, the contradiction type and the affected success criteria. Resolution is: retrieve resolving evidence, raise an EDR/decision task (`blocks_on_decision` edge in the graph), or escalate to human authority. Autonomous execution on the affected task is blocked until resolved.

Conflicts between rank-9/10 items (donor material, model suggestion) are not conflicts; both are recorded as evidence with provenance.

## 5.7 Budget and eviction

`context_budget` is expressed in tokens and set by the ExecutionPlan from the worker profile's capacity, minus a reserve for worker output and just-in-time expansion.

Eviction order when over budget — **evict from the bottom**:

```
10  agent hypotheses
 9  donor / external evidence
 8  historical/temporal context
 7  semantically-similar-but-unlinked code
 6  dependency closure beyond depth 1
 5  sibling module code
 4  tests for untouched code
 3  architecture context beyond the touched components
--- never evicted below this line ---
 2  domain rules and business rules in scope
 1  requirements, accepted EDRs, success criteria, verification plan
 0  the write scope itself and its direct dependencies
```

If the un-evictable set alone exceeds budget, that is a **decomposition failure**, not a context failure: the DCE returns `CONTEXT_BUDGET_EXCEEDED` and the task is returned to the planner for splitting. This coupling between context budget and task granularity is why Chapter 4's sizing rules exist.

> **Optimisation target (correcting a REV 1.3 ambiguity).** Assembly optimises for verified outcome, not minimum tokens. A smaller package that causes a repair loop is more expensive than a larger one that does not. The eval corpus measures both.

## 5.8 Coverage contract

Every ContextPackage declares coverage against the task's success criteria:

```
coverage:
  authoritative_requirements   : satisfied | partial | missing
  applicable_domain_rules      : ...
  impacted_code_and_deps       : ...
  architecture_constraints     : ...
  security_constraints         : ...
  verification_obligations     : ...
  known_unresolved_questions   : listed
```

Any `missing` on a required category blocks autonomous execution and triggers retrieval, research or escalation. `partial` is permitted below a risk threshold and is recorded for failure attribution (§5.11).

## 5.9 Context Critic — triggered, not default

A second reasoning pass is expensive and slow. It runs when **any** holds: `risk_class ≥ high`; `blast_radius ≥ cross_module`; coverage contains `partial` on a required category; the task is a repair of a previously context-attributed failure; or confidence is below the policy threshold.

The critic may only request additional retrieval or raise a Context Finding. It cannot alter Project Truth and cannot approve its own request. Its cost counts against the control-plane overhead budget (§16.4).

## 5.10 Knowledge graph — derived vs asserted edges

> **Closes F16.** Code-symbol edges rot on every commit; without this split the traceability gate passes against stale data.

| Edge class | Examples | Lifecycle | Audit weight |
|---|---|---|---|
| **Asserted** | requirement→feature, requirement→EDR, task→requirement, evidence→requirement, decision→consequence | Durable, versioned, human- or governance-created | Full — usable as traceability proof |
| **Derived** | symbol→symbol, test→symbol, file→module, requirement→symbol (inferred) | Recomputed per integrated commit, disposable, never versioned | Advisory only — never sole proof of traceability |

Every derived edge carries `derived_at`, `derived_from_commit`, `deriver_version`. Graph staleness (share of derived edges older than the head commit) is a monitored metric. The release-checklist question *"can DDE detect drift?"* is answered against asserted edges plus fresh derived edges only.

## 5.11 Failure attribution

Verification and recovery record whether a failure was plausibly caused by context omission, contradiction, staleness, contamination or mis-ranking. This becomes the primary DCE learning signal **and** the exclusion filter for routing learning (§6.8) — a failure attributed to context must not teach the router that a worker is weak.

Attribution is produced by a deterministic rule set first (was a required category `partial`? did the worker request context that existed but was not supplied? did it edit outside the supplied scope?) and only falls back to a model judgment when the rules are inconclusive. Rule-derived attributions carry higher confidence and are the only ones eligible to gate policy promotion.

## 5.12 Just-in-time expansion

```
ContextRequest: request_id, run_id, task_id, reason, requested_refs[],
                requested_capabilities[], urgency, expected_use
ContextResponse: approved_refs[], denied_refs[], reason_codes[],
                 context_revision, caveats[]
```

A request is evaluated against task scope, policy and budget. A worker can never convert a context request into unrestricted repository access. Denials are normal control outcomes, recorded, and counted — a high denial rate means the initial package or the task scope is wrong.

## 5.13 Evaluation corpus and promotion gates

**Corpus construction protocol** — the part REV 1.3 omitted, without which the omission-rate gate is unmeasurable:

1. Source cases from **real completed missions**, not synthetic ones. A case is a task plus its repository state at that commit.
2. Ground truth "required context" is defined **retrospectively from the accepted diff and its verification**: every file, symbol, requirement, EDR and domain rule that the accepted change actually touched or depended on. This is mechanically derivable and does not require a human to guess relevance beforehand.
3. A human reviews and adjusts each case once; the case is then frozen with a version.
4. Minimum viable corpus: **60 cases** spanning at least 6 task classes, with ≥ 10 adversarial cases (contradictory sources, stale documentation, near-duplicate symbols, donor contamination, ambiguous requirement).
5. Corpus grows from production; cases are never deleted, only retired with reason.

**Promotion gates for a new context policy** — all must hold against the current certified baseline:

| Gate | Threshold |
|---|---|
| Critical coverage | No regression on required categories |
| Context-attributed failure rate | No regression |
| Contradiction rate | No regression |
| Task success on corpus | No regression, improvement preferred |
| Token cost per verified success | Not a gate on its own; reported alongside success |

A policy that reduces tokens while increasing repair loops fails promotion. That is the entire point of measuring cost per *verified* outcome.

---
---

# Chapter 6 — Routing Intelligence

> **Closes F5, F6, F7.** REV 1.3 made a simulation-trained router the day-one routing mechanism. Its parameters had to be hand-authored before any real data existed, its validity check could only run after that data arrived, and its promotion gates required volumes a new deployment will not reach for a long time. REV 2.0 keeps every routing capability — simulation, shadow learning, canary promotion, rollback — but re-orders them so the system routes correctly on day one and learning activates when it is genuinely justified.

## 6.1 Routing pipeline — the single normative version

> REV 1.3 stated this three times (§11.1, §40.3, §75.3) with different shapes. This is the only version.

```
0  HARD POLICY GATE          production writes, secrets, destructive ops, financial impact
1  CAPABILITY REQUIREMENTS   which capabilities must be satisfiable
2  WORKLOAD CLASSIFICATION   what kind of work this is
3  WORKER ELIGIBILITY        certified profiles that can satisfy 1+2
4  ENVIRONMENT COMPATIBILITY OS/arch/toolchain/device/network/modality
5  CAPACITY & AVAILABILITY   health, quota, concurrency, budget headroom
--- hard gates end; a candidate surviving to here is legal ---
6  PERFORMANCE ESTIMATE      expected success, rework, latency
7  ECONOMIC SCORE            expected cost per verified success
8  ROUTE CRITIC              triggered, not default (6.6)
9  ESCALATION / FALLBACK     ordered recovery route
→  RouteDecision
```

**Hard-gate rule.** A candidate that fails any of gates 0–5 is removed, not penalised. No economic score can compensate for a policy, capability, environment, capacity or security violation. Gates 6–9 only ever reorder legal candidates.

## 6.2 The v1 router is deterministic and explicit

Stage 1–3 route with a **declared policy table**, not a learned or simulated model.

```yaml
# policies/routing/deterministic-v1.yaml   (versioned, hash-pinned, rollback-able)
version: 1
workload_classes:
  bulk_implementation:
    prefer:  [profile.longcontext_economy, profile.general_implementation]
    require: [capability.repository, capability.testing]
    max_risk: medium
  architectural_reasoning:
    prefer:  [profile.premium_reasoning]
    require: [capability.repository]
    min_risk: high
  verification:
    prefer:  [profile.deterministic_runner]
    forbid:  [profile.any_generator_of_the_change_under_test]   # independence, Ch.11.4
  visual_analysis:
    prefer:  [profile.vision]
    require: [capability.browser, modality.image]
escalation:
  on_verification_failure: {after: 2, to: profile.premium_reasoning}
  on_worker_unavailable:   {to: next_eligible_by_score}
  on_ambiguity_high:       {to: human_decision_task}
```

Every decision emits **reason codes** — an operator sees not only which profile was chosen but whether it was chosen by policy, capability fit, availability, cost or escalation. Explainability is a Stage 1 requirement, not a Stage 5 feature.

**Cost tiers (additive, operator-facing).** A caller may set `cost_tier` (`low | medium | high | xhigh | max`) on a route evaluation. The tier **reorders the declared `prefer[]` of the matched workload class before gates 6–7 rank survivors** — `low` promotes economy-class profiles, `high`/`xhigh`/`max` promote premium-class ones, `medium` is the declared order. Tier membership is declared metadata on the profile; it never changes gate outcomes: a tier can reorder legal candidates but can never resurrect one the hard gates eliminated ("gates 6–9 only ever reorder legal candidates"). Every tiered decision records `COST_TIER:<tier>` in its `reason_codes`. Until real cost telemetry exists (Ch.6.5's actual-cost gap), band membership is derived from declared profile naming (`*_economy`, `premium_*`) and is replaced by measured cost bands once that gap closes.

**Degraded-mode default (development only, additive).** When zero candidates survive the hard gates due to a capacity/availability-class failure, the router may — only in the `development` environment class, only when explicitly enabled (`routing.degraded_default`), and never when the failure is a gate-0 hard-policy denial (which is a governance outcome, not an outage) — select a declared degraded default profile instead of escalating, recording `DEGRADED_DEFAULT_APPLIED` in `reason_codes`. In every non-development environment class the behaviour is unchanged: `NO_ELIGIBLE_WORKER` escalates to a human-decision task, because the absence of a legal candidate is information, never a routing error to paper over.

**Mission-affinity tie-break (additive).** Within a mission, the router may prefer the profile it last selected for a sibling task as a tie-break among survivors — subordinate to the declared `prefer[]` order, which always outranks it, and recorded as `MISSION_CONTINUITY` in `reason_codes`. Affinity never rewrites the recorded candidate ranking (the audit trail keeps the declared order) and can never select a profile the hard gates eliminated.

**Why this rather than a simulator.** A hand-authored policy table and a hand-parameterised simulator encode the same knowledge — the author's priors. The table is inspectable, diffable, unit-testable, instantly changeable and honest about being a heuristic. The simulator wraps the same priors in machinery whose validity cannot be assessed until the real data arrives that would make it unnecessary. The simulator is therefore kept for what it is genuinely good at (§6.4).

## 6.3 RouteDecision

```
RouteDecision
  decision_id, tenant_id, project_id, mission_id, task_id
  candidates[]              { profile_id, gate_results[], eliminated_at_gate, scores{} }
  selected_worker_profile_id
  workload_class, required_capabilities[], required_environment_class
  reason_codes[]
  predicted_success, predicted_cost, predicted_latency, confidence
  selection_source     enum(deterministic, shadow, canary, promoted_historical, exploration)
  selection_propensity numeric        -- 6.7; 1.0 for deterministic selections
  fallback_plan[], escalation_plan[]
  policy_version, decision_hash, created_at
```

`candidates[]` records **every** evaluated profile with the gate at which it was eliminated. This is the counterfactual substrate — without it, no off-policy evaluation is possible later, and it costs nothing to record now. Recording it from Stage 1 is the single irreversible decision in this chapter.

## 6.4 Routing Simulation Model — re-scoped

The RSM is **retained** and **repositioned**: it is an evaluation and fixture-generation subsystem, never a training source for a production policy and never an authority.

| RSM is used for | RSM is not used for |
|---|---|
| Generating adversarial routing fixtures (worker outage, capability gap, modality mismatch, budget exhaustion, environment incompatibility) | Producing the day-one production policy |
| Regression-testing policy changes before deployment | Estimating real success probabilities |
| Stress-testing escalation and fallback chains | Any promotion evidence |
| Cold-start sanity checks on new workload classes | Any calibration claim |

It generates `ExperienceRecord`s with `experience_origin = simulation`, which are **excluded by construction** from any dataset used to train or promote a production policy. Simulation seeds, parameter sets and model versions are persisted for reproducibility.

## 6.5 Real telemetry from day one

Even under deterministic routing, DDE records for every decision: candidate set with elimination gates, predictions, selection propensity, actual verified outcome, verification confidence, rework count, escalation, human intervention, actual token/tool cost, elapsed time, failure class, recovery path, context policy version, capability set, and the attribution from §5.11.

This is cheap, must never be skipped, and is the only thing that makes later learning possible without an architectural migration.

> **Health-based eviction and fallback (amended 2026-08-22; owner queue-closure decision).** Recorded telemetry outcomes are the input to routing health, not merely training data. The deterministic router **shall** maintain per-profile health derived from recorded outcomes and evict a profile from the eligible set when its health falls below policy threshold, substituting the profile's declared fallback chain — ordered candidates declared in advance, never improvised at failure time. Eviction is a gate-5 outcome: it removes a candidate, it does not reorder survivors, and it is recorded in `reason_codes` like any other elimination. Health recovers only through new recorded outcomes, never through operator override of the recorded data.

> **Flaky-check quarantine (amended 2026-08-22; owner queue-closure decision).** A check whose flake rate exceeds threshold (§11.8) is quarantined from routing-learning eligibility and from blocking verification verdicts, and moves to a two-tier verification cadence: it runs on the slow tier out-of-band for signal repair, and on the fast tier as advisory-only, until its measured flake rate returns under threshold. Quarantine is a measured, reversible state — never a silent deletion of the check and never a retry into green.

**Shadow-mode policy promotion keys on success-yield (landed 2026-08-22; commit `ae970f5`).** A shadow policy is replayed against its evaluation window's real decisions and each replayed pair lands in exactly one of four measured quadrants; the promotion verdict derives from those quadrant counts, not from `success_yield` alone (routed-and-passed over all decisions), which rises under permissiveness. A candidate can no longer win by approving more — it must pass where it routed and fail where it declined.

## 6.6 Route Critic — triggered

Runs when: `risk_class ≥ high`; financial, security or production blast radius; a prior attempt on this task failed verification; or predicted-success confidence is below threshold. It may upgrade a route or force escalation; it can never downgrade below a hard gate. Its cost counts against the overhead budget (§16.4).

## 6.7 Exploration and propensity

> **Closes F6.** Off-policy evaluation over data generated by a deterministic argmax policy is not valid: alternative arms have zero support and no propensities are recorded.

- Every RouteDecision records `selection_propensity`.
- An **exploration budget** applies only to tasks with `risk_class = low`, `blast_radius ≤ module`, cost below a ceiling, and a fully idempotent write scope. Default ε = 0.05, configurable, defaults to 0 in production tenants until explicitly enabled.
- Exploration selects uniformly among *eligible* candidates only — it never violates a hard gate.
- Estimators permitted for offline comparison: inverse propensity scoring and doubly-robust, each requiring stated overlap and coverage conditions. An estimate without adequate overlap is reported as **insufficient evidence**, never as a point estimate.

Without exploration enabled, learned routing may still be evaluated in shadow mode, but §6.9 promotion is capped at "no worse than baseline" claims — uplift claims require overlap.

## 6.8 Learning eligibility and credit assignment

> **Closes F7.** A verified failure is not automatically a routing failure.

An `ExperienceRecord` is eligible for routing training only when all hold:

1. `experience_origin = real` (never simulation).
2. `verification_confidence` is above threshold — a failure detected by a flaky or low-confidence verifier does not teach the router anything.
3. `failure_attribution` (§5.11) is `route_attributable` or `none`. Failures attributed to context, environment, tool, specification or upstream dependency are **excluded**, or included with a down-weight only when attribution confidence is low and the record is flagged.
4. The outcome is terminal — no in-flight or superseded attempts.

`ExperienceRecord` carries: `experience_origin`, `routing_policy_version`, `candidate_set_hash`, `selection_propensity`, `prediction_vector`, `observed_outcome_vector`, `verification_confidence`, `failure_attribution`, `attribution_confidence`, `holdout_partition`, `promotion_evidence_refs[]`, `drift_snapshot_id`, `learning_run_id`.

## 6.9 Learning activation — staged, not scheduled

`routing.mode` progresses through: `deterministic` → `shadow_learning` → `canary` → `promoted_historical`, with `ROLLBACK` reachable from any state, returning to the **last certified policy** and never to an untested fallback.

Activation gates (defaults; configuration, not product truth; raise-able per tenant by governance):

| Gate | Default | Mandatory |
|---|---|---|
| Eligible real attempts per workload class | 300 | yes |
| Eligible real attempts, global | 1,200 | yes |
| Verification-backed outcome coverage | ≥ 90% | yes |
| Calibration on holdout | Brier/ECE below configured threshold | yes |
| Holdout uplift vs deterministic baseline | No material regression; uplift preferred | yes |
| Safety regressions attributable to learned routing | Zero | mandatory |
| Fallback robustness under worker outage | Demonstrated | mandatory |
| Distribution drift | Within monitored bounds | yes |
| Propensity overlap (if uplift is claimed) | Adequate on the evaluated slice | conditional |

> Thresholds were lowered from REV 1.3 (500/class, 2,000 global) because they are now **per eligible record** after attribution filtering, which is a stricter and smaller population — and because deterministic routing is the certified baseline rather than a stopgap, so activation is an optimisation rather than a rescue.

Promotion sequence: `OBSERVE → TRAIN → OFFLINE EVALUATE → SHADOW → HOLDOUT EVALUATE → APPROVAL → LIMITED CANARY → MONITOR → PROMOTE | ROLLBACK`. No learned router promotes directly from training metrics. The previous policy remains deployable throughout the rollback window.

> **Offline warmup before online learning; frozen-first rollout** *(amended 2026-08-24, from the Orca-router research; `docs/planning/orca-routing-research-integration.md`)*. A candidate policy's offline phase MUST be a full-information fit over eligible recorded decisions before any partial-information update path may exist, and the first promotable mode is frozen exploitation — continued online updating requires an explicit configuration switch and its own canary evidence. Promotion additionally asserts the learner beats the best **constant** policy on the identical evaluation window, not merely the incumbent policy table.

## 6.10 Routing evaluation suite

Simulator fixture validity · cold-start safety · calibration · policy safety (can the learner ever violate a hard gate — must be structurally impossible, not merely unobserved) · shadow agreement · holdout uplift · worker-outage degradation · distribution shift detection · exploration containment (exploration never touches a high-risk task).

---
---

# Chapter 7 — Execution plan, environment and workspace

> **Closes F4.** REV 1.3 required side-effecting capability calls to pass through a DDE proxy. That is unachievable for third-party agent harnesses that ship their own shell, filesystem and browser tools. REV 2.0 states the enforcement model that actually works.

## 7.1 ExecutionPlan

```
ExecutionPlan
  plan_id, tenant_id, project_id, mission_id, task_id
  route_decision_id, context_package_id
  worker_profile_id, execution_environment_id, workspace_policy
  capability_requirements[], enforcement_tier   -- 7.2
  autonomy_level, resource_budget, time_budget, token_budget
  attempt_budget                                -- durable ceiling, amended 2026-08-22
  network_policy, filesystem_policy
  verification_plan_id, acceptance_oracle_id
  write_scope_lease_id                          -- Ch.10.3
  checkpoint_policy, retry_policy, escalation_policy
  plan_hash, status, created_at/approved_at/started_at/ended_at
```

The RouteDecision answers *which worker*. The ExecutionPlan answers *exactly how it may act*. Keeping these separate is what stops the router from accumulating infrastructure, secrets and recovery concerns.

**Planner steps** (deterministic): verify the profile is certified for the exact model+harness+toolset+environment tuple · select a compatible environment · allocate a workspace · resolve capabilities to implementations · request minimum leases · bind context and oracle · compute budgets · select policy-permitted fallbacks · hash and persist **before** execution.

**Attempt budgets are durable plan state (amended 2026-08-22).** The attempt ceiling lives on the persisted, hashed ExecutionPlan — not as a caller parameter and not in process memory — so a restart, a replan, or a different dispatcher cannot silently widen it. At dispatch, the remaining budget is checked against the durable plan: a dispatch beyond the ceiling is refused and classified `BUDGET_EXCEEDED` on the attempt (Ch.12.3), which routes to the pause-for-human recovery path rather than a retry.

## 7.2 Enforcement tiers — the correction

Capability authority is decided by the lease. **How that decision is enforced depends on what is executing.**

| Tier | Applies to | Enforcement mechanism | Revocation latency |
|---|---|---|---|
| **T1 — Brokered** | DDE-native capabilities and MCP-brokered tools | Every call passes through the capability gateway: lease validated, scope checked, effect journalled, credential brokered per call | Immediate — next call fails closed |
| **T2 — Contained** | Third-party agent harnesses with their own tool planes (shell, file edit, browser, their own MCP clients) | The **ExecutionEnvironment is the enforcement boundary**: container/microVM isolation, workspace-only bind mount, read-only system paths, non-privileged user, seccomp profile, resource limits, and an **egress proxy that terminates all network traffic** with per-environment allowlists | Bounded — revocation kills the egress allowlist entry and terminates the run |

**T2 rules, mandatory for any autonomous run:**
1. **Zero ambient credentials.** No provider token, cloud credential, SSH key or registry login exists in the environment's filesystem or environment variables. Credentials are obtained per operation via the brokered path (T1) or injected into a proxied request by the egress proxy, never handed to the process.
2. **All egress through the proxy.** DNS is pinned to the proxy resolver; direct IP egress is dropped. The allowlist is derived from the ExecutionPlan's capability set, not from the worker's request.
3. **Git access is proxied.** The worker pushes to a DDE-managed remote, never to the origin. Mainline access belongs to the integration manager (Ch.10).
4. **The workspace is the only writable path** besides `/tmp` with a size cap.
5. **Egress proxy logs are effect records.** Every allowed request is journalled with run, lease and effect identity — this is how a T2 worker's side effects remain auditable despite not passing through the T1 gateway.
6. **Termination reaches the process (amended 2026-08-22; owner queue-closure decision).** Arming run stop sweeps every registered run-scoped process handle through the escalation ladder — terminate, then grace period, then kill — so "stop" for third-party harnesses means the worker's processes are actually gone, not merely denied new credentials. Network egress cutoff and container-level containment at stop are **not** covered by this amendment; they remain open under forthcoming EDR candidate EDR-0011.

`enforcement_tier = audit_only` exists for local development and simulation and is **rejected by configuration validation** in any environment class other than `development` (§13.7).

## 7.3 ExecutionEnvironment

```
ExecutionEnvironment
  environment_id, tenant_id
  class          enum(research, development, security, staging, production)
  type           enum(local, docker, microvm, vm, device, ci_runner, remote_api)
  os_family, architecture, runtime_image, image_digest
  toolchain_manifest, toolchain_manifest_hash
  resource_limits, network_policy, filesystem_policy
  isolation_level enum(process, container, gvisor, microvm)
  credential_profile_id, security_profile_id
  capability_compatibility, worker_compatibility
  status, health_status, lifecycle_state
```

> **Correction:** REV 1.3's DDL omitted `class`, which its own security chapter required. `class` and `type` are orthogonal and both are mandatory: `class` is the security posture, `type` is the substrate.

**States:** `PROVISIONING → READY → ACTIVE → DRAINING → RETIRED`; any → `FAILED → REPAIRING | REPLACEMENT`. No run is scheduled into `DRAINING` or `FAILED`.

## 7.4 Provisioning economics

> Making the environment the enforcement boundary makes provisioning latency a first-order concern that REV 1.3 never addressed.

| Mechanism | Rule |
|---|---|
| Warm pool | Maintain N ready environments per common `(class, image_digest)` tuple. Default N=2 per active project. |
| Image discipline | One base image per environment class, pinned by digest. Toolchain changes produce a new digest and trigger re-certification (§8.5). |
| Reuse policy | An environment may serve multiple sequential runs of the **same tenant and project** only if the workspace is destroyed and recreated between runs and no credential material was ever present. Cross-tenant reuse is forbidden. |
| Teardown | Destroyed after its run unless pooled. Destruction never destroys artifacts or evidence — those are already in R2. |
| Budget | Environment CPU-seconds and provisioning latency are tracked per mission and count toward the overhead budget (§16.4). |

Cold provisioning above the policy threshold (default 45 s) raises an operational alert, because slow provisioning silently destroys the economics of fine-grained tasks.

## 7.5 Workspace

```
Workspace: create(base_revision, policy) · read(path) · write(path) ·
           execute(command) · capture_revision() · snapshot() · cleanup()
```

Normally a Git worktree bound to one environment and one task, branched from the **mission integration branch** (Ch.10.2). Identity and revision are recorded on the WorkerRun and every checkpoint.

The boundary must prevent path escape, symlink escape, access to another project's repository or another task's workspace, and reads of credential paths. These are security failures, not worker failures, and the Flight Lab attempts all of them (§19.2).

Workspace creation, cleanup and recovery are performed by DDE, never by the worker.

**Future-state scrubbing is opt-in policy (landed 2026-08-22; commit `81546d1`).** A workspace created under a policy that enables it has its *future state* — worktree metadata that would let a run see or resume another run's in-progress state — scrubbed before first use. The default remains off because shared-store garbage collection makes unconditional scrubbing hazardous; when enabled it happens at provisioning time, inside DDE, never by the worker.

---
---

# Chapter 8 — Worker contract and certification

## 8.1 WorkerAdapter — the single normative contract

> REV 1.3 published two incompatible adapter signatures (§14A and §41.1). This is the only one.

```
WorkerAdapter
  register()                                    -> Registration
  health()                                      -> WorkerHealth
  capabilities()                                -> CapabilityManifest
  prepare(execution_plan, context_ref, env_ref) -> PreparedRun
  start(worker_run)                             -> RunHandle
  status(worker_run)                            -> RunStatus
  request_pause(worker_run)                     -> PauseResult
  resume(worker_run, checkpoint_ref)            -> ResumeResult
  checkpoint(worker_run)                        -> CheckpointRef
  cancel(worker_run, reason)                    -> CancelResult
  collect_artifacts(worker_run)                 -> ArtifactManifest
  collect_usage(worker_run)                     -> UsageRecord
  terminate(worker_run)                         -> TerminationResult
  cleanup(worker_run)                           -> CleanupResult
```

Adapters are the **only** place vendor SDKs may be imported (enforced by an import-boundary test in CI).

## 8.2 WorkerRun

```
WorkerRun
  run_id, task_attempt_id, sequence          -- 1:N within the attempt (Ch.3.9)
  execution_plan_id, worker_session_id NULL
  worker_id, worker_profile_id
  environment_id, workspace_id, context_package_id
  policy_version, lease_set_hash, checkpoint_id
  status, failure_class NULL
  usage_record_id NULL, artifact_manifest_id NULL
  started_at, ended_at
```

**Lifecycle** (verification is *not* a run state — it belongs to the task):

```
PLANNED → PREPARING → READY → RUNNING → COMPLETED | FAILED
RUNNING → CHECKPOINTING → RUNNING
RUNNING → PAUSING → PAUSED → RESUMING → RUNNING
RUNNING → CANCELLING → CANCELLED
FAILED  → RECOVERING → RUNNING | (attempt reroutes / escalates)
```

**Refused resumes are observable, never silent (amended 2026-08-22; owner queue-closure decision).** A resume request that is refused — stop authority active (Ch.14), lease no longer matching the active run (Ch.9.2), budget exhausted (Ch.7.1), plan hash drift — emits an observability event carrying the run identity, the refusal reason and the correlation id of the triggering command, on the same event surface as every other lifecycle transition. A refused resume leaves the run in its current state; it never falls back to an unobserved retry loop.

**Live usage metering (amended 2026-08-22; owner queue-closure decision).** Each run produces a run-scoped usage report from its actual token/tool consumption, and the reported usage **decrements the persisted attempt budget** on the run's execution plan (Ch.7.1). When the budget crosses zero, dispatch classifies `BUDGET_EXCEEDED` and the existing pause-for-human path (Ch.12.3, Ch.13.1) engages. Usage reporting is scoped to the run and recorded as run evidence; it is not a free-floating counter and cannot outlive its run.

## 8.3 WorkerEvent

```
WorkerEvent: event_id, run_id, task_id, sequence, event_type, timestamp,
             actor, correlation_id, causation_id, payload, schema_version,
             integrity_hash        UNIQUE(run_id, sequence)
```

Append-only. Consumers tolerate duplicates and bounded reordering via `(run_id, sequence)` plus idempotent handling. Worker-local transcripts and chain-of-thought stay inside the worker unless deliberately promoted to an Artifact, Finding or Evidence record — DDE consumes normalised lifecycle events, not worker chatter.

Malformed events are schema-validated and quarantined, never applied.

## 8.4 Worker Manager

Registers configurations and exposes **only certified profiles** to routing · enforces health before allocation · binds runs to plan/environment/workspace/context/leases · translates events into state transitions · fences late and duplicate messages by run identity and sequence · quarantines unhealthy or policy-violating configurations · coordinates graceful interruption, checkpointing and termination.

It is not an agent framework and does not reason about the task.

## 8.5 Certification — tiered

> **Closes F20.** A profile is `model × harness × toolset × environment`. With re-certification required on any change and models shipping continuously, a single monolithic suite guarantees certification is skipped in practice.

| Tier | Trigger | Content | Budget |
|---|---|---|---|
| **Smoke** | Automatic on any change to `profile_hash` (model version, harness version, toolset manifest, image digest) | 12 fixtures: tool-call correctness, structured output, file-write safety, workspace containment, cancellation, checkpoint/resume, cost reporting accuracy | **≤ 15 min, ≤ USD 5** — hard ceiling |
| **Standard** | Weekly, and before first production use of a profile | Smoke + task-class benchmarks for each workload class the profile claims | ≤ 2 h |
| **Full** | Before promoting a profile to `critical` autonomy, and quarterly | Standard + security suite + chaos + long-running recovery | Untimed |

A profile whose `profile_hash` changed and whose smoke tier has not passed is `STALE`: visible to operators, selectable in `development`, and **not selectable by production routing**. This is what keeps certification honest — the failure mode is a blocked route, not a silent bypass.

## 8.6 WorkerSession

Continuity aid for harnesses that maintain external sessions. Stores DDE identifiers, external session id, policy version, context revision, current checkpoint, heartbeat. **Never authoritative.** If the external session disappears, DDE creates a new run from the checkpoint rather than treating the external session as truth.

---
---

# Chapter 9 — Capability plane and admission

## 9.1 Capability descriptor

```
CapabilityDescriptor
  capability_id, version, category, summary
  interface_schema_ref, input_schema_ref, output_schema_ref
  implementations[], supported_worker_profiles[], supported_environments[]
  supported_workloads[], risk_class
  side_effect_class            -- 9.3, mandatory
  enforcement_tier             -- T1 or T2 (Ch.7.2)
  permission_model, cost_model, network_requirements
  dependencies[], provenance, certification_status, lifecycle_status
```

## 9.2 CapabilityLease

```
CapabilityLease
  lease_id, tenant_id, project_id, mission_id, task_id
  execution_plan_id, worker_run_id, environment_id
  capability_id, capability_version
  resource_scope, operation_scope, constraints
  issued_by_policy_version, issued_at, expires_at, revocable, status
```

**States:** `REQUESTED → EVALUATING → GRANTED → ACTIVE → CONSUMED`; `GRANTED|ACTIVE → EXPIRED | REVOKED`.

Invariants: a lease is scoped to mission/task/run/resource and expires by default · a worker profile never implies access to every registered capability · credential material is brokered only after a lease is valid · every call is attributable to a lease and a run · **lease denial is a normal control outcome, not an error** · expired and revoked leases fail closed at the enforcement boundary even if the worker holds cached schemas · a lease is rejected if any bound identity no longer matches the active run.

**Run stop authority (landed 2026-08-22; commits `1de8b72`, `4d7cf1a`, `0df07eb`).** Arming run stop for a worker run gates the capability plane at its admission edge: the broker refuses issue/renew of credentials for that run, and arming sweeps every still-held lease and live handle in one transaction so no capability call survives the arm. Refusals are journalled atomically with the sweep — an enforcement event that cannot be lost independently of the action it refused. The stop record itself is durable: it lives in the command ledger as a flipping row keyed per run, consulted first from memory then from the ledger, so a restart cannot resurrect a stopped run; disarming flips the same record symmetrically.

## 9.3 Side-effect taxonomy

> **Closes F19.** REV 1.3 referenced `side_effect_class` in the descriptor but never enumerated it, leaving implementers unable to decide what needs the effect journal.

| Class | Meaning | Retry rule | Journal |
|---|---|---|---|
| `PURE_READ` | No state change anywhere | Free retry | No |
| `WORKSPACE_LOCAL` | Mutates only the task workspace | Free retry after workspace reset | No |
| `EXTERNAL_IDEMPOTENT` | External mutation, provider honours an idempotency key | Retry with the same key | Yes |
| `EXTERNAL_NON_IDEMPOTENT` | External mutation without provider-side deduplication | **Never blind-retry**; reconcile first (Ch.12.4) | Yes, mandatory |
| `IRREVERSIBLE` | Cannot be undone: payment, message send, production deploy, data deletion | Never auto-retried; requires approval per invocation above the autonomy ceiling | Yes, plus approval record |

A capability without a declared class cannot be admitted. Recovery rules in Chapter 12 dispatch on this field.

## 9.4 Progressive disclosure

```
CATALOG → MATCH → DESCRIBE → POLICY CHECK → DISCLOSE → LEASE → EXECUTE
```

Tier 0: compact manifest for the task class only. Tier 1: descriptor and schema for a candidate. Tier 2: lease after policy and resource checks. Tier 3: concrete execution interface. Tier 4: bounded result and evidence.

**Disclosure is not authorization.** A schema may be disclosed before execution permission exists; the lease remains the authority boundary.

Small, stable capability sets may use eager disclosure — the implementation benchmarks discovery round-trips against schema/token savings per task class and the choice is a policy, not a constant.

## 9.5 Tool admission

```
discover → static scan → provenance → permission review → sandbox trial →
benchmark → conformance test → certify → register
```

MCP and plugin metadata are untrusted inputs until admitted — tool poisoning and malicious tool descriptions are active threats in the MCP ecosystem. MCP-backed capabilities undergo exactly the same pipeline as native ones. Re-admission is required on any descriptor or version change.

## 9.6 Dependency admission — for the software being built

> **Closes F12.** DDE governed its own tools exhaustively and said nothing about the libraries a worker adds to the product. A worker introducing a malicious, abandoned or licence-incompatible package is among the most likely real failure modes of autonomous code generation.

Every change to a dependency manifest or lockfile produced by a worker is a **governed event**, evaluated before integration:

| Check | Source | Blocking |
|---|---|---|
| Licence compatibility with the project's declared licence policy | SPDX from package metadata | Yes |
| Known vulnerabilities | [OSV](https://osv.dev/) / [Grype](https://github.com/anchore/grype) | Yes above severity threshold |
| Maintenance signal | last release, maintainer count, download trend | Warn; blocks for `critical` risk projects |
| Provenance | registry, signature/attestation where available | Yes for new top-level dependencies |
| Transitive delta | count and identity of newly introduced transitive packages | Reported; blocks above a delta threshold |
| Typosquat heuristic | name distance to popular packages | Yes |

New **top-level** dependencies additionally require the justification recorded in `AGENTS.md` (licence, maintenance, why the standard library is insufficient) and, above the autonomy ceiling, an approval. An SBOM ([Syft](https://github.com/anchore/syft)) is generated per integration and stored as evidence.

## 9.7 Mandatory diff gates

These run on **every** worker-produced diff before integration, as blocking verification steps rather than registry entries:

| Gate | Tool | Failure |
|---|---|---|
| Secret detection | [Gitleaks](https://github.com/gitleaks/gitleaks) | Block, quarantine the diff, raise a security finding |
| Static analysis | [Semgrep](https://semgrep.dev/docs/) rulesets for the language + project rules | Block above severity |
| Dependency/vulnerability | §9.6 | Block |
| Licence header / file provenance | project policy + donor taint (§13.8) | Block |
| Forbidden path modification | policy: CI config, security policy, migrations outside scope, `.git` internals | Block, require approval |

A worker cannot disable, weaken or reconfigure these gates; the configuration lives outside the workspace and is not writable from it.

## 9.8 Initial capability portfolio

Context · source intelligence (Git, ripgrep, Tree-sitter, LSP, ast-grep, Semgrep) · web/browser · UX and visual regression · backend/database · security scanning · mobile/Android tooling · infrastructure · observability · communications. Concrete technology choices are implementation details behind these contracts and are listed in [Appendix A](#appendix-a--reference-worker-portfolio).

---
---

# Chapter 10 — Integration and Merge Queue

> **NEW in REV 2.0 — closes F2.** REV 1.3 gave every task an isolated Git worktree and never said how isolated worktrees converge. There was no integration step in the workflow, no conflict owner, no serialisation rule, and no failure class for merge conflict. For a system whose purpose is parallel autonomous development against one repository, this was the gap most likely to produce silent data loss.

## 10.1 Principles

1. **Workers never write to a shared branch.** A worker writes only inside its own workspace.
2. **Integration is a DDE operation**, performed by the integration manager with its own credentials, its own verification and its own audit trail.
3. **"Verified" means verified after integration**, not before. Pre-integration verification is a fast filter; post-integration verification is the authoritative claim.
4. **History is append-only.** Undo is a new commit, never a rewrite of the mainline.
5. **Conflicts are prevented structurally first** (write scopes), **detected mechanically second** (merge), **resolved by a task third** (repair) — never by a worker improvising in a shared branch.

## 10.2 Branching model

```
main                       protected; only the integration manager writes
 └── mission/<mission-id>   mission integration branch; one per mission
      ├── task/<task-id>-a  worktree branch; one per task attempt
      ├── task/<task-id>-b
      └── task/<task-id>-c
```

- Task workspaces branch from the **mission integration branch head**, not from `main`. Missions therefore integrate internally and land on `main` once, coherently.
- The mission branch merges to `main` when the mission's AcceptanceOracle passes (§11.3) and mission-level verification is green.
- `main` is protected: no force push, no direct push, required status checks. The integration manager holds the only credential permitted to advance it, and that credential never enters an ExecutionEnvironment (Ch.7.2).

## 10.3 WriteScopeLease — structural conflict prevention

The Task Planner reserves write scopes before scheduling (Ch.4.7). This is the cheapest conflict control available and eliminates most merges that would otherwise fail.

```
WriteScopeLease
  lease_id, tenant_id, project_id, mission_id, task_id
  scope_patterns[]      -- e.g. ["engine/routing/**", "schemas/objects/route_decision.json"]
  exclusive             -- default true
  status                enum(RESERVED, ACTIVE, RELEASED, EXPIRED)
  acquired_at, expires_at
```

- Two concurrently scheduled tasks may not hold overlapping exclusive scopes. Overlap is computed on normalised path globs and is deterministic.
- Shared read-only scopes are unlimited.
- A task writing **outside** its scope fails the integration gate with `SCOPE_VIOLATION`. This is a planning error or a worker containment error, and is recorded as both.
- Scope leases expire with the task attempt and are released on `RETIRE`/`SUPERSEDE` only after the workspace is destroyed (Ch.4.6).
- Some paths are inherently shared — lockfiles, migration directories, dependency manifests, generated contracts. These are declared `serialised_paths` in project policy: any task touching them is scheduled **exclusively** for that path, which is why dependency and migration work is naturally sequential.

## 10.4 Merge queue

Integration is serialised per project by an advisory lock (Ch.3.5). One proposal is integrated at a time.

```
IntegrationProposal
  proposal_id, tenant_id, project_id, mission_id, task_id, task_attempt_id
  source_branch, base_revision, proposed_revision
  diff_summary, changed_paths[], scope_lease_id
  pre_integration_verification_ref
  status  enum(QUEUED, REBASING, VALIDATING, VERIFYING, MERGED,
               CONFLICT, REJECTED, SUPERSEDED)
  conflict_class NULL, attempts, created_at
```

**Queue algorithm:**

```
1  Acquire project integration lock.
2  If proposal.base_revision != mission_branch.head:
       rebase the task branch onto mission head.
       On textual conflict → CONFLICT(textual). Release. Emit repair task.
3  Run mandatory diff gates (Ch.9.7) and scope check (10.3).
       On failure → REJECTED with reason. Release.
4  Merge into an ephemeral integration candidate ref.
5  Run post-integration verification on the candidate (Ch.11):
       build, unit, contract, affected integration tests, domain invariants,
       and the mission's AcceptanceOracle subset that is now satisfiable.
       On failure → CONFLICT(semantic) or REJECTED(verification). Release.
6  Fast-forward the mission branch to the candidate.
7  Record evidence, emit MergedToMission event, trigger incremental reindex (Ch.5.4).
8  Release lock.
```

Steps 2–5 are the expensive part; they are what stops two individually-correct changes from combining into a broken tree.

## 10.5 Conflict classes and ownership

| Class | Detection | Owner | Resolution |
|---|---|---|---|
| `textual` | Rebase conflict | Integration manager | Emit a `repair` task scoped to the conflicting paths, with both sides and the base as context. Never resolved by the queue itself. |
| `semantic` | Merge succeeds, post-integration verification fails | Task Planner | Emit a repair task, or replan if two tasks encoded incompatible designs |
| `contract` | A change breaks a `produces_contract_for` interface a sibling depends on | Task Planner | The contract owner repairs; dependents are re-queued after |
| `invariant` | Domain invariant fails only after integration | Verification | Repair task at high priority; mission blocks if unresolved |
| `scope_violation` | Diff touches paths outside the write-scope lease | Governance | Reject, quarantine, record as containment finding, require approval to accept |

Repeated conflicts on the same task (default > 2) escalate to replanning rather than another repair — a task that cannot land is usually a decomposition error.

## 10.6 Verification placement

| Stage | Where | Scope | Authority |
|---|---|---|---|
| Pre-integration | Task workspace | Fast: unit, lint, types, task-scoped tests | Advisory filter |
| Post-integration | Integration candidate | Build, full unit, contract, affected integration, invariants, diff gates | **Authoritative** |
| Mission-level | Mission branch before `main` | Full suite, E2E, visual, security, mission AcceptanceOracle | **Authoritative for mission completion** |

A task is only `COMPLETED` after post-integration verification passes. Evidence records reference the integrated revision, not the workspace revision, so evidence always refers to code that actually exists on a branch.

## 10.7 Reverting

Undo is a first-class task, never a history rewrite.

- Reverting an integrated task creates a `revert` task with an explicit revert commit, its own verification and its own evidence.
- If the reverted work produced external effects (Ch.12.4), the revert task must include compensating actions or explicitly record that compensation is impossible and escalate.
- `main` and mission branches are never force-pushed. The Flight Lab asserts this by attempting it (§19.2).

## 10.8 Mainline advancement

When a mission completes, the mission branch merges to `main` through the same queue with mission-level verification. On merge: `main` advances, the incremental index reindexes, derived knowledge-graph edges recompute (§5.10), evidence links to the final revision, and the mission's write-scope leases release.

## 10.9 Acceptance tests

- Two tasks editing disjoint modules integrate concurrently in queue order with no conflict.
- Two tasks editing the same file are never scheduled concurrently (scope lease refuses).
- A task whose diff touches a path outside its scope is rejected and quarantined.
- Two individually-passing changes that break the build when combined are caught at step 5 and never reach the mission branch.
- A rebase conflict produces a repair task carrying both sides plus base as context, and the original attempt is preserved as evidence.
- An attempt to force-push `main` fails and raises a security finding.
- A revert of an integrated change produces a new commit and new evidence, and the original evidence remains valid and reachable.

---
---

# Chapter 11 — Verification, AcceptanceOracle and ProductEnvironment

> **Closes F8 and F13.** REV 1.3 required verification to reject a change whose code tests all pass, without saying what mechanically evaluates that judgment — and specified no environment in which the manufactured software could actually be exercised.

## 11.1 Verification chain

```
Build → Static analysis → Diff gates (Ch.9.7) → Unit → Contract →
Integration → E2E/browser → Visual → Security → Domain invariants →
AcceptanceOracle evaluation → Requirement traceability → EDR consistency
→ ACCEPT | REPAIR | ESCALATE
```

## 11.2 AcceptanceOracle — bound to executable evidence

```
AcceptanceOracle
  oracle_id, oracle_version            -- immutable
  scope           enum(task, mission)
  requirement_refs[], feature_refs[]
  observable_outcomes[]  -> ObservableOutcome
  domain_invariants[]    -> InvariantCheck
  negative_cases[]       -> ObservableOutcome (must NOT hold)
  minimum_confidence
  human_assertions[]     -- explicitly not machine-decidable
  approved_by, approved_at
```

```
ObservableOutcome
  outcome_id, statement                 -- human-readable
  evidence_binding   REQUIRED — one of:
      { kind: "test",         ref: "tests/e2e/test_credit_limit.py::test_blocks_over_limit" }
      { kind: "db_assertion", ref: "sql/assertions/credit_limit_enforced.sql" }
      { kind: "api_probe",    ref: "probes/post_order_over_limit.yaml" }
      { kind: "visual_diff",  ref: "visual/supplier-credit-screen.json" }
      { kind: "invariant",    ref: "invariants/accounting/posting_balance.py" }
      { kind: "judge",        ref: "judges/ui_copy_review@v3", independence: required }
      { kind: "human",        assertion_id: "..." }
  status, evidence_ref, evaluated_at
```

**The binding rule (this is the correction).** Every `observable_outcome` **must** bind to at least one evidence producer from the list above. A prose statement with no binding is not an acceptance criterion — `validate` rejects the oracle. `judge` and `human` bindings are permitted but constrained:

- A `judge` binding is a **certified capability** with a versioned prompt, a frozen rubric, and its own false-positive/false-negative measurements on a labelled fixture set. An uncalibrated judge cannot be bound.
- A `judge` may not be produced by the same worker profile family that generated the change under test (§11.4).
- `human` bindings block acceptance until answered; they are counted against the attention budget (§13.4) and their number is a planning quality metric.

**Oracle-first rule.** A task with `risk_class ≥ high` or `blast_radius ≥ cross_module` cannot enter autonomous implementation unless a validated, approved oracle exists — or a human-approved exception is recorded with a reason.

**Oracle independence.** A generator may *propose* an oracle. The authoritative oracle is approved through governance and may be evaluated independently. An oracle proposed and approved inside the same mission by the same principal that requested the work is flagged for review.

## 11.3 Mission-level oracle and wrong-product detection

Task oracles prove the tasks were done. The **mission** oracle proves the right product was built. It is authored during planning, before implementation, and is the mechanism by which verification can reject a change whose code-level tests all pass:

- Every mission with `risk ≥ medium` carries a mission oracle whose `observable_outcomes` are end-to-end and user-visible.
- Mission completion requires the mission oracle to pass on the mission branch **before** merge to `main` (Ch.10.8).
- If all task oracles pass and the mission oracle fails, the outcome is `WRONG_PRODUCT`: the mission enters replanning with the failing outcomes as context, and the discrepancy is recorded as a first-class learning signal about decomposition quality, not about worker quality.

> **Scope note — Accepted EDR-0007 (2026-08-22).** The mechanism above is accepted in partial scope: ProductEnvironment end-to-end outcomes, merge-to-main gating and automatic replan invocation are deferred and tracked by that decision; the oracle contract and wrong-product classification stand as specified.

**Confidence semantics (amended 2026-08-22; owner queue-closure decision).** Oracle evaluation treats confidence as a mid-band, not a coin-flip: outcomes above the policy threshold count toward acceptance, outcomes below it fail, and outcomes in the mid-band are held as inconclusive rather than rounded to a verdict. Evidence degrades with age on a declared per-binding-kind cadence: evidence past its freshness window can lower an outcome's standing (including demoting an acceptance), but degradation is degrade-only — stale or degraded evidence never promotes an outcome that did not independently pass.

## 11.4 Generator/verifier independence

| Rule | Enforcement |
|---|---|
| The worker profile that produced a change cannot execute the authoritative verification of that change | Routing forbids it (Ch.6.2 `forbid` clause) |
| Deterministic verification is preferred; a judge is used only where determinism is impossible | Oracle validation warns when judge bindings exceed a share of outcomes |
| A judge model family differing from the generator family is required for `risk_class ≥ high` | Plan validation |
| Test code authored in the same task as the implementation is marked `co_authored` | Evidence carries the flag; co-authored tests alone cannot satisfy an oracle for `risk_class ≥ high` |

That last rule matters: a worker writing both the code and its tests is not independent verification, no matter how green the suite is.

## 11.5 Domain invariants

Invariants are executable checks over a real datastore, versioned like code: accounting posting balance and reconciliation · inventory quantity/value conservation · purchasing order-receipt-invoice-payment reconciliation · sales lifecycle coherence · tax and pricing calculation order, precision and rounding.

Each invariant declares the fixtures it needs and the ProductEnvironment class it must run in. An invariant failure is never auto-repaired by a worker without a repair task and human visibility when it involves financial state.

## 11.6 ProductEnvironment

> The environment where **the software DDE builds** runs, so that it can be exercised. Distinct from ExecutionEnvironment, which is where **workers** run.

```
ProductEnvironment
  product_env_id, tenant_id, project_id, mission_id NULL
  class          enum(ephemeral_preview, integration, staging, production)
  source_revision, build_artifact_ref
  runtime_topology_ref          -- compose/manifest describing the product's services
  datastore_ref, seed_dataset_ref, migration_state
  base_url NULL, credentials_profile_id
  status enum(PROVISIONING, MIGRATING, SEEDING, READY, IN_USE, TEARDOWN, FAILED)
  ttl_expires_at
```

**Lifecycle:** provision from the build artifact of a specific revision → apply migrations forward from a known baseline → seed the declared dataset → expose to verification → snapshot on failure for diagnosis → teardown at TTL.

**Rules:**
- Every ephemeral preview has a TTL and is destroyed on expiry; storage growth from abandoned previews is a monitored metric.
- Seed datasets are versioned artifacts with content hashes, so an invariant failure is reproducible.
- Migration verification is mandatory and bidirectional: forward-apply to an empty database, and forward-apply to a snapshot of the previous release's schema. A migration that only works on an empty database is not verified.
- Production ProductEnvironments are never provisioned by a worker and never reachable from an ExecutionEnvironment.
- Failure snapshots are evidence artifacts, subject to the same retention and WORM rules.

## 11.7 Evidence

```
Evidence: evidence_id, tenant_id, project_id, mission_id, task_id,
          verification_run_id, integrated_revision, oracle_id, outcome_id,
          evidence_type, artifact_refs[], content_hash, signature,
          produced_by(principal|capability|worker_profile), independence_flags,
          recorded_at, status
```

Evidence is append-only, content-hashed, signed, and references the **integrated** revision. Superseding evidence never deletes it.

## 11.8 Verifier quality is itself measured

False-positive and false-negative rates per verification type · flake rate per test (a flaky test is a defect, tracked and repaired, never retried into green) · coverage of oracle outcomes by deterministic vs judge vs human bindings · judge agreement with human review on a sampled subset · mean time from failure to attributed cause.

A verification suite whose flake rate exceeds threshold **blocks routing learning** (§6.8), because a noisy verifier corrupts every downstream signal in the system. Above that threshold the check enters quarantine with a two-tier cadence (§6.5, amended 2026-08-22): advisory-only in the fast tier, signal-repairing out-of-band on the slow tier, restored only by measured evidence.

**Self-grading guardrails (landed 2026-08-22; commit `e730a9e`).** Verification assesses the producing run's own behaviour before its outcome is trusted: diff-independence (did the run author tests that merely certify itself?), declared-path scope, and oracle-declared-path adherence. A guardrail violation classifies `SCOPE_VIOLATION` on the attempt (Ch.12.3) — always a containment finding, never a retryable verification failure — so a green suite produced by a misbehaving run cannot launder itself into acceptance.

---
---

# Chapter 12 — Recovery, effects and durability

## 12.1 Checkpoint

A checkpoint is a **reconstructible continuation contract**, not a progress percentage.

```
Checkpoint
  checkpoint_id, task_id, task_attempt_id, worker_run_id
  context_package_id, execution_plan_id
  completed_work[], verified_work[], pending_work[], known_failures[]
  next_action, do_not_repeat[]
  artifact_refs[], lease_refs[]
  workspace_revision, integration_state
  event_sequence, integrity_hash, created_at
```

A checkpoint never replaces the immutable event history and never becomes the sole source of truth. `do_not_repeat` is load-bearing: it is what prevents a resumed run from re-executing a completed migration or a sent message.

## 12.2 TaskAttempt durability

```
TaskAttempt
  attempt_id, task_id, sequence UNIQUE(task_id, sequence)
  execution_plan_id, input_context_hash, workspace_revision
  result_artifact_refs[], verification_refs[], integration_proposal_id NULL
  status, failure_class NULL, retry_of NULL, checkpoint_id
  started_at, ended_at
```

An attempt becomes durable when its result, artifact references and state are committed. Recovery resumes from the latest valid checkpoint **plus** the durable results of completed attempts — completed sibling work is never re-run merely because a later task failed.

## 12.3 Failure taxonomy and recovery matrix

| Failure class | Default action | Escalation condition |
|---|---|---|
| `CONTEXT_FAILURE` | Recompile with expanded retrieval; run critic | Low confidence persists or contradiction remains |
| `PLANNING_FAILURE` | Decompose or amend the graph | Repeated decomposition failure → replan |
| `ROUTING_FAILURE` | Re-evaluate route | No eligible worker, or repeated route failure |
| `AUTHORIZATION_FAILURE` | Request corrected policy or approval; **no silent retry** | Any policy bypass attempt → security review |
| `ENVIRONMENT_FAILURE` | Replace environment, resume from checkpoint | Workspace or state integrity uncertain |
| `WORKER_FAILURE` | Recover session/run, else reroute | Repeated failure or untrusted worker state |
| `TOOL_FAILURE` | Alternate capability implementation | No certified implementation available |
| `MERGE_CONFLICT` | Emit scoped repair task (Ch.10.5) | > 2 conflicts on one task → replan |
| `SCOPE_VIOLATION` | Reject, quarantine diff | Always — containment finding |
| `VERIFICATION_FAILURE` | Repair, then re-verify; preserve failing evidence | Repeated failure or high-risk mismatch |
| `WRONG_PRODUCT` | Replan from mission oracle failures | Always — human visibility |
| `SPECIFICATION_FAILURE` | Create decision/clarification task; **never guess** | Human authority required |
| `RESOURCE_EXHAUSTION` | Checkpoint, request budget or reschedule | Budget cannot be increased |
| `BUDGET_EXCEEDED` | Dispatch-time refusal against the plan's durable attempt budget; checkpoint and pause for a human budget decision (Ch.7.1) | Budget increased via approval (Ch.13.1) |
| `SIDE_EFFECT_UNKNOWN` | Reconcile before any retry (12.4) | Reconciliation impossible → human |
| `DRIFT_FAILURE` | Stop the mutation path, trigger drift review | Always |
| `INTENTIONALLY_STOPPED` | Acknowledge the operator stop (`requires_human`, never auto-retried); a new WorkerRun only after the durable stop record is DISARMED (amended 2026-08-23, EDR-0010/EDR-0012) | Operator acknowledgement required — always human |

> **Intentional stops are classified at their real site and gate every new-run path (amended 2026-08-23; EDR-0010 accepted, EDR-0012 wiring).** A run killed mid-flight by an armed stop is durably recorded `INTENTIONALLY_STOPPED` by the run lifecycle's failure writer — never absorbed by the borrowed `WORKER_CAPABILITY_DENIED`/`AUTHORIZATION_FAILURE` classes — with the durable stop record as the classification authority. The guard is total across WorkerRun-minting paths: dispatch-time retry checks AND the resume path consult it before any prior-run replace, new-run insert or lease grant, so no fresh WorkerRun can be created past an unacknowledged stop (Ch.12.4's law applied to resumes).

## 12.4 External effect journal

```
ExternalEffect
  effect_id, command_id, worker_run_id, capability_lease_id
  target_system, target_resource, operation, side_effect_class
  idempotency_key, request_hash
  status enum(PREPARED, SENT, CONFIRMED, FAILED, UNKNOWN, RECONCILING, RECONCILED)
  external_reference, response_hash, reconciliation_method
  created_at, confirmed_at
```

```
PREPARED → SENT → CONFIRMED
                ↘ FAILED
                ↘ UNKNOWN → RECONCILING → RECONCILED
```

**Recovery rule.** An `UNKNOWN` effect is never blind-retried. The capability adapter reconciles using the idempotency key, the external reference, a read-after-write query, or a provider-specific method. **Only a verified absence permits a new mutation attempt.** For `IRREVERSIBLE` effects (§9.3), reconciliation failure escalates to a human rather than resolving automatically.

**The law covers every new-mutation path, not only retries (amended 2026-08-23; EDR-0012).** "Only verified absence permits a new mutation" binds resume/restart paths exactly as it binds dispatch-time retry: a path that mints a fresh WorkerRun on an existing attempt consults the same durable stop record before any prior-run replace, new-run insert or lease grant. An operator's unacknowledged stop cannot be routed around by re-entering through resume instead of retry.

T2 (contained) workers produce effect records from the egress proxy log (Ch.7.2), so a harness with its own tool plane still yields an auditable effect trail.

## 12.5 Replay and idempotency

Replay starts from the latest valid checkpoint and re-executes only work whose durable result is absent or invalidated. No replay may repeat an externally visible mutation unless its idempotency contract is proven.

Every externally visible mutation carries `command_id` and `idempotency_key`. The command ledger records first-seen, in-progress, completed and failed. A repeated command returns the stored result or current status — it never launches a second mutation. Retention of that ledger is governed by §3.7.

## 12.6 MissionWorkflow

Long-running work is expressed through a backend-neutral interface:

```
MissionWorkflow: start · pause · resume(checkpoint) · wait(condition) ·
                 request_approval · checkpoint · retry(policy) · reroute ·
                 cancel · complete · fail
```

The v1 implementation is PostgreSQL state plus Redis scheduling. A durable workflow engine may be introduced only when measurements show DDE-owned durability has become the limiting operational burden, and only behind this unchanged interface. Introducing one is an EDR with evidence, not a preference.

Durable execution requirements: every asynchronous command has a durable identity and idempotency key · every attempt has a durable record independent of mission completion · completed attempts are not replayed because a later task failed · external side effects sit behind idempotent adapters or the journal · checkpoint state suffices to reconstruct the next legal action · recovery dispatches on failure class, never on a generic retry.

---
---

# Chapter 13 — Governance, approvals and autonomy economics

> **Closes F9.** REV 1.3 required approved oracles, architecture approvals and production approvals but specified no approval SLA, no behaviour on expiry, no pre-authorization pattern, and no rule allowing unblocked work to continue. An overnight mission would stall at the first architecture question.

## 13.1 Approval

```
Approval
  approval_id, tenant_id, project_id, mission_id, task_id NULL
  approval_type enum(architecture_change, production_change, scope_widening,
                     capability_grant, oracle_approval, irreversible_effect,
                     dependency_addition, donor_reuse, budget_increase)
  scope_hash                     -- binds to the exact plan/action
  requested_by, required_role, evidence_refs[], suggested_decision NULL
  status enum(REQUESTED, UNDER_REVIEW, APPROVED, REJECTED, EXPIRED, WITHDRAWN)
  decided_by, decided_at, expires_at, rationale
```

An approval is bound to an exact mission/task/plan/action scope by `scope_hash`. It **cannot be reused** for a materially different plan — a re-planned action requires a new approval even if it looks similar.

**Batch approval (amended 2026-08-22; owner queue-closure decision).** The approvals surface accepts a batch command that decides multiple pending approvals in one server-side, all-or-nothing transaction: either every approval in the batch records its decision or none does — no partial batches. Batch decisions obey the same `scope_hash` binding and expiry rules as single ones, and the batch itself is one auditable command with its own idempotency key.

`budget_increase` is the decision type for the pause-for-human budget path (Ch.7.1, Ch.12.3): when a run pauses on `BUDGET_EXCEEDED`, the attention model surfaces a `budget_increase` request; granting it raises the plan's durable attempt ceiling through the governed approval surface — never through a dispatcher parameter (amended 2026-08-22; owner queue-closure decision).

## 13.2 Pre-authorization — how overnight autonomy actually works

Blanket autonomy is unsafe; per-action approval is unusable. The resolution is **bounded standing authority**.

```
StandingApproval
  standing_id, tenant_id, project_id, mission_id NULL
  approval_types[]                  -- which classes it pre-authorises
  blast_radius_ceiling              -- e.g. module
  risk_ceiling                      -- e.g. medium
  cost_ceiling, task_count_ceiling
  path_scope[]                      -- may be narrower than mission scope
  forbidden_operations[]            -- always excluded, e.g. IRREVERSIBLE effects
  valid_from, valid_until           -- e.g. one overnight window
  revocable_immediately  = true
  granted_by, rationale
```

Rules: a standing approval can never pre-authorise an `IRREVERSIBLE` side effect, a production change, a scope widening beyond the mission's declared scope, or a `critical` risk action. Every action taken under it is recorded with the `standing_id` and surfaced in the morning review. Revocation is immediate and applies to in-flight runs at the enforcement boundary.

This is the mechanism that makes "bounded autonomy" a real property rather than an aspiration.

## 13.3 Non-blocking decisions

When a task requires a decision:

1. The task enters `BLOCKED_ON_DECISION` and a `decision` task is added to the graph with a `blocks_on_decision` edge (Ch.4.5).
2. **Only transitive dependents block.** Independent branches continue (Ch.4.9).
3. The mission enters `PARTIAL`, not `FAILED`, if any branch can still progress.
4. On approval expiry the mission **parks**: state is checkpointed, workspaces preserved or released per policy, leases expired, and an attention item raised. Parking is not failure and does not discard durable results.
5. A decision, once made, becomes an EDR — so the same question is never asked twice.

## 13.4 Autonomy economics — human attention is a measured resource

| Metric | Definition | Initial target |
|---|---|---|
| Human minutes per verified mission | Sum of review, approval and clarification time | Tracked from Stage 1; target set after 20 missions |
| Approvals per mission | Count by type | ≤ 3 for `risk = medium` missions |
| Human assertions per oracle | `human` bindings in acceptance oracles | ≤ 2; more indicates poor observability design |
| Blocked-branch ratio | Share of wall-clock time with all branches blocked on humans | < 20% for overnight missions |
| Attention debt | Open attention items older than their SLA | Zero at start of each working day |

If human minutes per verified mission are not falling as the system matures, the system is not becoming more autonomous regardless of how much it automates. This is the honest measure of the whole project and it is a Stage-3 gate.

## 13.5 Autonomy levels

| Level | Meaning | Requires |
|---|---|---|
| 0 | Propose only; no execution | — |
| 1 | Read-only analysis and research | Research environment |
| 2 | Workspace-local changes; no integration | Contained environment |
| 3 | Integrate to mission branch after verification | Diff gates + post-integration verification |
| 4 | Merge to `main` on mission oracle pass | Mission oracle + standing approval |
| 5 | Act on external systems with `EXTERNAL_IDEMPOTENT` effects | Effect journal + leases |
| 6 | `IRREVERSIBLE` effects | Per-invocation approval; never pre-authorised |

`autonomy_ceiling` is set per mission, may be lowered per task, and can never be raised by a worker, a plan, or a route.

## 13.6 Focus Guardian

Before significant actions, a deterministic check: does this advance the mission, is it in scope, are the capabilities permitted, does it respect project truth, does it require approval? Unrelated discoveries become **Findings** or backlog candidates — never silent scope expansion. In-scope blocking discoveries become graph amendments (Ch.4.5). The distinction between those two paths is what keeps missions finite.

## 13.7 Configuration flags and validation

```
routing.mode = deterministic | shadow_learning | canary | promoted_historical
routing.exploration.epsilon                     (default 0.0 in production)
routing.degraded_default                        (legal only in development)
routing.cost_tier = low | medium | high | xhigh | max   (default: declared order)
routing.learning.enabled
routing.learning.min_eligible_attempts_per_class / _global
routing.learning.calibration_threshold / uplift_threshold
routing.learning.canary_percentage / rollback_window
context.retrievers.semantic.enabled             (default false until §5.13 uplift)
context.adaptive_policy.enabled
capability.enforcement.mode = strict | audit_only
planning.mode.model_assisted.enabled
integration.merge_queue.concurrency             (must be 1 per project)
verification.judge_bindings.max_share
autonomy.default_ceiling
android.offline_queue.enabled
donor.reuse_policy_version
```

**Configuration validation is a startup gate.** The process refuses to start if any of these hold in a non-development environment class: `capability.enforcement.mode = audit_only`; `routing.degraded_default = true`; `autonomy.default_ceiling ≥ 4` without a configured mission oracle policy; `routing.mode = promoted_historical` without a certified policy artifact; `integration.merge_queue.concurrency > 1`; `routing.exploration.epsilon > 0` with `autonomy.default_ceiling ≥ 5`. A dangerous combination must be impossible to reach by editing a value.

## 13.8 External evidence and donor governance

Every donor repository, APK, website or external artifact receives a machine-readable classification **before** implementation use: `OPEN_REUSE`, `CONDITIONAL_REUSE`, `SOURCE_REFERENCE_ONLY`, `RESTRICTED`, `UNKNOWN`, `REJECTED`. Unknown or conflicting licence evidence defaults to `SOURCE_REFERENCE_ONLY` or `REJECTED` per policy and can never silently become implementation code.

Provenance taint propagates: donor-derived requirements, patterns, assets, algorithms and UI evidence carry tags that persist into Feature DNA, tasks, diffs and evidence, so DDE can answer *which donor evidence influenced this artifact*. Donor analysis runs in isolated environments; executable donor code is untrusted until admitted; prompt injection inside donor content cannot elevate authority (§14.5). A signed reuse decision is required before donor-derived implementation enters an autonomous production task.

**Model-provider data handling** is part of this governance, not separate from it: a project policy declares which worker profiles may receive donor-classified or confidentiality-classified material, and routing treats that as a **hard gate** at level 0. Sending restricted source to an ineligible provider is a policy violation, not a preference.

**UI template and component sourcing is donor governance too** *(amended 2026-08-24, from the anti-generic-output research; playbook §10.5)*: template/component sources classify on the same scale — shadcn-ecosystem registries and blocks are `OPEN_REUSE` (programmatically ingestable); commercial template products such as Tailwind Plus or Cruip are `CONDITIONAL_REUSE` (their output may be referenced as art direction but never enters DDE's generator); marketplace bundles are `REJECTED` for builder use; showcase galleries (`godly.site`, `lapa.ninja`, mobbin-class) are `SOURCE_REFERENCE_ONLY`. Animation/motion-component libraries enter through the same classification at the same gate. Ingestion mechanics land with the Donor Lab mission (S5/DDE-046) behind its EDR.

## 13.9 Tenancy authority

Scope chain: `Principal → Organization/Tenant → Project → Mission → Task → runtime bindings`. A principal must be authorized for the tenant and project **before** any domain or capability operation is evaluated, and tenant identity is derived from the authenticated principal, never from a client-supplied target id.

Isolation is enforced at four layers: database RLS (§3.2) · object-storage key prefixes with mediated access that rejects cross-scope references even when an artifact id is otherwise valid · project-scoped Git connections and credentials, so a worker's general repository capability never reaches another project's repository · telemetry carrying tenant/project/mission correlation, with dashboards applying the same authorization scope as API reads.

---
---

# Chapter 14 — Security, identity and credentials

## 14.1 Security chain

```
Principal → Policy → CapabilityLease → ExecutionPlan → ExecutionEnvironment
          → CredentialBroker → Enforcement boundary (T1 gateway | T2 egress proxy)
          → Tool/Resource → Audit + Evidence
```

## 14.2 Principals

| Principal | Authentication | Baseline scopes |
|---|---|---|
| Human | OIDC/OAuth2 + device session | `mission.read`, assigned `approval.*` |
| Service (internal module boundary) | mTLS or signed service credential | Service-specific |
| Worker runtime | mTLS or signed worker token, bound to environment identity | `worker.execute`, `worker.events`, `worker.artifacts` |
| Device (Android/Termux) | Device-bound credential | `device.read`, assigned `device.command` |
| Capability implementation / plugin | Signed registration + service credential | `capability.execute` for its declared surface only |

Authorization is RBAC for broad roles plus contextual (ABAC-style) constraints: tenant, project, environment class, resource scope, autonomy level, capability risk, time window, policy version. **A role never grants unrestricted access to a resource.**

## 14.3 Credential Broker

The broker is the **only** component permitted to exchange a valid CapabilityLease for secret material or a scoped execution handle.

| Operation | Required behaviour |
|---|---|
| `issue(lease)` | Only after policy and lease validation; returns a short-lived credential or handle bound to tenant, project, mission, task, run, capability, resource scope, policy version and expiry |
| `renew(lease, credential)` | Revalidates the **active** lease; issues a replacement; never silently widens authority or extends beyond the lease |
| `revoke(credential)` | Invalidates or quarantines at the provider where semantics permit; always invalidates locally |
| `inspect(lease)` | Returns non-secret metadata only: provider, scope, expiry, status, policy version |
| `emergency_revoke(scope)` | Revokes all active material under a tenant/project/mission/run scope, and terminates dependent runs |

Preference order: workload identity → OIDC-exchanged short-lived token → provider-issued temporary credential → signed execution handle → static secret behind the broker. A static secret **never** enters a worker process, a ContextPackage, a prompt, an event, a log, an artifact or an error payload. Audit records store metadata and hashes, never secret material. Providers sit behind a `CredentialProvider` contract so no core logic couples to one secret manager.

## 14.4 Worker admission

A worker connects, proves identity, presents its configuration and version, is mapped to a certified WorkerProfile, and is admitted only if certification (§8.5), environment compatibility and policy checks pass. Uncertified configurations are visible as candidates but unselectable by production routing.

## 14.5 Security invariants

1. Agent identity alone never grants a capability.
2. A WorkerRun never inherits capabilities from a previous run; each plan re-issues explicitly.
3. Environment network access is deny-by-default outside approved profiles; egress is allow-listed per environment class and capability policy.
4. Worker environments are unreachable from the public internet unless a specific capability requires controlled ingress; management endpoints stay private.
5. MCP and plugin metadata remain untrusted until admitted and certified.
6. **Prompt injection in external evidence cannot elevate authority.** Authority derives from the principal and the lease, never from content. A model instruction found inside a donor file, a web page, a test fixture or a code comment has authority rank 10 and is treated as a hypothesis.
7. Capability revocation takes effect at the enforcement boundary even when the worker holds stale state.
8. Credential material is never logged, never rendered into screenshots, and is redacted from artifacts by a scrubber before storage.
9. Every security-relevant decision — grant, denial, revocation, escalation, containment violation — produces an `audit_event` in the hash-chained ledger (§3.7).
10. Run-stop arming is enforced at credential admission: after stop is armed for a run, the broker issues no new credential material to it (landed 2026-08-22; commit `1de8b72`).

---
---

# Chapter 15 — Gateway, API and MCP

## 15.1 Gateway role

A thin transport boundary — authenticate and identify client/device/service roles · authorize command scope before it reaches Core · protocol negotiation and versioning · WebSocket/SSE subscriptions for mission and run events · enforce idempotency keys on side-effecting commands · separate command acceptance from eventual completion. **It never owns Project Truth or mission state.**

```
ClientSession: session_id, principal_id, client_type, device_id,
               protocol_version, scopes[], connected_at, last_seen_at,
               subscriptions[], status
```

A gateway session identifies a connected client, not a manufacturing mission. Many sessions may observe one mission and vice versa, subject to authorization.

**Reconnection.** A reconnecting client presents its session id and last acknowledged event sequence. DDE returns a state snapshot plus retained events sufficient to close a bounded gap. If the gap cannot be safely replayed (§3.7), the client receives a fresh snapshot rather than inferring state from stale local data.

## 15.2 Envelopes

```json
// command
{ "command_id": "...", "idempotency_key": "...", "principal_id": "...",
  "client_session_id": "...", "target_type": "task", "target_id": "...",
  "command_type": "task.pause", "parameters": {},
  "requested_at": "...", "protocol_version": "1" }
```

```json
// event
{ "event_id": "...", "event_type": "WorkerRunStarted", "aggregate_type": "worker_run",
  "aggregate_id": "...", "tenant_id": "...", "project_id": "...", "mission_id": "...",
  "task_id": "...", "sequence": 104, "occurred_at": "...",
  "correlation_id": "...", "causation_id": "...", "payload": {}, "schema_version": "1" }
```

**Accepted/final semantics.** Commands that launch asynchronous work return acceptance with `command_id`, target state and run/task reference. Completion arrives later as an authoritative state transition event. Clients must never interpret acceptance as successful execution.

## 15.3 API conventions

HTTPS JSON, UTF-8, versioned `/v1` · Bearer/OIDC for humans and clients, mTLS or signed credentials for services and workers · `correlation_id` on every request · `command_id` + `idempotency_key` on every mutation · `202 Accepted` means accepted, not completed · stable machine-readable `error_code` with retryability metadata · additive schema changes preferred, breaking changes require a new version · cursor pagination for event/artifact/activity collections · ETag for mutable resources under optimistic concurrency.

## 15.4 Core endpoints

| Endpoint | Purpose | Mode | Scope |
|---|---|---|---|
| `POST /v1/missions` | Create mission | sync accept | `mission.create` |
| `GET /v1/missions/{id}` | Read mission | sync | `mission.read` |
| `POST /v1/missions/{id}/{pause,resume,cancel}` | Mission control | async | `mission.control` |
| `POST /v1/missions/{id}/plan` | Produce or amend TaskGraph | async | `plan.write` |
| `GET /v1/task-graphs/{id}` | Read graph + versions | sync | `plan.read` |
| `POST /v1/task-graphs/{id}/amendments` | Propose amendment | sync | `plan.amend` |
| `POST /v1/tasks` · `GET /v1/tasks/{id}` | Task create/read | sync | `task.*` |
| `POST /v1/context/compile` · `/{id}/expand` | Context compile / JIT expansion | async | `context.*` |
| `POST /v1/routes/evaluate` | Evaluate route | sync | `route.evaluate` |
| `POST /v1/execution-plans` | Create and validate plan | sync | `execution.plan` |
| `POST /v1/worker-runs` + `/{id}/{pause,resume,cancel}` | Run lifecycle | async | `worker.*` |
| `GET /v1/workers` · `/{id}/health` | Worker registry and health | sync | `worker.read` |
| `POST /v1/capabilities/discover` · `POST /v1/capability-leases` | Discovery and lease | sync | `capability.*` |
| `POST /v1/integration/proposals` · `GET /v1/integration/queue` | Merge queue | async | `integration.*` |
| `POST /v1/verifications` · `GET /v1/evidence/{id}` | Verification and evidence | async / sync | `verification.*`, `evidence.read` |
| `POST /v1/approvals` · `/{id}/decision` · `POST /v1/standing-approvals` | Governance | async / sync | `approval.*` |
| `GET /v1/mission-control/{id}` | Operational projection | sync | `mission.read` |
| `GET /v1/missions/{id}/events` | Event query/stream | sync/stream | `event.read` |

## 15.5 Error contract

```json
{ "error_code": "CAPABILITY_LEASE_EXPIRED",
  "message": "Capability lease is no longer active",
  "retryable": false,
  "details": { "lease_id": "...", "worker_run_id": "..." },
  "correlation_id": "..." }
```

| Family | Examples | Default retry |
|---|---|---|
| AUTHENTICATION | `INVALID_CREDENTIALS`, `SESSION_EXPIRED` | No |
| AUTHORIZATION | `FORBIDDEN`, `LEASE_EXPIRED`, `POLICY_DENIED`, `TENANT_SCOPE_VIOLATION` | No |
| CONFLICT | `VERSION_CONFLICT`, `RESOURCE_LOCKED`, `WRITE_SCOPE_CONFLICT` | Conditional |
| PLANNING | `GRAPH_INVALID`, `DECOMPOSITION_REQUIRED`, `CONTEXT_BUDGET_EXCEEDED` | Re-plan |
| CONTEXT | `CONTEXT_INCOMPLETE`, `CONTEXT_CONTRADICTION`, `INDEX_STALE` | After recompile |
| ROUTING | `NO_ELIGIBLE_WORKER`, `ROUTE_REJECTED`, `PROFILE_STALE` | Re-evaluate |
| EXECUTION | `WORKER_UNAVAILABLE`, `ENVIRONMENT_FAILED`, `PROVISIONING_TIMEOUT` | Recover/reroute |
| INTEGRATION | `MERGE_CONFLICT`, `SCOPE_VIOLATION`, `GATE_FAILED` | Repair task |
| SIDE_EFFECT | `EFFECT_UNKNOWN`, `EFFECT_CONFLICT` | Reconcile |
| VERIFICATION | `VERIFICATION_FAILED`, `ORACLE_UNSATISFIED`, `WRONG_PRODUCT` | Repair / replan |
| RESOURCE | `BUDGET_EXCEEDED`, `QUOTA_EXCEEDED`, `EVENT_WINDOW_EXPIRED` | Pause/reschedule |

## 15.6 MCP position

MCP is a **capability interoperability boundary**. DDE keeps mission state, event history and workflow state outside MCP.

| Tool class | Examples | Mutation |
|---|---|---|
| Read | `dde_get_mission`, `dde_get_task`, `dde_get_evidence`, `dde_get_graph` | none |
| Context | `dde_compile_context`, `dde_request_context` | controlled |
| Planning | `dde_propose_amendment`, `dde_evaluate_route`, `dde_create_execution_plan` | controlled |
| Execution | `dde_start_task`, `dde_request_capability` | high |
| Verification | `dde_start_verification`, `dde_get_verification` | controlled |
| Governance | `dde_request_approval`, `dde_record_decision` | high |
| Control | `dde_pause_task`, `dde_resume_task`, `dde_cancel_task` | high |

Every DDE MCP tool declares: stable name, semantic version, JSON Schema 2020-12 input/output, required principal scopes, mutation classification, idempotency requirement, target-resource rules, audit event type, error codes, and sync/async execution.

**MCP security rule.** Tool discovery or schema disclosure never constitutes DDE authorization; the CapabilityLease remains the execution authority. MCP-backed implementations enter the same admission and certification pipeline as native ones. Where MCP tasks are used, they map to DDE Task/TaskAttempt; the MCP task is transport-facing and the DDE task is authoritative. No MCP task bypasses Mission Kernel, policy, leases or verification.

---
---

# Chapter 16 — Observability, SLOs and the overhead budget

## 16.1 Unified trace

```
Mission → TaskGraph → Task → ContextPackage → RouteDecision → ExecutionPlan →
WorkerRun → CapabilityLease → Tool/Effect → Artifact → VerificationRun →
IntegrationProposal → Evidence → Outcome → ExperienceRecord
```

One trace id spans the chain. OpenTelemetry is the transport; the DDE event store is the source of truth. LLM-specific tracing (token, cost, prompt/response linkage) is exported to a dedicated tool but is never authoritative.

## 16.2 Minimum metrics

**Planning** — amendment rate, decomposition depth error, parallel efficiency, replan frequency, traceability completeness.
**Context** — coverage completeness, omission rate, contradiction rate, index lag, retrieval latency, package size, JIT request/denial rate, context-attributed failure rate.
**Routing** — eligibility rejection reasons, first-route success, escalation rate, calibration error, predicted vs actual cost, exploration share.
**Execution** — worker availability, run success, retry count, provisioning latency, environment failure rate, tool failure rate.
**Integration** — queue depth and wait, merge conflict rate by class, scope violations, post-integration verification failure rate, time-to-mainline.
**Verification** — pass/fail, duration, oracle outcome coverage by binding type, judge agreement, flake rate, false positive/negative.
**Recovery** — checkpoint resume success, duplicate-prevention rate, reroute success, unknown-effect reconciliation rate, mean recovery time.
**Governance** — approvals per mission, human minutes per verified mission, blocked-branch ratio, attention debt, standing-approval usage.
**Operations** — mission cost, cost per verified success, queue age, artifact storage growth, API latency.

## 16.3 Event publication

Authoritative state and immutable events commit transactionally in PostgreSQL together with an outbox row. A dispatcher publishes to Redis streams with at-least-once delivery; consumers are idempotent on `event_id` and aggregate sequence. Per-aggregate ordering is guaranteed; **global ordering is not**, and consumers must not assume it. Redis loss never destroys authoritative state; projections rebuild from PostgreSQL.

## 16.4 Control-plane overhead budget

> **Closes F14.** Before a worker writes a line of code, DDE may have run context compilation, a context critic, routing and a route critic. REV 1.3 measured only API read latency, which is the cheapest thing in the system.

```
overhead_tokens  = context_assembly + context_critic + routing + route_critic
                   + planning (model_assisted) + judge evaluations
overhead_seconds = the same, plus environment provisioning and queue wait
```

| Budget | Initial target | Enforcement |
|---|---|---|
| Overhead tokens as share of total mission tokens | ≤ 25% | Alert above; investigate at 35%; hard cap configurable per tenant |
| Overhead seconds before first worker action | ≤ 90 s p95 for `s`-sized tasks | Alert above |
| Environment provisioning p95 | ≤ 45 s | Warm pool sizing responds automatically |
| Critic invocation share | Context critic ≤ 30% of tasks; route critic ≤ 20% | Trigger thresholds retuned if exceeded |
| Cost per verified success | Tracked per workload class | Primary economic metric; regression blocks policy promotion |

Exceeding the overhead budget is treated as a defect in the control plane, not as the cost of doing business. It is the metric that tells you whether the scaffolding is still earning its place (§18.6).

## 16.5 Operational SLOs

| Metric | Target | Gate |
|---|---|---|
| Mission state reconstruction | 100% of certified recovery fixtures | Release |
| Duplicate side-effect prevention | 100% of idempotency suite | Mutation capability certification |
| Lease fail-closed | 100% of security fixtures | Capability certification |
| Worker replacement without mission loss | 100% of certified scenarios | Autonomy |
| Checkpoint recovery | ≥ 99% of deterministic fixtures | Long-running autonomy |
| Post-integration verification catches combined-change breakage | 100% of merge fixtures | Integration |
| API p95 read latency | < 500 ms | Operational |
| Command acceptance p95 | < 1 s excluding heavy planning | Operational |
| Gateway reconnect recovery | < 10 s for a bounded gap | Client readiness |

---
---

# Chapter 17 — Operations, deployment and disaster recovery

## 17.1 Runtime units

| Unit | Initial deployment | Health | Scaling |
|---|---|---|---|
| DDE Core (incl. Gateway, Worker Manager, Planner, DCE, Router, Integration) | One container/process group | `/healthz`, `/readyz` with DB + Redis checks | Vertical first; horizontal only after §3.5 invariants are proven |
| Outbox dispatcher | Same image, separate process | Lag metric | `SKIP LOCKED` allows N instances safely |
| Worker hosts | Separate environment per certified profile | Heartbeat + adapter health | By workload and cost |
| Egress proxy | Sidecar per environment or shared per environment class | Allow/deny counters | With environment count |
| PostgreSQL | Managed (Neon/Supabase) | Connection, replication, backup health | Managed |
| Redis | Managed | Memory, queue lag, evictions | Disposable |
| Object storage | R2/S3-compatible | Availability, integrity | Storage growth |

## 17.2 Network boundaries

```
Internet ──TLS──> DDE Gateway ──private──> DDE Core
                                             ├── PostgreSQL
                                             ├── Redis
                                             └── Object storage
                                    outbound control channel
                                             ↓
                                    Worker environments
                                             ↓ scoped egress via proxy
                                    Tools / external APIs / Git
```

Worker environments are not reachable from the internet. Management endpoints are private. Production egress is allow-listed per environment class and capability policy.

## 17.3 Health model

Liveness: the process responds. Readiness: DDE can **safely accept work** — database reachable, migrations at head, outbox lag below threshold, configuration validation passed (§13.7). Worker health: adapter heartbeat plus runtime checks. Environment health: host, toolchain and workspace checks. Capability health: implementation availability plus certification status.

Readiness returning 503 on migration mismatch is deliberate: a Core running against a schema it was not built for is worse than a Core that is down.

## 17.4 CI/CD

```
commit → lint → typecheck → contract drift check → unit → contract tests →
design token drift + static design lints → migration validation (empty DB +
previous-release snapshot) → integration → security scans (SAST, secrets,
SBOM, vulnerabilities) → build image → Flight Lab smoke → staging deploy →
post-deploy verification → approval → production → post-deploy verification →
auto-rollback on failure
```

Any change touching a contract runs contract tests against the previous compatible version. Any change to a worker profile's manifest triggers smoke certification (§8.5). The golden mission fixture runs on every merge to `main`.

**Design gates (landed 2026-08-22; commit `5f31142`).** CI additionally enforces the frontend playbook's deterministic layer: a generated-token drift check (the `tokens.ts` artifact is regenerated and must diff clean) and the static design-lint suite over studio surfaces run on every PR; dde-studio client tests are PR-blocking rather than compile-only. These are the Phase-0/1 guardrails of the frontend/UX playbook, wired at their production enforcement point.

## 17.5 Backup, retention and disaster recovery

> **Closes F22.** REV 1.3 had backup and rollback as a checklist line with no targets.

| Concern | Requirement |
|---|---|
| **RPO** | ≤ 5 minutes for control-plane state (PostgreSQL PITR / WAL archiving enabled from Stage 1) |
| **RTO** | ≤ 2 hours for full control-plane restoration |
| Restore drills | Quarterly, executed against a real restore into an isolated environment; a drill that is not executed counts as a failed control |
| Evidence and artifacts | WORM: object-lock with a retention period ≥ the project's audit retention requirement. Evidence buckets have versioning enabled and deletion disabled for the retention window |
| Evidence integrity | Content hash plus signature at write; `audit_events` hash-chained; periodic chain verification job |
| Event archives | Detached partitions exported to object storage, catalogued, and restorable into a scratch database for investigation |
| Secrets | Rotation schedule per credential class; emergency revoke path tested in the same drill cadence |
| Redis | No backup required by design — anything lost is rebuildable from PostgreSQL. If that stops being true, it is a defect |

## 17.6 Deployment rule

Deploy DDE Core as one application. Run workers in separate environments. PostgreSQL is authoritative, Redis is disposable, artifacts live in object storage. Extract a subsystem only after evidence shows a concrete need for independent scaling, isolation, deployment cadence or reliability — and only after §3.5's transaction invariant has an explicit replacement.

**No-PC operational path.** Codespaces or a cloud VM for bootstrap development, a persistent Linux host for the control plane, Android/Termux as an edge client. Canonical state is never coupled to a developer workstation.

---
---

# Chapter 18 — Staged execution plan

> **Closes F3 as directed: scope is not reduced.** Every capability declared in REV 1.3's v1 remains in v1. What changes is the order and the gating, so that a complete — if thin — instance of the whole system is running from Stage 1 and never stops running.

## 18.1 The two rules that make full scope deliverable

**Rule 1 — Vertical slice before depth.** Every subsystem lands first as a *contract-complete but minimal* implementation that participates in the end-to-end chain, and only afterwards gains depth. A subsystem that cannot be exercised by the golden mission is not started.

**Rule 2 — The golden mission never goes red.** From Stage 1 onward, every merge to `main` runs the golden mission end to end. Each stage adds scenarios to it and may never remove one. This converts "29 missions of scaffolding before anything works" into "a working system that gets more capable every week", without dropping a single feature.

Consequence: features ship **dark** where necessary. A capability may exist behind a configuration flag with its contracts, tests and telemetry complete before it is enabled by default. That is how full scope and staged execution coexist.

## 18.2 Stage gates

| Stage | Theme | Exit gate — all must hold |
|---|---|---|
| **S0** | Foundation | Schema generation pipeline green; migrations apply to empty DB and reverse; CI enforces contract drift; RLS policies present; `/readyz` accurate |
| **S1** | **Walking skeleton** | Golden mission runs end to end unattended-with-supervision: mission → graph → context → route → plan → contained run → diff → verification → integration → evidence. `dde mission trace` reconstructs every step. |
| **S2** | Safety envelope | Every S2 security fixture passes: lease revocation mid-run fails closed; no ambient credential reachable from an environment; unknown effect reconciles before retry; diff gates block a planted secret and a planted vulnerable dependency; cross-tenant access fails before resource access |
| **S3** | Durability and parallelism | Three tasks integrate concurrently without conflict; a killed Core resumes from checkpoint; a killed worker is replaced without mission loss; a blocked approval does not block an independent branch; human-minutes-per-mission is being measured |
| **S4** | Intelligence, measured | Context eval corpus ≥ 60 cases with a certified baseline; semantic retrieval enabled only if it shows uplift; routing telemetry complete with propensities; mission oracle rejects a planted wrong-product implementation |
| **S5** | Capability breadth | Donor pipeline classifies licence before reuse; MCP server passes contract suite; visual and security capabilities certified; product environments provision, seed, verify and tear down |
| **S6** | Clients and tenancy | Multi-tenant isolation suite green; CLI, web and Android produce identical authoritative outcomes on the same golden mission; reconnect recovers without duplicate commands |
| **S7** | Adaptive and hardened | Learning activation gates enforced and demonstrated (including refusal to activate when unmet); chaos suite green; DR drill executed; all Chapter 16.5 SLOs met |

## 18.3 Stage contents — full v1 scope, ordered

**S0 — Foundation**
`DDE-001` repo, devcontainer, CI · `DDE-002` schema source of truth + generation + migration 0001 · `DDE-003` Project Truth and requirements engine · `DDE-004` EDR engine and governance records · `DDE-005` event store, transactional outbox, audit ledger.

**S1 — Walking skeleton** *(the critical restructure: end-to-end at step ~11, not step 20)*
`DDE-006` Mission Kernel and mission state machine · `DDE-007` **TaskGraph + Task Planner (template mode)** ⟨Ch.4⟩ · `DDE-008` ContextPackage + DCE with explicit/authority/lexical/structural retrievers ⟨Ch.5⟩ · `DDE-009` deterministic router + RouteDecision with full candidate recording ⟨Ch.6⟩ · `DDE-010` Execution Planner + ExecutionEnvironment (container) + Workspace ⟨Ch.7⟩ · `DDE-011` WorkerAdapter + Worker Manager + first certified profile ⟨Ch.8⟩ · `DDE-012` verification runner + AcceptanceOracle v1 with test bindings ⟨Ch.11⟩ · `DDE-013` **Integration/merge queue + WriteScopeLease** ⟨Ch.10⟩ · `DDE-014` evidence pipeline + `dde mission trace` · `DDE-015` CLI.

**S2 — Safety envelope**
`DDE-016` capability registry, descriptors, side-effect taxonomy ⟨Ch.9⟩ · `DDE-017` CapabilityLease + T1 gateway enforcement · `DDE-018` T2 containment: egress proxy, zero ambient credentials, containment fixtures ⟨Ch.7.2⟩ · `DDE-019` Credential Broker + provider contract ⟨Ch.14.3⟩ · `DDE-020` ExternalEffect journal + idempotency ledger + reconciliation ⟨Ch.12.4⟩ · `DDE-021` mandatory diff gates + dependency admission + SBOM ⟨Ch.9.6–9.7⟩ · `DDE-022` tenancy columns activation + RLS enforcement suite ⟨Ch.13.9⟩.

**S3 — Durability and parallelism**
`DDE-023` checkpoints + TaskAttempt durability + replay ⟨Ch.12⟩ · `DDE-024` failure taxonomy + recovery matrix + replan ⟨Ch.4.6, 12.3⟩ · `DDE-025` second and third worker adapters + tiered certification ⟨Ch.8.5⟩ · `DDE-026` approvals, standing approvals, non-blocking decisions, attention budget ⟨Ch.13⟩ · `DDE-027` Gateway, REST/WS API, session and reconnect semantics ⟨Ch.15⟩ · `DDE-028` Mission Control projection and attention model · `DDE-029` warm pools and provisioning economics ⟨Ch.7.4⟩.

**S4 — Intelligence, measured**
`DDE-030` semantic retriever + index lifecycle + versioned embeddings ⟨Ch.5.4⟩ · `DDE-031` Context Critic (triggered) + conflict adjudication ⟨Ch.5.6, 5.9⟩ · `DDE-032` context eval corpus + labeling protocol + promotion gates ⟨Ch.5.13⟩ · `DDE-033` knowledge graph with derived/asserted split ⟨Ch.5.10⟩ · `DDE-034` failure attribution engine ⟨Ch.5.11⟩ · `DDE-035` routing telemetry, propensity logging, shadow mode ⟨Ch.6.5–6.7⟩ · `DDE-036` Routing Simulation Model as fixture generator ⟨Ch.6.4⟩ · `DDE-037` mission-level AcceptanceOracle + wrong-product detection ⟨Ch.11.3⟩ · `DDE-038` ProductEnvironment lifecycle + seed datasets + migration verification ⟨Ch.11.6⟩ · `DDE-039` domain invariant engine ⟨Ch.11.5⟩ · `DDE-040` model-assisted planning mode + mission templates ⟨Ch.4.3⟩ · `DDE-041` control-plane overhead budget instrumentation ⟨Ch.16.4⟩.

**S5 — Capability breadth**
`DDE-042` DDE MCP server ⟨Ch.15.6⟩ · `DDE-043` browser/Playwright capability · `DDE-044` visual engineering and multimodal evidence pipeline · `DDE-045` security capability (SAST/DAST/agentic security worker) · `DDE-046` Donor Lab: ingestion, extraction, Feature DNA ⟨Ch.13.8⟩ · `DDE-047` donor licence/reuse classifier + taint propagation · `DDE-048` Android/APK analysis capabilities · `DDE-049` database and backend capabilities · `DDE-050` documentation and context-provider capabilities.

**S6 — Clients and tenancy**
`DDE-051` multi-tenant authority, org/tenant hierarchy, isolation suite · `DDE-052` web dashboard · `DDE-053` Android thin client with API parity and reconnect ⟨Ch.15.1⟩ · `DDE-054` Termux edge node · `DDE-055` messaging adapters (transport only, no authority) · `DDE-056` client parity fixture across CLI/web/Android on the golden mission.

**S7 — Adaptive and hardened**
`DDE-057` ExperienceRecord + eligibility filtering + governed promotion ⟨Ch.6.8⟩ · `DDE-058` routing learner, shadow evaluation, calibration, canary, rollback ⟨Ch.6.9⟩ · `DDE-059` adaptive context policy with promotion gates · `DDE-060` Flight Lab full suite ⟨Ch.19⟩ · `DDE-061` chaos and worker-replacement suites · `DDE-062` DR drills, backup/restore verification, WORM enforcement ⟨Ch.17.5⟩ · `DDE-063` load and capacity testing · `DDE-064` production readiness review and removal-test pass ⟨§18.6⟩.

## 18.4 Traceability to REV 1.3's sequence

Nothing was dropped. The REV 1.3 missions map as follows: DDE-001→S0/001 · 002→S0/002 · 003→S0/003 · 004→S0/004 · 005→S1/006 · 006→S0/005 · 007→S4/033 · 008→S1/008 · 009→S4/031 · 010→S3/023 · 011→S2/016 · 012→S2/017 · 013→S1/009 · 014→S4/032+035 · 015–017→S1/011 and S3/025 · 018→S1/012 + **S1/013 (new)** · 019→S5/046 · 020→**S1 exit gate rather than a mission** · 021→S3/027 · 022→S3/028 · 023→S7/057 · 024→S5/046-047 · 025→S2/018-019 · 026→S7/060-061 · 027→S6/053-054 · 028→S3/026 · 029→S7/062. The `R` missions from REV 1.3 §79 map to S2/021, S2/018, S4/036, S4/035, S2/019, S4/037, S5/047, S6/056 and S7/058 respectively.

## 18.5 What "MVP" means here

There is no reduced MVP. **v1 = S0 through S7 complete.** The Stage 1 walking skeleton is not a product milestone and is not shippable to anyone; it is an engineering milestone that proves the spine works before depth is added to it. Declaring it "the MVP" would be exactly the mistake this document is structured to avoid.

## 18.6 Removal tests

At every stage exit, ask of every component: can this subsystem, prompt scaffold, evaluator, adapter or dependency now be removed without reducing verified outcomes or increasing cost per verified success? Removals are recorded as EDRs with the measurement that justified them. Candidates to re-examine at each gate: the context critic (as models improve), the route critic, model-assisted planning (as templates cover more cases), the simulation model, and any retriever whose marginal uplift on the eval corpus has fallen below its cost.

## 18.7 Explicitly deferred infrastructure

Not provisioned in v1, by decision, each reversible behind an existing interface: a durable workflow engine (MissionWorkflow already abstracts it) · a dedicated vector database (pgvector suffices at this scale) · Kubernetes (one container per unit) · a service mesh · microservice extraction · a secrets-manager appliance beyond the cloud provider's own · any agent framework, graph runtime or agent-to-agent message bus.

---
---

# Chapter 19 — Contract tests and Flight Lab

The blueprint is executable only if it is tested. Every contract gets four tests: **schema**, **state transition**, **negative**, **recovery**.

## 19.1 Contract suites

| Suite | Required fixtures |
|---|---|
| Schema/contract | Valid, missing field, unknown field, stale version, generated-code drift |
| API | Unauthorized command, duplicate idempotency key, stale ETag, oversized payload, pagination boundary |
| MCP | Schema validation, missing scope, malformed task, discovery, revoked lease |
| Planning | Cyclic graph, untraceable node, oversized node, overlapping write scopes, amendment out of scope, replan with in-flight run |
| Context | Missing required coverage, contradiction, stale index, budget exceeded, JIT denial |
| Routing | No eligible worker, stale profile, hard-gate bypass attempt, exploration containment, propensity recorded |
| Worker protocol | Heartbeat loss, duplicate event, out-of-order event, malformed event quarantine, pause/resume, termination |
| Environment | Incompatible toolchain, workspace escape, symlink escape, resource exhaustion, replacement mid-run |
| Integration | Concurrent disjoint merge, overlapping scope refusal, rebase conflict, semantic conflict, scope violation, force-push attempt, revert |
| Verification | Oracle without binding, judge independence violation, co-authored test on high-risk task, flaky test detection, wrong-product |
| Recovery | Core crash, worker crash, environment crash, network loss, context loss, event window expired |
| Side effects | Timeout after write, replay with same key, reconciliation, unknown result, irreversible effect without approval |
| Security | Credential exfiltration attempt, prompt injection in donor content, poisoned capability metadata, lease revocation mid-run, cross-tenant access, planted secret in diff, planted vulnerable dependency |
| Governance | Expired approval, reused approval scope, standing approval exceeded, autonomy ceiling escalation attempt |
| Learning | Simulation record entering training set, ineligible attribution entering training set, promotion without gates, rollback |

## 19.2 Golden mission

```
MISSION-ERP-000421 — Implement supplier credit limits
Requirements : REQ-AP-019
Graph        : specification → schema → service → API → UI → tests → verification
Workers      : economy implementation → recovery → premium escalation
Capabilities : repository, database, testing, browser, documentation
Verification : unit + integration + visual + security + domain invariant + mission oracle
Approvals    : architecture change + production change
```

It must produce a complete trace from mission creation through planning, context compilation, routing, execution planning, contained execution, evidence, independent verification, integration, repair or escalation where needed, and final acceptance. It is the canonical end-to-end regression fixture and runs on every merge to `main` from Stage 1.

Stage-added scenarios: S2 adds a lease revocation mid-mission; S3 adds a Core restart and a blocked approval on one branch; S4 adds a planted wrong-product implementation; S5 adds a donor-derived component with ambiguous licence; S6 adds Android and web parity; S7 adds a worker outage and a policy rollback.

---
---

# Chapter 20 — Change control and traceability to REV 1.3

**Authority.** REV 2.0 supersedes REV 1.3 as the construction baseline. It does not override Project Truth, the Product Constitution, approved Requirements or accepted EDRs. Where a REV 1.3 section described a subsystem at a higher level, REV 2.0 supplies the more specific contract.

| REV 1.3 area | REV 2.0 disposition |
|---|---|
| §1–9 architecture, authority, principles | Preserved; authority restated as precedence ranks (Ch.2.2) |
| §10, §39, §76 Context Intelligence | Preserved and completed with retrieval pipeline, index lifecycle, eviction order, corpus protocol (Ch.5) |
| §11, §40, §75 Routing | Preserved; pipeline unified, deterministic v1 router added, simulation re-scoped, learning gated (Ch.6) |
| §12, §27 Evaluation | Preserved; planner and integration suites added (Ch.4.10, Ch.19) |
| §13, §45 Recovery | Preserved; extended with merge, scope and wrong-product failure classes (Ch.12) |
| §14, §41 Workers | Two adapter contracts collapsed into one; run lifecycle corrected; certification tiered (Ch.8) |
| §15, §42 Capabilities | Preserved; side-effect taxonomy defined; dependency admission added (Ch.9) |
| §18, §77 Donor intelligence | Preserved; extended with provider data-handling as a hard routing gate (Ch.13.8) |
| §19 Visual engineering | Preserved; vendor-specific modality claim moved to worker profile attributes (App. A) |
| §20, §74 Verification | Preserved; oracle outcomes must bind to executable evidence; independence rules added (Ch.11) |
| §21, §43, §72, §73 Security | Preserved; enforcement split into T1/T2 tiers (Ch.7.2, Ch.14) |
| §22 Workflow | Extended with the integration step (Ch.10) |
| §23, §44 Interfaces | Preserved (Ch.15) |
| §25, §51 Deployment | Preserved; scale invariant made explicit (Ch.3.5, Ch.17) |
| §37, §66 Data model | **Regenerated** from a single schema source; tenancy applied; IDs decided; partitioning added (Ch.3) |
| §38 State machines | Preserved; `INTEGRATING`, `BLOCKED_ON_DECISION`, `SUPERSEDED` added (Ch.4.8) |
| §53, §79 Sequence | Restructured into S0–S7 with full traceability (Ch.18.3–18.4); no capability removed |
| §63 Effect journal | Preserved; bound to the side-effect taxonomy (Ch.12.4) |
| §71 Multi-tenancy | Preserved and propagated into the schema (Ch.3.2) |
| §78 Android | Preserved (Ch.18 S6) |
| §83 Preserved decisions | **Reaffirmed:** v1 capability scope is not reduced. Execution is staged (Ch.18.5) |
| **New** | TaskGraph and Task Planner (Ch.4) · Integration and Merge Queue (Ch.10) · ProductEnvironment (Ch.11.6) · standing approvals and attention budget (Ch.13) · overhead budget (Ch.16.4) · DR targets and WORM (Ch.17.5) · execution guide (Ch.1) |

---
---

# Appendix A — Reference worker portfolio

> **Closes F21.** All vendor-specific content is isolated here so the core specification stays model-agnostic. Nothing in Chapters 2–20 depends on any name below. Replacing an entry is a configuration change, not an architecture change.

| Profile role | Reference implementation | Profile attributes that matter |
|---|---|---|
| Persistent orchestration, memory, skills, delegation, browser/computer use, scheduling, messaging | Hermes-class harness | long-lived session, own tool plane → **T2 containment**, progressive tool disclosure |
| Long-context analysis, corpus and batch work, bulk implementation, economical execution | DeepSeek-harness-class | large context capacity, `modality: text` unless a profile declares otherwise, low cost per token |
| High-value reasoning, architecture, difficult debugging, complex integration, premium review | Claude-Code-class | own tool plane → **T2 containment**, high capability, high cost, escalation target |
| Cursor models / agent (first certified implementation worker) | `adapters/cursor` over `cursor-sdk` + `cursor-sdk-bridge` | **T2**, local runtime only, `auto_create_pr` forbidden, API key never enters the ExecutionEnvironment |
| Deterministic verification | Test runners, linters, scanners, invariant checkers | not a model; `T1`; independence guaranteed structurally |
| Vision and visual evidence | Multimodal model behind a vision capability | `modality: image`; returns structured evidence, not prose |
| Security | Agentic security platform | isolated target environment, controlled network |

**Modality is a profile attribute, never an architectural assumption.** A worker that cannot accept images is described by `modality: [text]` in its profile; routing gate 4 handles it. No chapter of this document may encode a specific model's current limitations.

Capability implementation candidates by class — context and documentation providers · Git, ripgrep, Tree-sitter, LSP, ast-grep, Semgrep, CodeQL · Playwright and browser backends · design-system extraction, Storybook, visual regression, accessibility tooling · PostgreSQL/Supabase, OpenAPI, property testing · Gitleaks, Trivy, Syft, Grype, agentic security · JADX, Apktool, ADB, Maestro, Frida, MobSF · Docker, OpenTofu, Ansible, GitHub Actions · OpenTelemetry, Langfuse, Sentry, Prometheus/Grafana · messaging transports.

---

# Appendix B — Corrections applied

| REV 1.3 defect | Correction in REV 2.0 |
|---|---|
| §23A.1 cited `[R3]` for the OpenClaw gateway while `[R3]` was defined as OpenHands Workspace | Both reference schemes merged; gateway patterns described without a mis-citation (Ch.15) |
| §61 contained the literal artifact string `citeturn533982search5` in body text | Removed |
| §44.5, §61 and Appendix H asserted a "July 2026 / 2026-07-28" MCP specification while the cited reference was the 2025-06-18 spec | Version-specific claims removed; MCP is described by role, with a link to the living specification (Ch.15.6) |
| Two reference schemes `[1]–[14]` and `[R1]–[R9]` covering overlapping sources | Single link index (Ch.1.8) |
| Inner title block read "Revision 1.2" inside a REV 1.3 document; front matter had no revision id | Revision, date and supersession stated in the front matter |
| `execution_environments` DDL omitted the security `class` required by §21A.1 | `class` and `type` both mandatory (Ch.7.3) |
| §66 matrix had no tenants/organizations entity though §71 mandated tenancy | Schema regenerated; tenancy columns and RLS mandatory (Ch.3.2) |
| Primary key type left as "UUID/ULID" throughout | Decided: UUIDv7 (Ch.3.4) |
| `worker_runs.task_attempt_id` and `task_attempts.worker_run_id` mutual FKs | One direction only; cardinality decided as 1:N (Ch.3.9) |
| Two WorkerAdapter signatures (§14A.1, §41.1) | One normative contract (Ch.8.1) |
| Two WorkerRun lifecycles, one including verification states | Verification belongs to the task, not the run (Ch.8.2) |
| Two attempt counters (`attempt_number`, `sequence`) | One counter per level (Ch.3.9) |
| Three routing pipelines (§11.1, §40.3, §75.3) | One normative pipeline (Ch.6.1) |
| "Lower levels may inform higher levels" inverted against its own numbering | Restated as precedence ranks (Ch.2.2) |
| `side_effect_class` referenced but never enumerated | Taxonomy defined and bound to recovery rules (Ch.9.3) |
| §59.2 named ~15 "Services" while §36.3 placed them in one deployable | Renamed to modules; transaction invariant stated (Ch.3.5, Ch.3.8) |
| `command_idempotency.expires_at` with no stated relationship to retry windows | Retention rule stated (Ch.3.7) |
| `REPLANNING` state with no defined semantics | Full replan disposition model (Ch.4.6) |

---

# Appendix C — Review findings → resolution map

| # | Finding | Severity | Resolved in |
|---|---|---|---|
| F1 | No task-decomposition or DAG contract | Blocking | **Ch.4** (new) |
| F2 | No integration or merge semantics for parallel work | Blocking | **Ch.10** (new) |
| F3 | v1 scope not deliverable; §83 forbade reducing it | Blocking | **Ch.18** — scope retained in full, execution staged, golden mission from S1 |
| F4 | Capability enforcement impossible for third-party harnesses | Blocking | **Ch.7.2** T1/T2 tiers; **Ch.7.4** provisioning economics |
| F5 | Simulation bootstrap is costly guesswork with an unclosable validation loop | High | **Ch.6.2** deterministic v1 router; **Ch.6.4** RSM re-scoped to fixtures |
| F6 | Off-policy evaluation unsound without exploration or propensities | High | **Ch.6.7** |
| F7 | Credit assignment across subsystems undefined | High | **Ch.6.8** eligibility filter; **Ch.5.11** attribution |
| F8 | AcceptanceOracle outcomes not mechanically checkable | High | **Ch.11.2** evidence binding rule; **Ch.11.4** independence |
| F9 | Human approval throughput unmodelled | High | **Ch.13.2–13.4** standing approvals, non-blocking decisions, attention budget |
| F10 | REV 1.3 addendum not propagated into schema sections | High | **Ch.3.1–3.2** generated schema, mandatory tenancy |
| F11 | Duplicate contracts violate the document's own integrity gate | High | **Ch.3.9, 6.1, 8.1, 8.2**; Appendix B |
| F12 | No dependency admission for the manufactured software | High | **Ch.9.6–9.7** |
| F13 | No environment lifecycle for the product under construction | High | **Ch.11.6** ProductEnvironment |
| F14 | Control-plane latency and token overhead unanalysed | High | **Ch.16.4** overhead budget |
| F15 | Context contracts without algorithm or index lifecycle | Medium | **Ch.5.2–5.7, 5.13** |
| F16 | Knowledge graph without freshness or derivation model | Medium | **Ch.5.10** |
| F17 | No retention, partitioning or archival policy | Medium | **Ch.3.7** |
| F18 | Scheduler concurrency invariant unstated | Medium | **Ch.3.5** |
| F19 | `side_effect_class` referenced but undefined | Medium | **Ch.9.3** |
| F20 | Certification combinatorics unbounded | Medium | **Ch.8.5** tiered certification with hard budgets |
| F21 | Vendor names baked into normative text | Medium | **Appendix A** |
| F22 | Backup/DR without targets; evidence without immutability | Medium | **Ch.17.5** RPO/RTO/WORM |
| F23 | Authority numbering described in inverted language | Medium | **Ch.2.2** |

---

**End of REV 2.0.** The construction gate is satisfied when the implementation repository contains contract tests corresponding to every chapter, the Flight Lab executes the Chapter 19 suites, and each stage gate in Chapter 18.2 has been demonstrated rather than asserted.



