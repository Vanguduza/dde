# DDE Code (extension package: `dde-studio`)



VS Code / Cursor **extension suite** that turns the editor into a DDE control plane:

activity-bar views for **Mission Overview** (primary home), connection, mission, integration, context, routing, fleet
Mission Control (Hermes / Claude Code / DeepSeek), verification, and approvals.



Authoritative plan: [`docs/planning/dde-vscode-extension-suite.md`](../../docs/planning/dde-vscode-extension-suite.md).



This is an `interfaces/**` client. It talks to Gateway HTTP and (later) CLI-JSON only.

It does **not** write Project Truth tables, own mission state, or import `engine/**`.



## Architecture (research-aligned)



| Decision | Choice |

|---|---|

| Delivery mode | **Two supported paths:** (1) VS Code / Cursor **extension**; (2) standalone Windows **Electron EXE** (`desktop/`) — user-requested amendment to plan §3.2. Not a Code fork. |

| Package / contribution id | `dde-studio` / `dde.studio.*` (kept per plan §8.1) |

| Display name | **DDE Code** |

| Transport now | Live `/healthz` + `/readyz`; real Gateway session/command and mission-scoped Frontend Studio read transport; other module list surfaces remain incremental |

| Transport later | Gateway REST/WS (DDE-027, S3) swaps under the same client abstraction |

| Auth | Gateway: `connection/authService.ts` → `SecretStorage`. Claude Code subscription: official `claude auth login` / `setup-token` + verify via `claude auth status` (SecretStorage / Electron safeStorage) — never fake signed-in; API key is backup only |

| Chat | Webview-first when built; Chat Participant only as gated additive (§3.3) |

| React/Vite `webview-ui` | **Implemented for the canonical central Frontend Studio workbench** — built during VSIX prepublish; older sidebar Frontend Studio views are compatibility shims |



```

Cursor / VS Code (workbench)                    Complete Windows product (double-click)
  └─ DDE Code extension (optional)                  └─ DDE-Complete-Setup → DDE Code
       ├─ Activity bar views                           ├─ Same activity-bar layout
       ├─ Central React Frontend Studio panel          ├─ Frontend workbench bundle
       ├─ Status bar → Core ready / down               ├─ Same shared HTML pages
       └─ Gateway /v1 + health probes                  ├─ Setup wizard + Start local Core
                                                       └─ Core via Docker (same install)
```

### Delivery paths

| Path | How to run | Bundles |
|---|---|---|
| **Complete Windows** (`packaging/windows/`) | `DDE-Complete-Setup-*.exe` | **Primary** — DDE Code + Core tar + wizard + compose |
| **Extension** (this package) | F5 in Cursor/VS Code | UI only (optional Cursor host) |
| **UI-only EXE** (`desktop/`) | `npm run dist:win` | Electron only (when Core already exists) |

Postgres, workers, and Gateway **cannot** honestly live *inside* the Electron process. The complete installer co-locates Docker appliance files next to DDE Code under `Program Files\DDE`.

### Deprecated approaches

| Approach | Status |
|---|---|
| Full Code - OSS fork | Out of scope — wrong cost curve |
| Embedding Core/Postgres in the Electron EXE | Not possible without Docker; use complete installer |
| Separate appliance-only + UI-only installers as primary | Superseded by `DDE-Complete-Setup` |



## Module map (sidebar today)



| View | Module id | Status |
|---|---|---|
| **Overview** (primary home) | `dde-core-ui` (Mission Overview) | **Main dashboard** — live System health; empty missions/tasks/events; operator cmds disabled until Gateway |
| Connection | `dde-core-ui` | **Live** `/healthz` + `/readyz` + auth SecretStorage |
| Mission | `dde-mission` | Rich stub shell (§5) — empty until CLI/Gateway |
| Integration | `dde-integration` | Rich stub shell (§4.2) — empty until DDE-013 |
| Context | `dde-context` | Rich stub shell (§5.2 coverage categories) |
| Routing | `dde-routing` | Rich stub shell (§5.1 gates vs ranking) |
| Hermes / Claude Code / DeepSeek | `dde-workers` | **Mission Control** fleet rooms (status, activity, routing, observability, control) + **live Core health** (no fake runs/events) |
| Verification | `dde-verification` | Rich stub shell (§5.3 thirteen stages) |
| Approvals | `dde-approvals` | Rich stub shell (§4.1) + Morning Review panel |
| Chat | `dde-chat` | Webview-first placeholder — blocked on Gateway S3 |
| Donors | `dde-donor` | Taxonomy legend stub — blocked on DDE-046/047 |
| Knowledge | `dde-knowledge` | Stub — blocked on DDE-033 |
| Evaluate | `dde-evaluation` | Stub — blocked on eval / promotion APIs |
| Debug | `dde-debug` | Stub inspector — health only until event stream |
| Preview | `product-environment` | Stub — blocked on DDE-038 |

Morning Review is a command + editor webview panel (not a sidebar row); same blocked-on DDE-026 copy on desktop.



## Hermes naming



Blueprint Appendix A: Hermes / Claude-Code-class / DeepSeek-harness-class are

**worker harness roles**, not embedded vendor products. When a Cursor worker card

exists, label it **Cursor Agent** — never bare "Cursor" (§3.4). The host is "your editor."



## Requirements (Windows)



