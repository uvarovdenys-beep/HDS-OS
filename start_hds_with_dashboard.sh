#!/bin/bash
# HDS SMART Startup with Dashboard
# Launches vision daemon, browser daemon, webhook API + dashboard, and agent

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="monitor"
AUDIO_MODE="0"
AUTO_KILL="false"
AI_NAME="${DEPLOYING_AI:-hds_cli}"

while [[ $# -gt 0 ]]; do
    case $1 in
        --ai) AI_NAME="$2"; shift 2 ;;
        --monitor) MODE="monitor"; shift ;;
        --once) MODE="once"; shift ;;
        --auto-kill) AUTO_KILL="true"; shift ;;
        --audio) AUDIO_MODE="0"; shift ;;
        *) shift ;;
    esac
done

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║      HDS NUCLEUS + DASHBOARD STARTUP SEQUENCE            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Allocate ports
echo "Phase 1: Allocating Ports..."
ALLOCATION=$(cd "$BASE_DIR" && python3 -c "
import sys
sys.path.insert(0, 'agent')
from port_registry import PortRegistry
import json
config = PortRegistry.allocate_instance(
    deploying_ai='$AI_NAME',
    auto_kill=$( [ "$AUTO_KILL" = "true" ] && echo "True" || echo "False")
)
print(json.dumps(config))
")

export VISION_PORT=$(echo "$ALLOCATION" | python3 -c "import sys, json; print(json.load(sys.stdin)['vision_daemon_port'])")
export BROWSER_PORT=$(echo "$ALLOCATION" | python3 -c "import sys, json; print(json.load(sys.stdin)['browser_daemon_port'])")
export WEBHOOK_PORT=$(echo "$ALLOCATION" | python3 -c "import sys, json; print(json.load(sys.stdin)['webhook_port'])")

echo "✅ Ports allocated:"
echo "   Vision:   $VISION_PORT"
echo "   Browser:  $BROWSER_PORT"
echo "   Webhook:  $WEBHOOK_PORT"
echo ""

# Start daemons
echo "Phase 2: Starting Microkernel Daemons..."
cd "$BASE_DIR"

VISION_PORT=$VISION_PORT python3 agent/vision_daemon.py > /tmp/hds_vision.log 2>&1 &
VISION_PID=$!
echo "   🔄 Vision Daemon (PID: $VISION_PID)"

BROWSER_PORT=$BROWSER_PORT python3 agent/browser_daemon.py > /tmp/hds_browser.log 2>&1 &
BROWSER_PID=$!
echo "   🔄 Browser Daemon (PID: $BROWSER_PID)"

WEBHOOK_PORT=$WEBHOOK_PORT python3 agent/webhook_server_enhanced.py > /tmp/hds_webhook.log 2>&1 &
WEBHOOK_PID=$!
echo "   🔄 Webhook Server + Dashboard (PID: $WEBHOOK_PID)"
echo ""

# Wait for daemons
sleep 2

# Start agent
echo "Phase 3: Starting HDS Agent Nucleus..."
export HDS_SILENT=$AUDIO_MODE

python3 << 'PYTHON'
import sys
import os
sys.path.insert(0, 'agent')
from agent import HDS6Agent

os.environ['VISION_PORT'] = os.environ['VISION_PORT']
os.environ['BROWSER_PORT'] = os.environ['BROWSER_PORT']
os.environ['WEBHOOK_PORT'] = os.environ['WEBHOOK_PORT']

agent = HDS6Agent()
if os.environ.get('MODE', 'monitor') == 'monitor':
    agent.monitor()
else:
    agent.run()
PYTHON

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║            HDS SHUTDOWN COMPLETE                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Dashboard was available at:"
echo "   http://localhost:$WEBHOOK_PORT"
echo ""
EOF

chmod +x start_hds_with_dashboard.sh
echo "✅ Created: start_hds_with_dashboard.sh"
