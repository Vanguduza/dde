#Requires -Version 5.1
<#
.SYNOPSIS
  Detect whether the official Claude Code CLI (`claude`) is available.
.OUTPUTS
  Writes a single status token to stdout:
    present | missing
.NOTES
  "present" requires Get-Command claude (or a known install path that we add to
  this session's PATH). Does not imply signed-in — use `claude auth status` for that.
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "ClaudeCli.Common.ps1")

if (Test-ClaudeCliPresent) {
    Write-Output "present"
    exit 0
}

Write-Output "missing"
exit 0
