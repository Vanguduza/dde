#Requires -Version 5.1
<#
.SYNOPSIS
  Shared helpers for Claude Code CLI detect / PATH / ensure (dot-sourced).
.NOTES
  Official Windows install (preferred): irm https://claude.ai/install.ps1 | iex
  Binary: %USERPROFILE%\.local\bin\claude.exe
  Docs: https://code.claude.com/docs/en/installation
#>

function Get-ClaudeNativeBinDir {
    return (Join-Path $env:USERPROFILE ".local\bin")
}

function Get-ClaudeCandidatePaths {
    $native = Join-Path (Get-ClaudeNativeBinDir) "claude.exe"
    $npmCmd = Join-Path $env:LOCALAPPDATA "npm\claude.cmd"
    $npmExe = Join-Path $env:APPDATA "npm\claude.exe"
    return @($native, $npmCmd, $npmExe)
}

function Update-SessionPathFromRegistry {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if (-not [string]::IsNullOrWhiteSpace($machine)) { $parts += $machine }
    if (-not [string]::IsNullOrWhiteSpace($user)) { $parts += $user }
    $env:Path = ($parts -join ";")
}

function Ensure-ClaudeNativeBinOnUserPath {
    <#
    .SYNOPSIS
      Persistently add %USERPROFILE%\.local\bin to User PATH when missing.
      Anthropic's native installer often leaves this step to the user.
    #>
    $binDir = Get-ClaudeNativeBinDir
    if (-not (Test-Path -LiteralPath $binDir)) {
        return $false
    }

    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ([string]::IsNullOrWhiteSpace($userPath)) {
        $userPath = ""
    }
    $entries = $userPath -split ";" | ForEach-Object { $_.Trim().TrimEnd("\") } | Where-Object { $_ }
    $norm = $binDir.TrimEnd("\")
    $already = $entries | Where-Object { $_.Equals($norm, [StringComparison]::OrdinalIgnoreCase) }
    if (-not $already) {
        $newPath = if ([string]::IsNullOrWhiteSpace($userPath)) { $binDir } else { "$userPath;$binDir" }
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    }

    # Always refresh this process so Get-Command works immediately.
    Update-SessionPathFromRegistry
    if ($env:Path -notlike "*$binDir*") {
        $env:Path = "$binDir;$env:Path"
    }
    return $true
}

function Find-ClaudeExecutablePath {
    Update-SessionPathFromRegistry
    try {
        $cmd = Get-Command claude -ErrorAction Stop
        if ($cmd -and $cmd.Source) {
            return $cmd.Source
        }
    } catch {
        # fall through to known locations
    }

    foreach ($candidate in Get-ClaudeCandidatePaths) {
        if (Test-Path -LiteralPath $candidate) {
            $dir = Split-Path -Parent $candidate
            if ($env:Path -notlike "*$dir*") {
                $env:Path = "$dir;$env:Path"
            }
            return $candidate
        }
    }
    return $null
}

function Test-ClaudeCliPresent {
    $path = Find-ClaudeExecutablePath
    return -not [string]::IsNullOrWhiteSpace($path)
}

function Get-ClaudeVersionText {
    $claude = Find-ClaudeExecutablePath
    if (-not $claude) {
        return $null
    }
    try {
        $out = & $claude --version 2>&1 | Out-String
        return $out.Trim()
    } catch {
        return $null
    }
}
