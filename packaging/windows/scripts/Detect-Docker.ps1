#Requires -Version 5.1
<#
.SYNOPSIS
  Detect Docker Desktop / engine availability for DDE local appliance mode.
.OUTPUTS
  Writes a single status token to stdout:
    healthy | installed_not_running | missing
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-DockerCli {
    try {
        $null = Get-Command docker -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

function Test-DockerEngine {
    try {
        & docker info --format "{{.ServerVersion}}" 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Test-DockerDesktopInstall {
    $paths = @(
        "${env:ProgramFiles}\Docker\Docker\Docker Desktop.exe",
        "${env:ProgramFiles}\Docker\Docker\DockerCli.exe"
    )
    foreach ($p in $paths) {
        if (Test-Path -LiteralPath $p) { return $true }
    }
    $uninstall = Get-ItemProperty HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\* `
        -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -like "Docker Desktop*" }
    return [bool]$uninstall
}

if (Test-DockerCli) {
    if (Test-DockerEngine) {
        Write-Output "healthy"
        exit 0
    }
    Write-Output "installed_not_running"
    exit 0
}

if (Test-DockerDesktopInstall) {
    Write-Output "installed_not_running"
    exit 0
}

Write-Output "missing"
exit 0
