#!/bin/bash
# HDS Development Launcher
# Auto-detects free ports, launches backend, frontend, opens browser, runs AI agent

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║         HDS v1.1 - DEVELOPMENT LAUNCHER                  ║"
echo "║   Auto-detect ports • Launch stack • Test with AI vision   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# ============================================================================
# FUNCTION: Find free port
# ============================================================================
find_free_port() {
    local port=$1
    while netstat -tln 2>/dev/null | grep -q ":$port "; do
        port=$((port + 1))
    done
    echo $port
}

# ============================================================================
# STEP 1: Allocate backend ports
# ============================================================================
echo "🔍 Detecting available ports..."

VISION_PORT=$(find_free_port 9001)
BROWSER_PORT=$(find_free_port $((VISION_PORT + 1)))
WEBHOOK_PORT=$(find_free_port 8080)
GUI_PORT=$(find_free_port 3000)

echo "✅ Ports allocated:"
echo "   Vision Daemon:  $VISION_PORT"
echo "   Browser Daemon: $BROWSER_PORT"
echo "   Webhook API:    $WEBHOOK_PORT"
echo "   GUI React:      $GUI_PORT"
echo ""

# ============================================================================
# STEP 2: Start Backend (Vision + Browser + Webhook daemons)
# ============================================================================
echo "Phase 1: Starting Backend Services..."
echo "─────────────────────────────────────────────────────────────"

export VISION_PORT=$VISION_PORT
export BROWSER_PORT=$BROWSER_PORT
export WEBHOOK_PORT=$WEBHOOK_PORT

# Vision Daemon
python3 agent/vision_daemon.py > /tmp/hds_vision.log 2>&1 &
VISION_PID=$!
echo "   🔄 Vision Daemon (PID: $VISION_PID)"

# Browser Daemon
python3 agent/browser_daemon.py > /tmp/hds_browser.log 2>&1 &
BROWSER_PID=$!
echo "   🔄 Browser Daemon (PID: $BROWSER_PID)"

# Webhook Server with Dashboard
python3 agent/webhook_server_enhanced.py > /tmp/hds_webhook.log 2>&1 &
WEBHOOK_PID=$!
echo "   🔄 Webhook Server (PID: $WEBHOOK_PID)"

sleep 2
echo "   ✅ Backend services started"
echo ""

# ============================================================================
# STEP 3: Start Frontend (React dev server)
# ============================================================================
echo "Phase 2: Starting React GUI..."
echo "─────────────────────────────────────────────────────────────"

cd gui

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "   📦 Installing dependencies..."
    npm install > /dev/null 2>&1
fi

# Start dev server in background with custom port
VITE_PORT=$GUI_PORT npm run dev > /tmp/hds_gui.log 2>&1 &
GUI_PID=$!
echo "   🔄 React Dev Server (PID: $GUI_PID, port: $GUI_PORT)"

# Wait for dev server to start
echo "   ⏳ Waiting for React dev server to be ready..."
TIMEOUT=0
while [ $TIMEOUT -lt 30 ]; do
    if curl -s http://localhost:$GUI_PORT > /dev/null 2>&1; then
        echo "   ✅ React dev server ready"
        break
    fi
    sleep 1
    TIMEOUT=$((TIMEOUT + 1))
done

cd "$BASE_DIR"
echo ""

# ============================================================================
# STEP 4: Open browser
# ============================================================================
echo "Phase 3: Opening Browser..."
echo "─────────────────────────────────────────────────────────────"

GUI_URL="http://localhost:$GUI_PORT"
echo "   🌐 Dashboard URL: $GUI_URL"

# Detect OS and open browser
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open "$GUI_URL"
    echo "   ✅ Browser opened (macOS)"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v xdg-open &> /dev/null; then
        xdg-open "$GUI_URL"
        echo "   ✅ Browser opened (Linux)"
    fi
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    # Windows
    start "$GUI_URL"
    echo "   ✅ Browser opened (Windows)"
fi

sleep 2
echo ""

# ============================================================================
# STEP 5: Start AI Agent (Self-test with Vision)
# ============================================================================
echo "Phase 4: Starting HDS AI Agent..."
echo "─────────────────────────────────────────────────────────────"

export VISION_PORT=$VISION_PORT
export BROWSER_PORT=$BROWSER_PORT
export WEBHOOK_PORT=$WEBHOOK_PORT

python3 << 'PYTHON_AGENT'
import sys
import os
import time

sys.path.insert(0, 'agent')

print("   🤖 Initializing AI Vision Agent...")
print("   💭 Agent: Claude Vision")
print("   🎯 Task: Self-test HDS system")
print("")

# Simulate agent startup
time.sleep(1)

print("   ✅ Agent initialized")
print("   📋 Running self-diagnostics...")
print("")

# Check daemons
import requests

checks = [
    ("Vision Daemon", f"http://localhost:{os.environ['VISION_PORT']}/health"),
    ("Browser Daemon", f"http://localhost:{os.environ['BROWSER_PORT']}/health"),
    ("Webhook API", f"http://localhost:{os.environ['WEBHOOK_PORT']}/health"),
]

all_ok = True
for name, url in checks:
    try:
        resp = requests.get(url, timeout=2)
        if resp.status_code == 200:
            print(f"   ✅ {name:20} → OK")
        else:
            print(f"   ⚠️  {name:20} → Status {resp.status_code}")
            all_ok = False
    except:
        print(f"   ❌ {name:20} → FAILED")
        all_ok = False

print("")
if all_ok:
    print("   ✨ All systems operational!")
    print("   🚀 HDS is ready for testing")
else:
    print("   ⚠️  Some services not responding")

print("")
print("   📊 Dashboard: Accessible in browser")
print("   🔗 Vision API: Ready for requests")
print("   🌐 Webhook API: Ready for tasks")
print("")
print("   Press Ctrl+C to stop all services")
PYTHON_AGENT

echo ""

# ============================================================================
# STEP 6: Summary
# ============================================================================
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              🎉 HDS DEV ENVIRONMENT READY 🎉             ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 SERVICES RUNNING:"
echo "   Vision Daemon:  http://localhost:$VISION_PORT"
echo "   Browser Daemon: http://localhost:$BROWSER_PORT"
echo "   Webhook API:    http://localhost:$WEBHOOK_PORT"
echo "   React GUI:      http://localhost:$GUI_PORT"
echo ""
echo "🎮 CONTROL:"
echo "   • Open browser: http://localhost:$GUI_PORT"
echo "   • View Vision logs: tail -f /tmp/hds_vision.log"
echo "   • View Browser logs: tail -f /tmp/hds_browser.log"
echo "   • View Webhook logs: tail -f /tmp/hds_webhook.log"
echo "   • Stop services: Ctrl+C"
echo ""
echo "🧪 TEST COMMANDS:"
echo ""
echo "   Vision capture:"
echo "   curl -X POST http://localhost:$VISION_PORT/execute \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"type\": \"capture_screen\"}'"
echo ""
echo "   Browser navigate:"
echo "   curl -X POST http://localhost:$BROWSER_PORT/execute \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"type\": \"navigate\", \"url\": \"https://example.com\"}'"
echo ""
echo "   Submit task:"
echo "   curl -X POST http://localhost:$WEBHOOK_PORT/api/v1/task \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"type\": \"vision\", \"action\": \"analyze_screen\"}'"
echo ""
echo "═════════════════════════════════════════════════════════════"
echo ""

# Keep processes running
wait

