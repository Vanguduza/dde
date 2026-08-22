# DDE Code — standalone Windows desktop

Electron shell for DDE Code. Same views as the VS Code extension (`../shared`).
Client only — Core runs via Docker from the complete installer.

## Run (dev)

```powershell
cd interfaces\dde-studio
npm run desktop:install
npm run desktop:start
```

## Build EXE (UI only)

```powershell
$env:CSC_IDENTITY_AUTO_DISCOVERY = "false"   # skip winCodeSign symlink issues
cd interfaces\dde-studio
npm run dist:win
```

| File | What |
|---|---|
| `desktop/dist/DDE-Code-Setup-0.1.0.exe` | NSIS installer (UI only) |
| `desktop/dist/DDE-Code-Portable-0.1.0.exe` | Single-file portable |
| `desktop/dist/win-unpacked/DDE Code.exe` | Unpacked app (bundled into complete installer) |

## Complete product (primary)

Prefer `packaging/windows` → `dist\windows\DDE-Complete-Setup-*.exe`, which installs this app under `Program Files\DDE\dde-code\` plus Core image, wizard, and compose scripts.

First run in DDE Code offers the setup wizard when Core is not configured, then **Start local Core** (`Start-DdeLocal.ps1`).
