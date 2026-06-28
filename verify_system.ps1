# verify_system.ps1
# HDS v1.1 System Verification (Windows / PowerShell port of verify_system.sh)
# Usage:  powershell -ExecutionPolicy Bypass -File verify_system.ps1

$ErrorActionPreference = "Continue"
$BASE_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $BASE_DIR

# Resolve python launcher (python / py)
$PY = "python"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { $PY = "py" }
}

$script:PASSED = 0
$script:FAILED = 0
$script:WARN   = 0

function Pass($m) { Write-Host "[OK]   $m" -ForegroundColor Green;  $script:PASSED++ }
function Fail($m) { Write-Host "[FAIL] $m" -ForegroundColor Red;    $script:FAILED++ }
function Warn($m) { Write-Host "[WARN] $m" -ForegroundColor Yellow; $script:WARN++ }

function Check-Command($cmd, $name) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) { Pass "$name is installed" }
    else { Fail "$name is NOT installed" }
}

function Check-PyModule($import, $name) {
    & $PY -c "import $import" 2>$null
    if ($LASTEXITCODE -eq 0) { Pass "Python module: $name" }
    else { Fail "Python module MISSING: $name" }
}

function Check-File($path, $name) {
    if (Test-Path $path) { Pass "$name exists" } else { Fail "$name NOT FOUND: $path" }
}

function Check-Dir($path, $name) {
    if (Test-Path $path -PathType Container) { Pass "$name exists" } else { Fail "$name NOT FOUND: $path" }
}

function Check-Port($port, $name) {
    $inUse = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($inUse) { Warn "Port $port ($name) is IN USE" } else { Pass "Port $port ($name) is available" }
}

Write-Host ""
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "   HDS v1.1 SYSTEM VERIFICATION (Windows)" -ForegroundColor Cyan
Write-Host "==============================================================" -ForegroundColor Cyan

Write-Host "`nPhase 1: System Requirements" -ForegroundColor Blue
Check-Command $PY "Python"
Check-Command "node" "Node.js"
Check-Command "npm"  "NPM"
Check-Command "git"  "Git"

Write-Host "`nPhase 2: Vision Daemon Dependencies" -ForegroundColor Blue
Check-PyModule "cv2"        "OpenCV (cv2)"
Check-PyModule "PIL"        "Pillow (PIL)"
Check-PyModule "pyautogui"  "PyAutoGUI"
Check-PyModule "pytesseract" "Tesseract OCR"
Check-PyModule "numpy"      "NumPy"
if (Get-Command tesseract -ErrorAction SilentlyContinue) { Pass "Tesseract system binary" }
else { Warn "Tesseract system binary NOT FOUND (install: choco install tesseract)" }

Write-Host "`nPhase 3: Browser Daemon Dependencies" -ForegroundColor Blue
Check-PyModule "playwright" "Playwright"
Check-PyModule "bs4"        "BeautifulSoup4"
Check-PyModule "html2text"  "html2text"

Write-Host "`nPhase 4: Core Dependencies" -ForegroundColor Blue
Check-PyModule "requests" "Requests"
Check-PyModule "yaml"     "PyYAML"

Write-Host "`nPhase 5: Agent Files" -ForegroundColor Blue
Check-File "agent\agent.py"               "Main Agent (agent.py)"
Check-File "agent\vision_daemon.py"       "Vision Daemon wrapper"
Check-File "agent\vision_daemon_real.py"  "Vision Daemon real implementation"
Check-File "agent\browser_daemon.py"      "Browser Daemon wrapper"
Check-File "agent\microkernel_ipc.py"     "Microkernel IPC"
Check-File "agent\port_registry.py"       "Port Registry"
Check-File "agent\port_checker.py"        "Port Checker"

Write-Host "`nPhase 6: Directory Structure" -ForegroundColor Blue
Check-Dir "agent"   "Agent directory"
Check-Dir "gui"     "React GUI directory"
Check-Dir "ai-mind" "AI-MIND directory"
Check-Dir "tasks"   "Tasks directory"

Write-Host "`nPhase 7: Startup Scripts" -ForegroundColor Blue
Check-File "start_hds.ps1" "Full startup script (ps1)"
Check-File "verify_system.ps1"   "System verification (this script)"

Write-Host "`nPhase 8: Documentation" -ForegroundColor Blue
Check-File "requirements_real.txt" "Dependencies file"

Write-Host "`nPhase 9: Port Availability" -ForegroundColor Blue
Check-Port 9001 "Vision Daemon"
Check-Port 9002 "Browser Daemon"
Check-Port 8080 "Webhook API"
Check-Port 3000 "React GUI"

Write-Host "`nPhase 10: React GUI Setup" -ForegroundColor Blue
Check-File "gui\package.json" "React package.json"
if (Test-Path "gui\node_modules") { Pass "React dependencies installed" }
else { Warn "React dependencies NOT installed (cd gui; npm install)" }

Write-Host "`nPhase 11: Quick Connectivity Tests" -ForegroundColor Blue
& $PY -c "import sys; sys.path.insert(0,'agent'); import microkernel_ipc" 2>$null
if ($LASTEXITCODE -eq 0) { Pass "Microkernel IPC imports successful" } else { Fail "Microkernel IPC import failed" }

Write-Host "`n==============================================================" -ForegroundColor Cyan
Write-Host ("  Passed:   {0}" -f $script:PASSED) -ForegroundColor Green
Write-Host ("  Warnings: {0}" -f $script:WARN)   -ForegroundColor Yellow
Write-Host ("  Failed:   {0}" -f $script:FAILED) -ForegroundColor Red
Write-Host ("  Total:    {0}" -f ($script:PASSED + $script:WARN + $script:FAILED))
Write-Host "==============================================================" -ForegroundColor Cyan

if ($script:FAILED -gt 0) { exit 1 } else { exit 0 }
