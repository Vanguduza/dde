#Requires -Version 5.1
<#
.SYNOPSIS
  Start the local DDE appliance: DB, migrate, Core.
#>
[CmdletBinding()]
param(
    [string]$InstallRoot = "${env:ProgramFiles}\DDE",
    [string]$DataRoot = "$env:ProgramData\DDE"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$detect = Join-Path $InstallRoot "scripts\Detect-Docker.ps1"
$status = (& $detect).Trim()
if ($status -ne "healthy") {
    throw "Docker is not healthy (status=$status). Run DdeSetupWizard.exe first."
}

$compose = Join-Path $InstallRoot "docker-compose.appliance.yml"
$envFile = Join-Path $DataRoot ".env"
if (-not (Test-Path -LiteralPath $compose)) {
    throw "Missing compose file: $compose"
}

function Invoke-Compose([string[]]$ExtraArgs) {
    $args = @("compose", "-f", $compose)
    if (Test-Path -LiteralPath $envFile) {
        $args += @("--env-file", $envFile)
    }
    $args += $ExtraArgs
    & docker @args
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed: $($ExtraArgs -join ' ')"
    }
}

Write-Host "Ensuring Postgres and Redis..."
Invoke-Compose @("up", "-d", "postgres", "redis")

Write-Host "Applying migrations..."
Invoke-Compose @("--profile", "bootstrap", "run", "--rm", "migrate")

Write-Host "Starting DDE Core..."
Invoke-Compose @("up", "-d", "core")

Write-Host "Stack started. API: http://127.0.0.1:8000"
