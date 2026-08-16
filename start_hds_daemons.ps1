# start_hds_daemons.ps1
# HDS Microkernel Daemon Startup (Windows port of start_hds_daemons.sh)

$ErrorActionPreference = "Continue"
$BASE_DIR  = Split-Path -Parent $MyInvocation.MyCommand.Path
$AGENT_DIR = Join-Path $BASE_DIR "agent"

$PY = "python"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { $PY = "py" }
}

Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  HDS MICROKERNEL DAEMON STARTUP" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan

function Test-Health($port) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:$port/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        return $true
    } catch { return $false }
}

function Start-Daemon($name, $port, $script) {
    if (Test-Health $port) {
        Write-Host "[OK] $name Daemon ($port) - already RUNNING" -ForegroundColor Green
        return
    }
    Write-Host "Starting $name Daemon on port $port..."
    $p = Start-Process -FilePath $PY -ArgumentList @($script, "$port") -WorkingDirectory $AGENT_DIR -PassThru -WindowStyle Hidden
    Write-Host "  PID: $($p.Id)"
    Start-Sleep -Seconds 1
    if (Test-Health $port) { Write-Host "  [OK] $name Daemon is ready!" -ForegroundColor Green }
    else { Write-Host "  [WARN] Could not verify $name Daemon status" -ForegroundColor Yellow }
}

Write-Host "`nComponent Status:" -ForegroundColor Blue
Start-Daemon "Vision"  9001 "vision_daemon.py"
Start-Daemon "Browser" 9002 "browser_daemon.py"

Write-Host "`n===========================================================" -ForegroundColor Cyan
Write-Host "Daemons started."
Write-Host "  Vision:  http://localhost:9001"
Write-Host "  Browser: http://localhost:9002"
Write-Host "===========================================================" -ForegroundColor Cyan