- [Node.js 20+](https://nodejs.org/) (LTS)

- [Cursor](https://cursor.com/) or [VS Code](https://code.visualstudio.com/) 1.85+

- Optional: DDE Core on `http://127.0.0.1:8000` (local appliance / Docker)



## Run on Windows



Exact commands from a PowerShell prompt at the repo root:



```powershell

cd C:\Users\Admin\Documents\dde\interfaces\dde-studio

npm install

npm run compile

```



### Launch / debug (Extension Development Host)



**Option A — open the extension folder**



1. In Cursor or VS Code: **File → Open Folder…** → `interfaces\dde-studio`

2. Press **F5** (or Run and Debug → **Run DDE Studio Extension**)

3. A new **Extension Development Host** window opens with DDE Code loaded



**Option B — monorepo workspace**



1. Open the repo root `C:\Users\Admin\Documents\dde`

2. Still use the launch config under `interfaces\dde-studio\.vscode\launch.json`

   (open that folder as the workspace, or copy/adapt the config to a multi-root launch).

   Simplest path on Windows: Option A.



In the Extension Development Host:



1. Click the **DDE Code** icon in the **primary** activity bar (not the secondary sidebar — Cursor reserves that)

2. Open Connection (live health) and the stub module / harness views

3. Command Palette → `DDE Code: Open Hermes Mission Control` (full editor panel)

4. Command Palette → `DDE Code: Morning Review` (stub until S3)



### Settings



| Setting | Default | Purpose |

|---|---|---|

| `dde.studio.coreUrl` | `http://127.0.0.1:8000` | Local Core Gateway |

| `dde.studio.cloudUrl` | _(empty)_ | Cloud Gateway URL |

| `dde.studio.preferredTarget` | `local` | `local` or `cloud` |

| `dde.studio.pollIntervalMs` | `5000` | Health poll interval |



Session tokens (S3): `AuthService` + `context.secrets` — never these settings.



### Package a `.vsix` (optional)



```powershell

cd C:\Users\Admin\Documents\dde\interfaces\dde-studio

npm run package

```



Install: Extensions → `…` → Install from VSIX.

### Standalone Windows EXE (no VS Code)

Double-click UI. Does **not** include Core.

```powershell
cd C:\Users\Admin\Documents\dde\interfaces\dde-studio
npm install
npm run desktop:install
# unsigned NSIS + portable (set CSC_IDENTITY_AUTO_DISCOVERY=false if winCodeSign symlink fails)
$env:CSC_IDENTITY_AUTO_DISCOVERY = "false"
npm run dist:win
```

Outputs (also copy locally to `dist\windows\` if you want them next to the complete installer):

| Artifact | Path |
|---|---|
| **Complete installer (primary)** | `dist/windows/DDE-Complete-Setup-0.1.0.exe` via `packaging/windows` |
| NSIS installer (UI only) | `interfaces/dde-studio/desktop/dist/DDE-Code-Setup-0.1.0.exe` |
| Portable EXE (UI only) | `interfaces/dde-studio/desktop/dist/DDE-Code-Portable-0.1.0.exe` |
| Unpacked app (bundled into complete) | `interfaces/dde-studio/desktop/dist/win-unpacked/DDE Code.exe` |

Dev run (no installer):

```powershell
cd interfaces\dde-studio\desktop
npm start
```

**Setup wizard** / **Start local Core** in Connection call `DdeSetupWizard.exe` and `Start-DdeLocal.ps1` under `C:\Program Files\DDE\` when installed via `DDE-Complete-Setup`.

### CI compile check



```powershell

cd C:\Users\Admin\Documents\dde\interfaces\dde-studio

npm ci

npm run check

```



## What works today



- Activity-bar container with research module views (stubs + live Connection)

- Editor-area fleet Mission Control (Hermes / Claude Code / DeepSeek)

- Worker lifecycle UI placeholders (pause/checkpoint/resume/cancel) — disabled until Worker Manager APIs

- Live `/healthz` + `/readyz` (status bar + Connection)

- `AuthService` SecretStorage seam; `StubCliJsonTransport` for S1 bridge

- Claude Code subscription sign-in via official CLI (`claude auth login` / `claude setup-token`), verified with `claude auth status`; setup-token in SecretStorage / safeStorage; API key backup only

- Morning Review command stub

- Chat-participant registration guarded / deferred (§3.3)



## Honest gaps vs the full research doc



- No real mission/task/route/verify/approval data (Gateway empty; CLI `--json` not shipped)

- Panel mockups in §5.1–§5.3 not fully drawn — stubs only

- No React `webview-ui` yet (intentionally deferred to §8.4)

- No `dde-chat` webview, donor, knowledge, evaluation, debug, or ProductEnvironment views

- Host confirmation spike (Codespaces + Cursor) still an open question (§9)

- Claude Code: no embeddable third-party OAuth client / no device-code from Anthropic — DDE shells to the official CLI only ([docs](https://code.claude.com/docs/en/authentication))



## Next steps (plan §8)



1. When DDE-015 lands: wire CLI-JSON into Mission / Integration / workers.

2. Extend `dde-workers` with a real certified profile; keep lifecycle actions.

3. At S3: Gateway client + real `AuthService`; build Approvals + webview chat.

4. React migration when Integration + Approvals need interactive state.

