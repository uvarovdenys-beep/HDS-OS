# start_hds.ps1
# HDS Complete System Startup (Windows port of start_hds.sh)
# Usage: powershell -ExecutionPolicy Bypass -File start_hds.ps1 [-Mode monitor|once|interactive]

param([string]$Mode = "interactive")

$ErrorActionPreference = "Continue"
$BASE_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $BASE_DIR

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "        HDS - COMPLETE SYSTEM STARTUP" -ForegroundColor Cyan
Write-Host "        MARK TWAIN Nucleus + Microkernel Daemons" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan

foreach ($f in @("start_hds_daemons.ps1", "start_hds_agent.ps1")) {
    if (-not (Test-Path (Join-Path $BASE_DIR $f))) {
        Write-Host "[FAIL] $f not found" -ForegroundColor Red
        exit 1
    }
}

Write-Host "`nPhase 1: Starting Microkernel Daemons..." -ForegroundColor Blue
& (Join-Path $BASE_DIR "start_hds_daemons.ps1")

Start-Sleep -Seconds 3

Write-Host "`nPhase 2: Starting HDS Agent..." -ForegroundColor Blue
& (Join-Path $BASE_DIR "start_hds_agent.ps1") -Mode $Mode
