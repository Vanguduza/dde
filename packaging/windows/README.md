# DDE Windows complete installer

One shippable package for Windows: **DDE Code** (Electron desktop UI) + **DDE Core** appliance
(Postgres, Redis, migrations, Docker compose) + **first-run wizard**.

## Bundled components

| Artifact | Purpose |
|---|---|
| `dde-code\` | Unpacked **DDE Code** Electron app (primary UI) |
| `payload/dde-core.tar` | Pre-built DDE Core Docker image (API + Alembic migrations) |
| `DdeSetupWizard.exe` | WPF first-run wizard (Docker, credentials, Claude Code subscription login, stack start) |
| `docker-compose.appliance.yml` | Local Postgres, Redis, migrate job, Core |
| `scripts/` | Start/stop, Docker detect, **Ensure-ClaudeCli**, code signing helpers |

## Install flow (end user)

1. Run `DDE-Complete-Setup-<version>.exe` (signed when build secrets are configured)
2. Files install to `C:\Program Files\DDE\` (UI under `dde-code\`)
3. Open **DDE Code** (Start Menu / desktop shortcut / post-install launch)
4. On first run, DDE Code offers the **setup wizard** if Core is not configured:
   - **Docker** — detect, download/install Docker Desktop, re-check
   - **Mode** — local appliance or cloud client
   - **Credentials** — admin login + provider API keys (DeepSeek/OpenAI/Cursor/GitHub)
   - **Claude Code** — ensure official **Claude Code CLI** (`claude`) on PATH (native installer + User PATH), then **subscription login** via `claude auth login` / Verify (`claude auth status`). Anthropic API key is **backup only**. Wizard never invents a completed OAuth session.
   - **Install** — load Core image → start DB → **migrate** → start Core → `/healthz`
5. Use **Start local Core** (or wizard completion) until Connection shows Core ready
6. Hermes / Claude Code / DeepSeek dashboards work against live `/healthz` / `/readyz`

UI-only `DDE-Code-Setup-*.exe` remains available for Cursor/extension hosts that already have a remote Core; the **complete** installer is the primary Windows distribution.

## Build (maintainer)

Requirements: Docker (unless `-SkipDocker`), .NET 8 SDK, Node.js + npm, Inno Setup 6, Windows x64.

```powershell
powershell.exe -File packaging/windows/scripts/Build-Installer.ps1 -Version 0.1.0
# Reuse existing Core tar:
powershell.exe -File packaging/windows/scripts/Build-Installer.ps1 -Version 0.1.0 -SkipDocker
```

Outputs:

- `dist/windows/payload/dde-core.tar`
- `dist/windows/DdeSetupWizard.exe`
- `interfaces/dde-studio/desktop/dist/win-unpacked/DDE Code.exe`
- `dist/windows/DDE-Complete-Setup-0.1.0.exe`  ← **primary**

### Code signing

Set before build (local or CI):

```powershell
$env:DDE_SIGNING_CERT_PFX_PATH = "C:\certs\dde.pfx"
$env:DDE_SIGNING_CERT_PASSWORD = "..."
# optional
$env:DDE_SIGNING_TIMESTAMP_URL = "http://timestamp.digicert.com"
```

CI secrets:

- `DDE_SIGNING_CERT_BASE64` — PFX file base64
- `DDE_SIGNING_CERT_PASSWORD`

Signing uses `scripts/Sign-Release.ps1` (Authenticode via `signtool`). Electron-builder uses `CSC_IDENTITY_AUTO_DISCOVERY=false` during desktop packaging (Inno signs the complete EXE when secrets are set).

## Architecture notes

- **DDE Core** runs in Docker (Linux container) even on Windows — this matches the blueprint execution model.
- **Migrations** run via `entrypoint.sh migrate` before Core serves traffic.
- **Docker Desktop** is required for local mode (workers + compose stack).
- **Cloud mode** skips local stack startup; wizard stores remote API URL and keys only.
- DDE Code never embeds Postgres/Redis; it shells to `scripts\Start-DdeLocal.ps1` and launches `DdeSetupWizard.exe` from the same install root.

## Service scripts

```powershell
# Primary UI
& "C:\Program Files\DDE\dde-code\DDE Code.exe"

# Re-run GUI wizard
& "C:\Program Files\DDE\DdeSetupWizard.exe"

# Start stack (migrate + core) after initial setup
powershell.exe -File "C:\Program Files\DDE\scripts\Start-DdeLocal.ps1"

# Stop stack
powershell.exe -File "C:\Program Files\DDE\scripts\Stop-DdeLocal.ps1"
```

Config and secrets: `%ProgramData%\DDE\config.toml`, `%ProgramData%\DDE\.env`

### Claude Code auth (subscription first)

- **CLI on PATH (prerequisite):** Official native Windows installer — `irm https://claude.ai/install.ps1 | iex` (preferred; auto-updates). Binary: `%USERPROFILE%\.local\bin\claude.exe`. WinGet fallback: `winget install Anthropic.ClaudeCode`. DDE’s `scripts\Ensure-ClaudeCli.ps1` detects, installs with consent, and **adds `.local\bin` to User PATH** (the upstream installer often skips this), then refreshes the session PATH. Claim “CLI installed” only after `Get-Command claude` / known path succeeds (`claude --version`).
- **Primary auth:** `claude auth login` (browser: email / GitHub / Google IdP) verified with `claude auth status`. Optional long-lived token via `claude setup-token` stored in Windows Credential Manager (`oauth_token_ref = wincred:DDE/ClaudeCodeOAuthToken`).
- **Backup only:** Anthropic API key (`claude_code.auth_mode = api_key_backup`) when subscription login is unavailable.
- **Honesty:** Anthropic does **not** publish a third-party OAuth client for Claude Code subscriptions ([authentication docs](https://code.claude.com/docs/en/authentication)). Device-code (RFC 8628) is not supported. DDE never invents “signed in” without a verified CLI status or a shape-validated setup-token in secure storage. CLI present ≠ signed in.
- **UI:** DDE Code shows **Install Claude Code CLI** when `claude` is missing (runs Ensure script / opens docs), then re-detects — not a dead “Blocked” dead-end.
- Secrets are never written to `config.toml` / `.env` as raw tokens — only refs + account metadata (`email`, `session_status`, `auth_method`, `subscription_type`).
- Docs: [Installation](https://code.claude.com/docs/en/installation) · [Authentication](https://code.claude.com/docs/en/authentication) · [CLI reference](https://code.claude.com/docs/en/cli-reference)

```powershell
# Detect / install Claude Code CLI (dry-run safe)
powershell.exe -File "C:\Program Files\DDE\scripts\Detect-ClaudeCli.ps1"
powershell.exe -File "C:\Program Files\DDE\scripts\Ensure-ClaudeCli.ps1" -DryRun
powershell.exe -File "C:\Program Files\DDE\scripts\Ensure-ClaudeCli.ps1"   # interactive
```
