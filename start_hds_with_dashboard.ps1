# start_hds_with_dashboard.ps1
# HDS Nucleus + Dashboard Startup (Windows port of start_hds_with_dashboard.sh)
# Usage: powershell -ExecutionPolicy Bypass -File start_hds_with_dashboard.ps1 [-Mode monitor|once] [-Ai name] [-AutoKill]

param(
    [string]$Mode = "monitor",
    [string]$Ai = $(if ($env:DEPLOYING_AI) { $env:DEPLOYING_AI } else { "hds_cli" }),
    [switch]$AutoKill
)

$ErrorActionPreference = "Continue"
$BASE_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $BASE_DIR

$PY = "python"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { $PY = "py" }
}

$LOG = Join-Path $env:TEMP "hds"
New-Item -ItemType Directory -Force -Path $LOG | Out-Null

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "    HDS NUCLEUS + DASHBOARD STARTUP SEQUENCE" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan

# Phase 1: Allocate ports
Write-Host "`nPhase 1: Allocating Ports..." -ForegroundColor Blue
$autoKillPy = if ($AutoKill) { "True" } else { "False" }
$allocCode = @"
import sys, json
sys.path.insert(0, 'agent')
from port_registry import PortRegistry
config = PortRegistry.allocate_instance(deploying_ai='$Ai', auto_kill=$autoKillPy)
print(json.dumps(config))
"@
$ALLOCATION = & $PY -c $allocCode
$cfg = $ALLOCATION | ConvertFrom-Json

$env:VISION_PORT  = $cfg.vision_daemon_port
$env:BROWSER_PORT = $cfg.browser_daemon_port
$env:WEBHOOK_PORT = $cfg.webhook_port

Write-Host "[OK] Ports allocated:" -ForegroundColor Green
Write-Host "   Vision:   $($env:VISION_PORT)"
Write-Host "   Browser:  $($env:BROWSER_PORT)"
Write-Host "   Webhook:  $($env:WEBHOOK_PORT)"

# Phase 2: Start daemons
Write-Host "`nPhase 2: Starting Microkernel Daemons..." -ForegroundColor Blue
$v = Start-Process -FilePath $PY -ArgumentList "agent\vision_daemon.py"  -WorkingDirectory $BASE_DIR -PassThru -WindowStyle Hidden -RedirectStandardOutput "$LOG\vision.log"  -RedirectStandardError "$LOG\vision.err"
Write-Host "   Vision Daemon (PID: $($v.Id))"
$b = Start-Process -FilePath $PY -ArgumentList "agent\browser_daemon.py" -WorkingDirectory $BASE_DIR -PassThru -WindowStyle Hidden -RedirectStandardOutput "$LOG\browser.log" -RedirectStandardError "$LOG\browser.err"
Write-Host "   Browser Daemon (PID: $($b.Id))"
$w = Start-Process -FilePath $PY -ArgumentList "agent\webhook_server_enhanced.py" -WorkingDirectory $BASE_DIR -PassThru -WindowStyle Hidden -RedirectStandardOutput "$LOG\webhook.log" -RedirectStandardError "$LOG\webhook.err"
Write-Host "   Webhook Server + Dashboard (PID: $($w.Id))"

Start-Sleep -Seconds 2

# Phase 3: Start agent
Write-Host "`nPhase 3: Starting HDS Agent Nucleus..." -ForegroundColor Blue
$env:MODE = $Mode
$agentCode = @"
import sys, os
sys.path.insert(0, 'agent')
from agent import HDS6Agent
agent = HDS6Agent()
if os.environ.get('MODE', 'monitor') == 'monitor':
    agent.monitor()
else:
    agent.run()
"@
& $PY -c $agentCode

Write-Host "`nDashboard was available at: http://localhost:$($env:WEBHOOK_PORT)" -ForegroundColor Cyan
