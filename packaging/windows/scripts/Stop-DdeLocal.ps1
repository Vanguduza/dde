#Requires -Version 5.1
<#
.SYNOPSIS
  Stop the local DDE appliance compose stack.
#>
[CmdletBinding()]
param(
    [string]$InstallRoot = "${env:ProgramFiles}\DDE"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$compose = Join-Path $InstallRoot "docker-compose.appliance.yml"
Write-Host "Stopping DDE local stack..."
& docker compose -f $compose down
if ($LASTEXITCODE -ne 0) {
    throw "docker compose down failed with exit $LASTEXITCODE"
}
Write-Host "Stopped."
