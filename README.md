# DDE — Development & Engineering Engine

DDE is a model-agnostic software manufacturing control plane. It owns product truth, mission state, context policy, routing policy, capability governance, verification and evidence. External agent harnesses and design providers are replaceable workers/capabilities. Editors, phones, browsers and chat channels are clients. This repository is the DDE Core control plane.

## Rev 3 canonical source of truth

New development starts from the repository/Core, not historic chat context.

### Primary forward-development authorities

1. [`docs/truth/BLUEPRINT_REV3.md`](docs/truth/BLUEPRINT_REV3.md) — canonical human-readable product/technical architecture and invariants.
2. [`docs/truth/DEV_PLAN_REV3.md`](docs/truth/DEV_PLAN_REV3.md) — canonical implementation sequence, vertical slices and gates.

Accepted Project Truth/EDR records outrank both.

### Supporting controlled projections/helpers

- [`docs/truth/IMPLEMENTATION_STATE.md`](docs/truth/IMPLEMENTATION_STATE.md) — evidence-based current state and next work packet; not target architecture.
- [`docs/truth/ARCHITECTURE_DECISIONS.md`](docs/truth/ARCHITECTURE_DECISIONS.md) — readable decision index; accepted EDR rows and Blueprint authority rules control conflicts.
- [`docs/truth/RESUME_PROMPT.md`](docs/truth/RESUME_PROMPT.md) — canonical bootstrap helper for a fresh engineering session.

[`docs/blueprint/REV_2_0.md`](docs/blueprint/REV_2_0.md) is historical/reference depth. Standalone Rev 3 amendments/addenda are also historical evidence after their decisions have been absorbed by the consolidated Blueprint/Plan.

**Current default next implementation gate:** `REV-3A Operational Safety Gate`, beginning with ProjectIdentity/bootstrap preflight, unless repository evidence shows REV-3A already passed.

Read [`AGENTS.md`](AGENTS.md) before changing code.

## Core consolidated Rev 3 laws

- Models occupy roles; model names are not permanent architectural jobs.
- Fable is the preferred strategic-orchestrator occupant when certified/available; Opus may temporarily occupy the role under fallback policy and returns to the ordinary worker pool when Fable is restored.
- Hermes remembers/retrieves/discovers patterns; DDE remains truth/routing/promotion authority.
- Context, provider quota and executable-tool versions are governed runtime resources.
- Every controlled mutation belongs to explicit packet/workspace scope; rejected work may not contaminate later commits.
- Existing verification evidence is inherited until a relevant dependency/invariant invalidates it.
- Claude `/design` is integrated behind DDE's DesignGateway. Provider artboards are DESIGN; only code-backed candidate runtimes are LIVE.
- Execution Graph/Node Inspector/Workflow Composer expose or compile into the real DDE runtime; they never create a second orchestration truth.

## The five environments

These must stay separate:

1. **Authoring environment** — Cursor/VS Code/DDE Code/terminal/chat. Edits or requests work; never authoritative.
2. **DDE Core** — owns Project Truth, missions, routing/policy, capabilities, evidence and governance.
3. **ExecutionEnvironment** — disposable sandboxed worker runtime with explicit filesystem/network/credential capabilities.
4. **ProductEnvironment** — throwaway/staged deployment of the software DDE is building, used for real verification/rendering.
5. **Worker providers/harnesses/design providers** — replaceable external capabilities; never authoritative.

## Codespace quickstart

This project is Linux/devcontainer-first. Local Python/Docker is not required when using Codespaces.

1. Create/open a Codespace on the intended branch.
2. Connect Cursor/VS Code to that Codespace.
3. In the terminal:

```bash
uv sync
just db-upgrade
just contract-test
just dev
```

4. In another terminal:

```bash
curl localhost:8000/healthz
curl localhost:8000/readyz
```

`just check` runs lint, formatting/type/unit/contract checks according to the repository recipe. GitHub Actions additionally applies migrations to an empty PostgreSQL database and checks generated-contract drift.

Copy `.env.example` when running outside compose and configure `DDE_DATABASE_URL` / `DDE_REDIS_URL` as documented.

> **Rev-3A warning:** until the native `ProjectIdentity`/`BootstrapReceipt` path is implemented, manually verify that you are in the intended DDE repository/root before loading project-specific agent configuration.

## Windows complete product

Codespaces remain the default cloud development path. The Windows distribution is under [`packaging/windows`](packaging/windows/README.md) and bundles DDE Code, DDE Core, PostgreSQL/Redis, migrations and setup tooling.

Example build:

```powershell
powershell.exe -File packaging/windows/scripts/Build-Installer.ps1 -Version 0.1.0
```

The current distribution/readiness state is evidence-tracked in `docs/truth/IMPLEMENTATION_STATE.md`; README presence does not imply every release-hardening path is complete.

## DDE Code / Frontend Studio

DDE Code is the operator surface for the software factory, not a collection of decorative dashboards.

Frontend Studio target workflow:

```text
Brief → Explore → References → Build → Motion → Verify → Ship
```

The consolidated target adds:

```text
Design with Claude
→ DesignArtifact candidate
→ Try live in isolated workspace
→ real application LIVE candidate
→ compare/refine
→ promote exact design/code pair
→ independent verification
```

and a DDE-native runtime control surface:

```text
Mission Overview
Execution Graph
Node Inspector
Design Review
Run Comparison
Workflow Library
Workflow Composer
```

These target features must remain honest in UI: no fabricated rows, no decorative graph disconnected from runtime, and no artboard labelled LIVE.

## Worker/harness model

Workers are selected as exact configurations, not merely by model name:

```text
model + model version
+ provider
+ harness + version
+ profile
+ tools/skills
+ context strategy
+ execution environment
+ policy hashes
```

Routing hard-gates illegal candidates before optimizing expected verified success, effective cost, latency, rework, quota/context pressure and operational risk.

Initial model affinities are priors only and decay as verified evidence accumulates.

## Cursor worker

Cursor-related worker logic lives behind `adapters/cursor` and the accepted adapter/capability boundary. Credentials remain on the adapter/broker side and are not passed into model-generated worker environments.

See [`docs/adapters/cursor.md`](docs/adapters/cursor.md) and current `IMPLEMENTATION_STATE.md` before assuming a specific Cursor runtime capability is live; installed/certified capability outranks README prose.

## Controlled commits

Read `AGENTS.md` before using commit helper scripts.

The consolidated Rev 3 architecture forbids broad staging for normal controlled feature packets because unrelated or rejected edits can be swept into accepted commits. `scripts/commit_if_green.*` predates the native ChangePacket/StagingManifest gate and must not be treated as permission to stage unrelated working-tree state. REV-3A will harden this path.
