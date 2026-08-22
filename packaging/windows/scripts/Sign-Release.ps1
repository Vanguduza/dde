#Requires -Version 5.1
<#
.SYNOPSIS
  Authenticode-sign release binaries when certificate env vars are present.

  Set one of:
    DDE_SIGNING_CERT_PFX_PATH + DDE_SIGNING_CERT_PASSWORD
    DDE_SIGNING_CERT_BASE64 + DDE_SIGNING_CERT_PASSWORD  (CI: decode to temp PFX)

  Optional:
    DDE_SIGNING_TIMESTAMP_URL (default http://timestamp.digicert.com)
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string[]]$Files
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Find-SignTool {
    $sdk = "${env:ProgramFiles(x86)}\Windows Kits\10\bin"
    if (Test-Path -LiteralPath $sdk) {
        $latest = Get-ChildItem $sdk -Directory | Sort-Object Name -Descending | Select-Object -First 1
        $candidate = Join-Path $latest.FullName "x64\signtool.exe"
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    $fallback = "${env:ProgramFiles(x86)}\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe"
    if (Test-Path -LiteralPath $fallback) { return $fallback }
    return $null
}

$pfxPath = $env:DDE_SIGNING_CERT_PFX_PATH
$password = $env:DDE_SIGNING_CERT_PASSWORD
$timestamp = if ($env:DDE_SIGNING_TIMESTAMP_URL) { $env:DDE_SIGNING_TIMESTAMP_URL } else { "http://timestamp.digicert.com" }

if ($env:DDE_SIGNING_CERT_BASE64 -and -not $pfxPath) {
    $pfxPath = Join-Path $env:TEMP "dde-signing.pfx"
    [IO.File]::WriteAllBytes($pfxPath, [Convert]::FromBase64String($env:DDE_SIGNING_CERT_BASE64))
}

if (-not $pfxPath -or -not $password) {
    Write-Host "Signing skipped (DDE_SIGNING_CERT_* not configured)."
    return
}

$signtool = Find-SignTool
if (-not $signtool) {
    Write-Warning "signtool.exe not found. Install Windows SDK signing tools."
    return
}

foreach ($file in $Files) {
    if (-not (Test-Path -LiteralPath $file)) {
        Write-Warning "Missing file, skip sign: $file"
        continue
    }
    Write-Host "Signing $file"
    & $signtool sign /fd SHA256 /tr $timestamp /td SHA256 /f $pfxPath /p $password $file
    if ($LASTEXITCODE -ne 0) {
        throw "signtool failed for $file"
    }
}

Write-Host "Signing complete."
