# start_hds_agent.ps1
# HDS Agent Startup (Windows port of start_hds_agent.sh)
# Usage: powershell -ExecutionPolicy Bypass -File start_hds_agent.ps1 [-Mode monitor|once|interactive]

param([string]$Mode = "interactive")

$ErrorActionPreference = "Continue"
$BASE_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $BASE_DIR

$PY = "python"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { $PY = "py" }
}

function Test-Health($port) {
    try { Invoke-WebRequest -Uri "http://localhost:$port/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop | Out-Null; return $true }
    catch { return $false }
}

Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  HDS NUCLEUS - FULL SYSTEM STARTUP" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan

Write-Host "`nChecking daemon status..."
if (-not (Test-Health 9001)) { Write-Host "[WARN] Vision Daemon (9001) not running" -ForegroundColor Yellow }
if (-not (Test-Health 9002)) { Write-Host "[WARN] Browser Daemon (9002) not running" -ForegroundColor Yellow }

Write-Host "`nStarting HDS Agent (mode: $Mode)..." -ForegroundColor Blue

$call = switch ($Mode) {
    "monitor" { "agent.monitor()" }
    "once"    { "agent.run()" }
    default   { "print('[HDS] Agent initialized. Ctrl+C to exit.'); agent.run()" }
}

$pycode = @"
import sys
sys.path.insert(0, 'agent')
from agent import HDS6Agent
agent = HDS6Agent()
$call
"@

& $PY -c $pycode
