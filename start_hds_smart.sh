#!/bin/bash
# start_hds_smart.sh
# HDS SMART Startup with Dynamic Port Allocation & Health Checks
# Smart startup with automatic port allocation and health verification

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ============================================================================
# PARSE ARGUMENTS
# ============================================================================

MODE="monitor"  # Default: monitor (continuous)
AUDIO_MODE="0"  # Default: silent
AUTO_KILL="false"
AI_NAME="${DEPLOYING_AI:-hds_cli}"
HELP=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --monitor)
            MODE="monitor"
            shift
            ;;
        --once)
            MODE="once"
            shift
            ;;
        --audio)
            AUDIO_MODE="0"  # Audio enabled
            shift
            ;;
        --silent)
            AUDIO_MODE="1"  # Audio disabled
            shift
            ;;
        --auto-kill)
            AUTO_KILL="true"
            shift
            ;;
        --ai)
            AI_NAME="$2"
            shift 2
            ;;
        --vision-port)
            export VISION_PORT="$2"
            shift 2
            ;;
        --browser-port)
            export BROWSER_PORT="$2"
            shift 2
            ;;
        --webhook-port)
            export WEBHOOK_PORT="$2"
            shift 2
            ;;
        --help|-h)
            HELP=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            HELP=true
            shift
            ;;
    esac
done

if [ "$HELP" = true ]; then
    cat << 'EOF'
HDS SMART Startup - Dynamic Port Allocation & Health Checks

Usage:
  bash start_hds_smart.sh [options]

Options:
  --monitor           Run in continuous mode (default)
  --once              Run single cycle and exit
  --audio             Enable audio notifications (default: silent)
  --silent            Disable audio notifications
  --auto-kill         Kill conflicting processes on startup
  --ai <name>         Set deploying AI name (default: hds_cli)

  Port Override (use if you want specific ports):
  --vision-port <port>    Vision daemon port (auto-allocated by default)
  --browser-port <port>   Browser daemon port (auto-allocated by default)
  --webhook-port <port>   Webhook API port (auto-allocated by default)

Examples:
  # Default: silent, continuous, auto-allocated ports
  bash start_hds_smart.sh

  # With audio, single cycle, for GPT-4
  bash start_hds_smart.sh --audio --once --ai "GPT-4"

  # Kill conflicting processes automatically
  bash start_hds_smart.sh --auto-kill

  # Use specific ports
  bash start_hds_smart.sh --vision-port 9001 --browser-port 9002 --webhook-port 8080

EOF
    exit 0
fi

# ============================================================================
# ALLOCATE PORTS (if not explicitly provided)
# ============================================================================

