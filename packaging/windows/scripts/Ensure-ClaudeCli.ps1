#Requires -Version 5.1
<#
.SYNOPSIS
  Ensure the official Claude Code CLI (`claude`) is on PATH for subscription auth.
.DESCRIPTION
  Detects `claude`, installs via Anthropic's native Windows installer when missing
  (preferred; auto-updates), with WinGet as fallback. Always ensures
  %USERPROFILE%\.local\bin is on User PATH and refreshes the current session.

  Does NOT claim signed-in. Auth remains `claude auth login` / `claude auth status`.

  Official docs: https://code.claude.com/docs/en/installation
.PARAMETER NonInteractive
  Install without prompting (wizard / UI consent already obtained).
.PARAMETER DryRun
  Print planned actions; do not download or mutate PATH.
.PARAMETER Method
  Native (install.ps1), Winget, or Auto (Native then Winget).
.OUTPUTS
  Exit 0 = present; 1 = cancelled/error; 2 = still missing after attempt.
#>
[CmdletBinding()]
param(
    [switch]$NonInteractive,
    [switch]$DryRun,
    [ValidateSet("Auto", "Native", "Winget")]
    [string]$Method = "Auto"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "ClaudeCli.Common.ps1")

$InstallDocsUrl = "https://code.claude.com/docs/en/installation"
$NativeInstallUrl = "https://claude.ai/install.ps1"
$NativeBin = Join-Path (Get-ClaudeNativeBinDir) "claude.exe"

function Write-Status {
    param([string]$Message)
    Write-Host $Message
}

function Test-Ready {
    # Prefer fixing PATH when binary already exists off-PATH.
    if (Test-Path -LiteralPath $NativeBin) {
        if ($DryRun) {
            Write-Status "[DryRun] Would ensure User PATH includes $(Get-ClaudeNativeBinDir)"
            return $true
        }
        [void](Ensure-ClaudeNativeBinOnUserPath)
    }
    return (Test-ClaudeCliPresent)
}

function Invoke-NativeInstall {
    Write-Status "Installing Claude Code CLI via official native installer..."
    Write-Status "  $NativeInstallUrl"
    if ($DryRun) {
        Write-Status "[DryRun] Would run: irm $NativeInstallUrl | iex"
        Write-Status "[DryRun] Would add $(Get-ClaudeNativeBinDir) to User PATH"
        return
    }
    # Download then invoke so we control ExecutionPolicy and avoid nested irm|iex surprises.
    $scriptText = (Invoke-WebRequest -Uri $NativeInstallUrl -UseBasicParsing -TimeoutSec 120).Content
    $tmp = Join-Path $env:TEMP ("dde-claude-install-{0}.ps1" -f [guid]::NewGuid().ToString("N"))
    try {
        Set-Content -LiteralPath $tmp -Value $scriptText -Encoding UTF8
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $tmp
        if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
            throw "Native installer exited with code $LASTEXITCODE"
        }
    } finally {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
    [void](Ensure-ClaudeNativeBinOnUserPath)
}

function Invoke-WingetInstall {
    Write-Status "Installing Claude Code CLI via winget (Anthropic.ClaudeCode)..."
    if ($DryRun) {
        Write-Status "[DryRun] Would run: winget install --id Anthropic.ClaudeCode -e --accept-package-agreements --accept-source-agreements"
        return
    }
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "winget is not available on this machine."
    }
    & winget install --id Anthropic.ClaudeCode -e --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
        throw "winget install exited with code $LASTEXITCODE"
    }
    # Native layout is still the usual path; also refresh PATH for WinGet layouts.
    if (Test-Path -LiteralPath $NativeBin) {
        [void](Ensure-ClaudeNativeBinOnUserPath)
    } else {
        Update-SessionPathFromRegistry
    }
}

function Invoke-Install {
    param([string]$Chosen)
    switch ($Chosen) {
        "Native" { Invoke-NativeInstall }
        "Winget" { Invoke-WingetInstall }
        "Auto" {
            try {
                Invoke-NativeInstall
            } catch {
                Write-Warning "Native install failed: $($_.Exception.Message)"
                Write-Status "Falling back to winget..."
                Invoke-WingetInstall
            }
        }
    }
}

# --- main ---
Update-SessionPathFromRegistry

if (Test-Ready) {
    $ver = Get-ClaudeVersionText
    Write-Status "Claude Code CLI is present on PATH."
    if ($ver) { Write-Status "  $ver" }
    Write-Status 'Auth is separate: run claude auth login, verify with claude auth status.'
    exit 0
}

Write-Status ""
Write-Status 'Claude Code CLI (claude) was not found on PATH.'
Write-Status "Subscription auth requires the official CLI."
Write-Status "Docs: $InstallDocsUrl"
Write-Status "Preferred install: native PowerShell installer (auto-updates)."
Write-Status "Binary location: $NativeBin"
Write-Status ""

if ($DryRun) {
    Write-Status "[DryRun] Claude CLI missing - would install via method=$Method"
    Invoke-Install -Chosen $Method
    Write-Status "[DryRun] Done (no changes applied)."
    exit 0
}

if (-not $NonInteractive) {
    Write-Status "Choose an option:"
    Write-Status "  [1] Install Claude Code CLI now (recommended - official native installer)"
    Write-Status "  [2] Install via winget (Anthropic.ClaudeCode)"
    Write-Status "  [3] Open install docs in browser"
    Write-Status "  [4] Cancel"
    $choice = Read-Host "Selection"
    switch ($choice) {
        "1" { $Method = "Native" }
        "2" { $Method = "Winget" }
        "3" {
            Start-Process $InstallDocsUrl
            Write-Status "After installing, re-run Ensure-ClaudeCli.ps1 or the setup wizard."
            exit 2
        }
        default {
            Write-Status "Cancelled."
            exit 1
        }
    }
}

try {
    Invoke-Install -Chosen $Method
} catch {
    Write-Error "Claude Code CLI install failed: $($_.Exception.Message)"
    exit 1
}

if (Test-Ready) {
    $ver = Get-ClaudeVersionText
    Write-Status "Claude Code CLI installed and on PATH."
    if ($ver) { Write-Status "  $ver" }
    Write-Status 'Next: claude auth login then claude auth status (wizard Verify).'
    # Soft-check auth help without claiming logged-in.
    try {
        $claude = Find-ClaudeExecutablePath
        if ($claude) {
            & $claude auth status --help 2>&1 | Out-Null
        }
    } catch {
        # ignore - version success is enough for "CLI installed"
    }
    exit 0
}

Write-Warning "Claude CLI still not on PATH after install. Add $(Get-ClaudeNativeBinDir) to User PATH, open a new terminal, re-run this script."
Write-Warning "Docs: $InstallDocsUrl"
exit 2
