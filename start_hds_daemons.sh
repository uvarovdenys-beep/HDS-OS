#!/bin/bash
# start_hds_daemons.sh
# HDS Microkernel Daemon Startup
# Launches Vision daemon, Browser daemon, and Webhook API server.

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$BASE_DIR/agent"
AI_NAME="${DEPLOYING_AI:-hds_cli}"

echo "═══════════════════════════════════════════════════════════"
echo "  HDS MICROKERNEL DAEMON STARTUP"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Allocate dynamic ports (no hardcoded defaults)
echo "Allocating ports..."
ALLOCATION=$(cd "$BASE_DIR" && python3 -c "
import sys; sys.path.insert(0, 'agent')
from port_registry import PortRegistry
import json
print(json.dumps(PortRegistry.allocate_instance(deploying_ai='$AI_NAME')))
")

VISION_PORT=$(echo "$ALLOCATION"  | python3 -c "import sys,json; print(json.load(sys.stdin)['vision_daemon_port'])")
BROWSER_PORT=$(echo "$ALLOCATION" | python3 -c "import sys,json; print(json.load(sys.stdin)['browser_daemon_port'])")
WEBHOOK_PORT=$(echo "$ALLOCATION" | python3 -c "import sys,json; print(json.load(sys.stdin)['webhook_port'])")

export VISION_PORT BROWSER_PORT WEBHOOK_PORT
echo "  Vision:  $VISION_PORT"
echo "  Browser: $BROWSER_PORT"
echo "  Webhook: $WEBHOOK_PORT"
echo ""

start_daemon() {
    local name=$1 port=$2 script=$3
    if netstat -tuln 2>/dev/null | grep -q ":$port "; then
        echo "⚠️  Port $port in use — $name already running"
        return
    fi
    echo "Starting $name on :$port ..."
    cd "$AGENT_DIR"
    PORT=$port python3 "$script" > /tmp/hds_${name,,}.log 2>&1 &
    local pid=$!
    echo "  PID: $pid"
    sleep 1
    if curl -s http://localhost:$port/health > /dev/null 2>&1; then
        echo "  ✅ $name ready"
    else
        echo "  ⚠️  $name health check pending (see /tmp/hds_${name,,}.log)"
    fi
    cd "$BASE_DIR"
}

echo "Component Status:"
echo "─────────────────────────────────────────────────────────"

start_daemon "Vision"  "$VISION_PORT"  "vision_daemon.py"
echo ""
start_daemon "Browser" "$BROWSER_PORT" "browser_daemon.py"
echo ""

# Webhook API — always started so external/server AI can connect
if netstat -tuln 2>/dev/null | grep -q ":$WEBHOOK_PORT "; then
    echo "⚠️  Webhook port $WEBHOOK_PORT in use — server likely running"
else
    echo "Starting Webhook API on :$WEBHOOK_PORT ..."
    cd "$BASE_DIR"
    WEBHOOK_PORT=$WEBHOOK_PORT python3 agent/webhook_server_enhanced.py > /tmp/hds_webhook.log 2>&1 &
    WEBHOOK_PID=$!
    echo "  PID: $WEBHOOK_PID"
    sleep 1
    if curl -s http://localhost:$WEBHOOK_PORT/health > /dev/null 2>&1; then
        echo "  ✅ Webhook API ready"
    else
        echo "  ⚠️  Webhook health check pending (see /tmp/hds_webhook.log)"
    fi
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "All daemons started."
echo ""
echo "  Vision:  http://localhost:$VISION_PORT"
echo "  Browser: http://localhost:$BROWSER_PORT"
echo "  Webhook: http://localhost:$WEBHOOK_PORT"
echo ""
echo "Logs: /tmp/hds_vision.log  /tmp/hds_browser.log  /tmp/hds_webhook.log"
echo "═══════════════════════════════════════════════════════════"
echo ""

wait