if [ -z "$VISION_PORT" ] || [ -z "$BROWSER_PORT" ] || [ -z "$WEBHOOK_PORT" ]; then
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║     HDS SMART STARTUP - ALLOCATING UNIQUE PORTS           ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    AUTO_KILL_FLAG=""
    [ "$AUTO_KILL" = "true" ] && AUTO_KILL_FLAG="--auto-kill"

    # Call Python script to allocate ports
    ALLOCATION=$(cd "$BASE_DIR" && python3 -c "
import sys
sys.path.insert(0, 'agent')
from port_registry import PortRegistry
import json

try:
    config = PortRegistry.allocate_instance(
        deploying_ai='$AI_NAME',
        auto_kill=$( [ "$AUTO_KILL" = "true" ] && echo "True" || echo "False")
    )
    print(json.dumps(config))
except SystemExit:
    sys.exit(1)
")

    if [ $? -ne 0 ]; then
        echo "❌ Failed to allocate ports"
        exit 1
    fi

    # Extract ports from JSON response
    export VISION_PORT=$(echo "$ALLOCATION" | python3 -c "import sys, json; print(json.load(sys.stdin)['vision_daemon_port'])")
    export BROWSER_PORT=$(echo "$ALLOCATION" | python3 -c "import sys, json; print(json.load(sys.stdin)['browser_daemon_port'])")
    export WEBHOOK_PORT=$(echo "$ALLOCATION" | python3 -c "import sys, json; print(json.load(sys.stdin)['webhook_port'])")
    INSTANCE_ID=$(echo "$ALLOCATION" | python3 -c "import sys, json; print(json.load(sys.stdin)['instance_id'])")
else
    echo "Using explicitly provided ports:"
    echo "  Vision:  $VISION_PORT"
    echo "  Browser: $BROWSER_PORT"
    echo "  Webhook: $WEBHOOK_PORT"
fi

# ============================================================================
# STARTUP PHASE
# ============================================================================

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║            HDS NUCLEUS STARTUP SEQUENCE                   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Instance Configuration:"
echo "  AI System:        $AI_NAME"
echo "  Mode:             $MODE"
echo "  Audio:            $([ "$AUDIO_MODE" = "0" ] && echo "ENABLED 🔊" || echo "DISABLED 🔇")"
echo ""
echo "Port Configuration:"
echo "  Vision Daemon:    http://localhost:$VISION_PORT"
echo "  Browser Daemon:   http://localhost:$BROWSER_PORT"
echo "  Webhook API:      http://localhost:$WEBHOOK_PORT"
echo ""

# ============================================================================
# CHECK & START DAEMONS
# ============================================================================

echo "Phase 1: Checking Microkernel Daemons..."
echo "─────────────────────────────────────────────────────────────"

# Vision Daemon
VISION_CHECK=$(curl -s http://localhost:$VISION_PORT/health 2>/dev/null || echo "")

if [ -z "$VISION_CHECK" ]; then
    echo "  🔄 Starting Vision Daemon on port $VISION_PORT..."
    cd "$BASE_DIR"
    VISION_PORT=$VISION_PORT python3 agent/vision_daemon.py > /tmp/hds_vision.log 2>&1 &
    VISION_PID=$!
    echo "    PID: $VISION_PID"

    # Wait for daemon to start
    echo "  ⏳ Waiting for Vision Daemon to be ready..."
    TIMEOUT=0
    while [ $TIMEOUT -lt 30 ]; do
        if curl -s http://localhost:$VISION_PORT/health > /dev/null 2>&1; then
            echo "    ✅ Vision Daemon ready"
            break
        fi
        sleep 1
        TIMEOUT=$((TIMEOUT + 1))
    done

    if [ $TIMEOUT -eq 30 ]; then
        echo "    ❌ Vision Daemon failed to start"
        exit 1
    fi
else
    echo "  ✅ Vision Daemon already running on port $VISION_PORT"
fi

# Browser Daemon
BROWSER_CHECK=$(curl -s http://localhost:$BROWSER_PORT/health 2>/dev/null || echo "")

if [ -z "$BROWSER_CHECK" ]; then
    echo "  🔄 Starting Browser Daemon on port $BROWSER_PORT..."
    cd "$BASE_DIR"
    BROWSER_PORT=$BROWSER_PORT python3 agent/browser_daemon.py > /tmp/hds_browser.log 2>&1 &
    BROWSER_PID=$!
    echo "    PID: $BROWSER_PID"

    # Wait for daemon to start
    echo "  ⏳ Waiting for Browser Daemon to be ready..."
    TIMEOUT=0
    while [ $TIMEOUT -lt 30 ]; do
        if curl -s http://localhost:$BROWSER_PORT/health > /dev/null 2>&1; then
            echo "    ✅ Browser Daemon ready"
            break
        fi
        sleep 1
        TIMEOUT=$((TIMEOUT + 1))
    done

    if [ $TIMEOUT -eq 30 ]; then
        echo "    ❌ Browser Daemon failed to start"
        exit 1
    fi
else
    echo "  ✅ Browser Daemon already running on port $BROWSER_PORT"
fi

echo ""

# ============================================================================
# START AGENT
# ============================================================================

echo "Phase 2: Starting HDS Agent Nucleus..."
echo "─────────────────────────────────────────────────────────────"
echo ""

cd "$BASE_DIR"

# Export all configuration
export VISION_PORT=$VISION_PORT
export BROWSER_PORT=$BROWSER_PORT
export WEBHOOK_PORT=$WEBHOOK_PORT
export HDS_SILENT=$AUDIO_MODE

# Run agent based on mode
if [ "$MODE" = "monitor" ]; then
    echo "Mode: MONITOR (continuous) - Agent will run indefinitely"
    echo "Press Ctrl+C to stop"
    echo ""
    python3 -c "
import sys
import os
sys.path.insert(0, 'agent')
from agent import HDS6Agent

os.environ['VISION_PORT'] = '$VISION_PORT'
os.environ['BROWSER_PORT'] = '$BROWSER_PORT'
os.environ['WEBHOOK_PORT'] = '$WEBHOOK_PORT'
os.environ['HDS_SILENT'] = '$AUDIO_MODE'

agent = HDS6Agent()
agent.monitor()
    "
elif [ "$MODE" = "once" ]; then
    echo "Mode: ONCE (single cycle) - Agent will run once and exit"
    echo ""
    python3 -c "
import sys
import os
sys.path.insert(0, 'agent')
from agent import HDS6Agent

os.environ['VISION_PORT'] = '$VISION_PORT'
os.environ['BROWSER_PORT'] = '$BROWSER_PORT'
os.environ['WEBHOOK_PORT'] = '$WEBHOOK_PORT'
os.environ['HDS_SILENT'] = '$AUDIO_MODE'

agent = HDS6Agent()
agent.run()
    "
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║            HDS SHUTDOWN COMPLETE                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
