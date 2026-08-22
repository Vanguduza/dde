#Requires -Version 5.1
<#
.SYNOPSIS
  Run the project's standard check suite and, only if every check passes, stage
  changes, commit, and push — all in one invocation.

.DESCRIPTION
  This script automates ONLY the mechanical "run checks, then commit+push" sequence
  (the same commands `just check` runs, invoked directly since `just` has had
  PATH/shell issues on this machine). It exists to save token/turn overhead for a
  human or an agent who would otherwise need several separate tool calls (lint,
  typecheck, test, git add, git commit, git push).

  It is NOT a substitute for the independent blueprint chapter-gate review required
  by .cursor/rules/mission-chapter-gate.mdc for any chartered DDE-N mission. This
  script exiting 0 means CI is green; it does NOT mean a blueprint chapter is done.
  See AGENTS.md, section "Mechanical commit helpers", for the full caveat.

  Check list mirrors the justfile `check` recipe (lint typecheck test contract-test)
  exactly, in the same order:
    1. uv run ruff check .
    2. uv run ruff format --check .
    3. uv run mypy
    4. uv run pytest tests/unit tests/contract tests/recovery --cov --cov-report=term-missing
    5. uv run python -m scripts.generate_contracts --check
    6. uv run pytest tests/contract

  On the first failing check, the script stops immediately with a non-zero exit
  code and performs NO git operations at all (no add, no commit, no push).

  Never uses --no-verify, never skips hooks, never amends, never force-pushes, and
  never touches git config, per AGENTS.md's git safety rules.

.PARAMETER Message
  Commit message (required).

.PARAMETER Push
  Whether to push after committing. Default: $true.

.PARAMETER Paths
  Specific paths to stage/commit. Default (omitted): stage everything via
  `git add -A` and commit everything staged. When given, only these paths are
  staged and only these paths are committed (other already-staged changes, if any,
  are left untouched in the index).

.EXAMPLE
  ./scripts/commit_if_green.ps1 -Message "Add eval corpus tables"

.EXAMPLE
  ./scripts/commit_if_green.ps1 -Message "Fix typo" -Paths docs/README.md -Push:$false
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Message,

    [bool]$Push = $true,

    [string[]]$Paths
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Msg)
    Write-Host "==> $Msg" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Msg)
    Write-Host "  OK: $Msg" -ForegroundColor Green
}

function Write-FailLine {
    param([string]$Msg)
    Write-Host "  FAIL: $Msg" -ForegroundColor Red
}

function Invoke-Check {
    param(
        [string]$Name,
        [string]$Exe,
        [string[]]$CmdArgs
    )
    Write-Step "check: $Name ($Exe $($CmdArgs -join ' '))"
    & $Exe @CmdArgs
    if ($LASTEXITCODE -ne 0) {
        Write-FailLine "$Name failed (exit $LASTEXITCODE)"
        Write-Host ""
        Write-Host "SUMMARY: FAILED at check '$Name'. No git operations were performed." -ForegroundColor Red
        exit 1
    }
    Write-Ok $Name
}

$repoRoot = (& git rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($repoRoot)) {
    Write-FailLine "Not inside a git repository."
    exit 1
}
Set-Location $repoRoot.Trim()

# Mirrors justfile `check: lint typecheck test contract-test` exactly — do not
# reorder or add/drop steps here without updating the justfile too.
Invoke-Check -Name "lint (ruff check)" -Exe "uv" -CmdArgs @("run", "ruff", "check", ".")
Invoke-Check -Name "lint (ruff format)" -Exe "uv" -CmdArgs @("run", "ruff", "format", "--check", ".")
Invoke-Check -Name "typecheck (mypy)" -Exe "uv" -CmdArgs @("run", "mypy")
Invoke-Check -Name "test (pytest)" -Exe "uv" -CmdArgs @("run", "pytest", "tests/unit", "tests/contract", "tests/recovery", "--cov", "--cov-report=term-missing")
Invoke-Check -Name "contract-test (generate_contracts --check)" -Exe "uv" -CmdArgs @("run", "python", "-m", "scripts.generate_contracts", "--check")
Invoke-Check -Name "contract-test (pytest tests/contract)" -Exe "uv" -CmdArgs @("run", "pytest", "tests/contract")

Write-Host ""
Write-Host "All checks passed." -ForegroundColor Green
Write-Host ""

Write-Step "git add"
if ($Paths -and $Paths.Count -gt 0) {
    & git add -- @Paths
} else {
    & git add -A
}
if ($LASTEXITCODE -ne 0) {
    Write-FailLine "git add failed"
    Write-Host ""
    Write-Host "SUMMARY: FAILED at git add. No commit was created." -ForegroundColor Red
    exit 1
}

if ($Paths -and $Paths.Count -gt 0) {
    & git diff --cached --quiet -- @Paths
} else {
    & git diff --cached --quiet
}
$nothingStaged = ($LASTEXITCODE -eq 0)
if ($nothingStaged) {
    Write-FailLine "Nothing to commit (no staged changes after 'git add')."
    Write-Host ""
    Write-Host "SUMMARY: FAILED - nothing to commit. No commit was created." -ForegroundColor Red
    exit 2
}

Write-Step "git commit"
if ($Paths -and $Paths.Count -gt 0) {
    & git commit -m $Message -- @Paths
} else {
    & git commit -m $Message
}
if ($LASTEXITCODE -ne 0) {
    Write-FailLine "git commit failed"
    Write-Host ""
    Write-Host "SUMMARY: FAILED at git commit. Review output above." -ForegroundColor Red
    exit 1
}

$commitHash = (& git rev-parse --short HEAD).Trim()
Write-Ok "committed $commitHash"

if (-not $Push) {
    Write-Host ""
    Write-Host "SUCCESS: checks passed, committed $commitHash. Push skipped (-Push:`$false)." -ForegroundColor Green
    exit 0
}

Write-Step "git push"
$branch = (& git rev-parse --abbrev-ref HEAD).Trim()
$previousEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$null = & git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>$null
$hasUpstream = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $previousEap

if (-not $hasUpstream) {
    Write-Host "  No upstream configured for '$branch'; running 'git push -u origin HEAD'." -ForegroundColor Yellow
    & git push -u origin HEAD
} else {
    & git push
}
if ($LASTEXITCODE -ne 0) {
    Write-FailLine "git push failed"
    Write-Host ""
    Write-Host "SUMMARY: FAILED at git push. Commit $commitHash was created locally but NOT pushed." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "SUCCESS: checks passed, committed and pushed $commitHash." -ForegroundColor Green
exit 0
