# DDE — Development & Engineering Engine

DDE is a model-agnostic software manufacturing control plane. It owns product truth, mission state, context policy, routing policy, capability governance, verification and evidence. External agent harnesses are workers. Editors, phones, browsers and chat channels are clients. This repository is the DDE Core control plane.

## Rev 3 source of truth

New development starts from the repository truth set, not from historic chat context:

1. [`docs/truth/BLUEPRINT_REV3.md`](docs/truth/BLUEPRINT_REV3.md) — canonical human-readable product and technical architecture.
2. [`docs/truth/ARCHITECTURE_DECISIONS.md`](docs/truth/ARCHITECTURE_DECISIONS.md) — architecture decision index; accepted Project Truth EDR rows remain authoritative.
3. [`docs/truth/DEV_PLAN_REV3.md`](docs/truth/DEV_PLAN_REV3.md) — canonical implementation sequence and gates.
4. [`docs/truth/IMPLEMENTATION_STATE.md`](docs/truth/IMPLEMENTATION_STATE.md) — evidence-based current state and next work packet.
5. [`docs/truth/RESUME_PROMPT.md`](docs/truth/RESUME_PROMPT.md) — canonical bootstrap prompt for a fresh engineering session.

[`docs/blueprint/REV_2_0.md`](docs/blueprint/REV_2_0.md) is retained as historical/reference depth. It is no longer the forward-development authority where it conflicts with Rev 3.

Read [`AGENTS.md`](AGENTS.md) before changing code.

## The five environments

These must stay separate. Confusing them is the most common way a project like this fails.

1. **Authoring environment** — Cursor Desktop on your machine. Edits code, drives agents. Never authoritative for anything.
2. **DDE Core** — the cloud control plane. Owns Project Truth, missions, events, evidence. The only authoritative state.
3. **ExecutionEnvironment** — disposable sandboxed containers where workers run. Isolated filesystem, deny-by-default network, no ambient credentials.
4. **ProductEnvironment** — throwaway deployments of the software DDE is building, used to verify it. Distinct from ExecutionEnvironment.
5. **Worker providers** — model APIs and agent harnesses. Replaceable, never trusted, never authoritative.

## Codespace quickstart

This project is Linux/devcontainer-first. You do not need local Python or Docker.

1. Push this repository to GitHub and create a Codespace on `main`.
2. Connect Cursor: `Ctrl+Shift+P` → `Codespaces: Connect to Codespace`.
3. In the Codespace terminal:

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

`just check` runs lint, typecheck, unit tests and contract tests. GitHub Actions additionally applies migrations to an empty PostgreSQL 16 database (upgrade and reverse) and fails on generated-contract drift.

Copy `.env.example` when running outside compose. Use `DDE_DATABASE_URL` (async SQLAlchemy URL) and `DDE_REDIS_URL`.

## Windows complete product (installer)

Codespaces remain the default cloud path. For a single Windows install, build and run the complete installer under [`packaging/windows`](packaging/windows/README.md).

The installer bundles:

- **DDE Code** (Electron desktop UI under `Program Files\DDE\dde-code\`)
- **DDE Core** (Docker image)
- **PostgreSQL + Redis**
- **Database migrations** (Alembic via Core entrypoint)
- **GUI setup wizard** (`DdeSetupWizard.exe`)
- **Optional Authenticode signing** when cert secrets are configured

After install, open **DDE Code**. First run offers the wizard if needed:

1. Detects Docker and offers **download/install** if missing
2. Asks **local vs cloud** mode
3. Collects **admin login and provider API keys**
4. Loads Core, migrates DB, starts services, verifies `/healthz`

```powershell
powershell.exe -File packaging/windows/scripts/Build-Installer.ps1 -Version 0.1.0
# Primary Windows product:
#   dist\windows\DDE-Complete-Setup-0.1.0.exe
# (DDE Code UI + Core image + wizard; reuse tar with -SkipDocker)
```

CI: `.github/workflows/windows-installer.yml` (set `DDE_SIGNING_CERT_BASE64` + `DDE_SIGNING_CERT_PASSWORD` for signed releases).

## DDE Code (VS Code / Cursor extension suite)

Package [`interfaces/dde-studio`](interfaces/dde-studio/README.md) (display name **DDE Code**). **Primary Windows distribution** is the complete installer above. Optional clients: VS Code/Cursor **extension**, and UI-only Electron NSIS/portable for hosts that already have Core. Same dashboards (Hermes / Claude Code / DeepSeek + stubs). Live `/healthz` / `/readyz`. Plan amendment: [`docs/planning/dde-vscode-extension-suite.md`](docs/planning/dde-vscode-extension-suite.md) §3.2.

```powershell
cd interfaces\dde-studio
npm install
npm run compile
# Extension: F5 in that folder (optional Cursor host)
npm run desktop:install
$env:CSC_IDENTITY_AUTO_DISCOVERY = "false"
npm run dist:win
# UI-only (optional): interfaces\dde-studio\desktop\dist\DDE-Code-Setup-0.1.0.exe
```

`justfile` does not load dotenv. Export `DDE_DATABASE_URL` and `DDE_REDIS_URL` in the same shell if recipes cannot reach the database.

## Cursor worker (models via SDK bridge)

Workers reach Cursor models through `adapters/cursor`, which owns a local `cursor-sdk-bridge` process. The Cursor API key stays on the adapter host; it is never given to a WorkerRun environment. v1 is **local runtime only** so Cursor cannot clone or open PRs outside the DDE merge queue.

```bash
uv sync --extra cursor
# set DDE_CURSOR_API_KEY from https://cursor.com/dashboard/api
```

See [`docs/adapters/cursor.md`](docs/adapters/cursor.md).