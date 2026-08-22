#Requires -Version 5.1
<#
.SYNOPSIS
  Ensure Docker is available for DDE workers. Offers download/install when missing.
#>
[CmdletBinding()]
param(
    [string]$InstallerUrl = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe",
    [string]$DownloadDir = "$env:TEMP\DDE-Docker",
    [switch]$NonInteractive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$detect = Join-Path $PSScriptRoot "Detect-Docker.ps1"
$status = (& $detect).Trim()

Write-Host "Docker status: $status"

if ($status -eq "healthy") {
    Write-Host "Docker is ready for DDE worker execution."
    exit 0
}

if ($status -eq "installed_not_running") {
    Write-Host "Docker Desktop is installed but the engine is not running."
    Write-Host "Starting Docker Desktop..."
    $desktop = "${env:ProgramFiles}\Docker\Docker\Docker Desktop.exe"
    if (Test-Path -LiteralPath $desktop) {
        Start-Process -FilePath $desktop | Out-Null
        $deadline = (Get-Date).AddMinutes(3)
        while ((Get-Date) -lt $deadline) {
            Start-Sleep -Seconds 5
            $status = (& $detect).Trim()
            if ($status -eq "healthy") {
                Write-Host "Docker engine is healthy."
                exit 0
            }
        }
    }
    Write-Warning "Could not start Docker engine automatically. Start Docker Desktop, then re-run the wizard."
    exit 2
}

# missing
Write-Host ""
Write-Host "DDE local workers need Docker Desktop (WSL2 backend)."
Write-Host "Docker was not found on this machine."
Write-Host ""

if ($NonInteractive) {
    Write-Error "Docker is required and --NonInteractive was set. Install Docker Desktop, then re-run."
    exit 1
}

Write-Host "Choose an option:"
Write-Host "  [1] Download and run Docker Desktop installer (recommended)"
Write-Host "  [2] Open Docker download page in browser"
Write-Host "  [3] Continue without workers (Core-only; missions needing workers stay blocked)"
Write-Host "  [4] Cancel"
$choice = Read-Host "Selection"

switch ($choice) {
    "1" {
        New-Item -ItemType Directory -Force -Path $DownloadDir | Out-Null
        $installer = Join-Path $DownloadDir "DockerDesktopInstaller.exe"
        Write-Host "Downloading Docker Desktop..."
        Invoke-WebRequest -Uri $InstallerUrl -OutFile $installer
        Write-Host "Launching installer. Complete Docker setup (enable WSL2), reboot if asked, then return here."
        Start-Process -FilePath $installer -Wait
        Write-Host "Re-checking Docker..."
        $status = (& $detect).Trim()
        if ($status -eq "healthy") {
            Write-Host "Docker is healthy."
            exit 0
        }
        Write-Warning "Docker still not healthy (status=$status). Finish Docker Desktop setup and re-run Ensure-Docker.ps1."
        exit 2
    }
    "2" {
        Start-Process "https://docs.docker.com/desktop/setup/install/windows-install/"
        Write-Host "After installing Docker Desktop, re-run this script or the first-run wizard."
        exit 2
    }
    "3" {
        Write-Warning "Continuing without Docker. Worker execution will be unavailable until Docker is healthy."
        exit 3
    }
    default {
        Write-Host "Cancelled."
        exit 1
    }
}
