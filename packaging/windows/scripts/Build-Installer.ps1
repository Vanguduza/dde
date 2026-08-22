#Requires -Version 5.1
<#
.SYNOPSIS
  Build DDE Code desktop, Core image, GUI wizard, and complete Windows installer.
.PARAMETER Version
  Release version tag for dde-core image and installer filename.
.PARAMETER SkipDocker
  Skip image build (use existing dist/windows/payload/dde-core.tar).
.PARAMETER SkipDesktop
  Skip Electron rebuild (use existing interfaces/.../desktop/dist/win-unpacked).
.PARAMETER SkipSign
  Skip Authenticode signing even when certificate env vars are set.
#>
[CmdletBinding()]
param(
    [string]$Version = "0.1.0",
    [switch]$SkipDocker,
    [switch]$SkipDesktop,
    [switch]$SkipSign
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$OutDir = Join-Path $RepoRoot "dist\windows"
$PayloadDir = Join-Path $OutDir "payload"
$WizardDir = Join-Path $RepoRoot "packaging\windows\DdeSetupWizard"
$DesktopDir = Join-Path $RepoRoot "interfaces\dde-studio\desktop"
$DesktopUnpacked = Join-Path $DesktopDir "dist\win-unpacked"
$DesktopExe = Join-Path $DesktopUnpacked "DDE Code.exe"
$ImageTag = "dde-core:$Version"
$ImageTar = Join-Path $PayloadDir "dde-core.tar"
$WizardExe = Join-Path $OutDir "DdeSetupWizard.exe"

function Find-Iscc {
    $candidates = @(
        $env:DDE_ISCC_PATH,
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    ) | Where-Object { $_ }
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) { return $c }
    }
    return $null
}

$IsccPath = Find-Iscc
New-Item -ItemType Directory -Force -Path $PayloadDir | Out-Null

function Find-Npm {
    $candidates = @(
        $env:DDE_NPM_PATH,
        (Get-Command npm.cmd -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
        (Get-Command npm -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
        "${env:ProgramFiles}\nodejs\npm.cmd",
        "${env:ProgramFiles(x86)}\nodejs\npm.cmd",
        "$env:LOCALAPPDATA\Programs\node\npm.cmd"
    ) | Where-Object { $_ }
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) { return $c }
    }
    return $null
}

function Invoke-SignRelease {
    param([string[]]$Files)
    $signScript = Join-Path $PSScriptRoot "Sign-Release.ps1"
    if ($SkipSign) { return }
    if (-not (Test-Path -LiteralPath $signScript)) { return }
    & $signScript -Files $Files
}

# 1) Build and export DDE Core Docker image
if (-not $SkipDocker) {
    Write-Host "Building DDE Core image $ImageTag..."
    & docker build `
        -f (Join-Path $RepoRoot "packaging\windows\Dockerfile.core") `
        -t $ImageTag `
        $RepoRoot
    if ($LASTEXITCODE -ne 0) { throw "docker build failed" }

    Write-Host "Exporting image to $ImageTar..."
    & docker save -o $ImageTar $ImageTag
    if ($LASTEXITCODE -ne 0) { throw "docker save failed" }
} elseif (-not (Test-Path -LiteralPath $ImageTar)) {
    throw "Missing $ImageTar and -SkipDocker was set"
}

# 2) Publish GUI setup wizard
Write-Host "Publishing DdeSetupWizard..."
& dotnet publish $WizardDir `
    -c Release `
    -r win-x64 `
    --self-contained true `
    -p:PublishSingleFile=true `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -o $OutDir
if ($LASTEXITCODE -ne 0) { throw "dotnet publish failed" }

Invoke-SignRelease -Files @($WizardExe)

# 3) Build DDE Code desktop (Electron unpacked dir for Inno bundle)
if (-not $SkipDesktop) {
    Write-Host "Building DDE Code desktop (win-unpacked)..."
    $npm = Find-Npm
    if (-not $npm) {
        throw "npm not found. Install Node.js or set DDE_NPM_PATH."
    }
    $env:CSC_IDENTITY_AUTO_DISCOVERY = "false"
    Push-Location $DesktopDir
    try {
        if (-not (Test-Path -LiteralPath (Join-Path $DesktopDir "node_modules"))) {
            & $npm install
            if ($LASTEXITCODE -ne 0) { throw "npm install (desktop) failed" }
        }
        & $npm run dist:dir
        if ($LASTEXITCODE -ne 0) { throw "npm run dist:dir failed" }
    } finally {
        Pop-Location
    }
} elseif (-not (Test-Path -LiteralPath $DesktopExe)) {
    throw "Missing $DesktopExe and -SkipDesktop was set"
}

if (-not (Test-Path -LiteralPath $DesktopExe)) {
    throw "DDE Code unpacked EXE not found: $DesktopExe"
}

# VERSION file for installer metadata
Set-Content -LiteralPath (Join-Path $OutDir "VERSION") -Value $Version -Encoding ASCII

# 4) Compile Inno Setup complete installer
if (-not $IsccPath -or -not (Test-Path -LiteralPath $IsccPath)) {
    throw @"
Inno Setup 6 not found.
Install from https://jrsoftware.org/isinfo.php then re-run.
Checked: Program Files, Program Files (x86), LocalAppData\Programs.
"@
}

$env:DDE_INSTALLER_VERSION = $Version
$env:DDE_REPO_ROOT = $RepoRoot
$env:DDE_DIST_WINDOWS = $OutDir
$env:DDE_CORE_IMAGE_TAG = $ImageTag
$env:DDE_DESKTOP_UNPACKED = $DesktopUnpacked

Write-Host "Compiling complete installer..."
& $IsccPath (Join-Path $RepoRoot "packaging\windows\setup.iss")
if ($LASTEXITCODE -ne 0) { throw "ISCC failed" }

$installer = Get-ChildItem $OutDir -Filter "DDE-Complete-Setup-$Version.exe" | Select-Object -First 1
if (-not $installer) {
    throw "Installer output not found: DDE-Complete-Setup-$Version.exe"
}

Invoke-SignRelease -Files @($installer.FullName)

# Copy UI-only artifacts next to the complete installer for convenience (optional builds)
$uiDist = Join-Path $DesktopDir "dist"
foreach ($name in @("DDE-Code-Setup-$Version.exe", "DDE-Code-Portable-$Version.exe")) {
    $src = Join-Path $uiDist $name
    if (Test-Path -LiteralPath $src) {
        Copy-Item -LiteralPath $src -Destination (Join-Path $OutDir $name) -Force
    }
}

Write-Host ""
Write-Host "Built:"
Write-Host "  Core image : $ImageTar"
Write-Host "  Wizard     : $WizardExe"
Write-Host "  DDE Code   : $DesktopExe"
Write-Host "  Installer  : $($installer.FullName)"
