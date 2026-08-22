#Requires -Version 5.1
<#
.SYNOPSIS
  Write install metadata consumed by the GUI wizard and service scripts.
  Optionally ensure Claude Code CLI is present (non-fatal if skipped/fails).
#>
[CmdletBinding()]
param(
    [string]$InstallRoot = "${env:ProgramFiles}\DDE",
    [string]$DataRoot = "$env:ProgramData\DDE",
    [string]$Version = "0.1.0",
    [string]$CoreImageTag = "dde-core:0.1.0",
    [switch]$EnsureClaudeCli,
    [switch]$SkipClaudeCli
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataRoot "artifacts") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataRoot "logs") | Out-Null

$meta = @{
    installed_at   = (Get-Date).ToString("o")
    install_root   = $InstallRoot
    data_root      = $DataRoot
    version        = $Version
    core_image_tag = $CoreImageTag
} | ConvertTo-Json

Set-Content -LiteralPath (Join-Path $DataRoot "install.json") -Value $meta -Encoding UTF8
Write-Host "Install metadata: $DataRoot\install.json"

# Claude CLI: prefer wizard consent (like Docker). Optional silent ensure for scripted installs.
if ($EnsureClaudeCli -and -not $SkipClaudeCli) {
    $ensure = Join-Path $PSScriptRoot "Ensure-ClaudeCli.ps1"
    if (Test-Path -LiteralPath $ensure) {
        Write-Host "Ensuring Claude Code CLI (official native installer)..."
        try {
            & $ensure -NonInteractive -Method Auto
        } catch {
            Write-Warning "Claude Code CLI ensure failed (non-fatal): $($_.Exception.Message)"
            Write-Warning "Run the setup wizard Claude Code page or: $ensure"
        }
    }
} else {
    Write-Host "Claude Code CLI: install during setup wizard (Install Claude Code CLI) or run scripts\Ensure-ClaudeCli.ps1"
}
