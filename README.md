# DDE — Development & Engineering Engine

DDE is a model-agnostic software manufacturing control plane. It owns product truth, mission state, context policy, routing policy, capability governance, verification and evidence. External agent harnesses are workers. Editors, phones, browsers and chat channels are clients. This repository is the DDE Core control plane.

The authoritative specification is [`docs/blueprint/REV_2_0.md`](docs/blueprint/REV_2_0.md).

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

## Cursor worker (models via SDK bridge)

Workers reach Cursor models through `adapters/cursor`, which owns a local `cursor-sdk-bridge` process. The Cursor API key stays on the adapter host; it is never given to a WorkerRun environment. v1 is **local runtime only** so Cursor cannot clone or open PRs outside the DDE merge queue.

```bash
uv sync --extra cursor
# set DDE_CURSOR_API_KEY from https://cursor.com/dashboard/api
```

See [`docs/adapters/cursor.md`](docs/adapters/cursor.md).
