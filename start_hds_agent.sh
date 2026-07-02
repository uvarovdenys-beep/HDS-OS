#!/bin/bash
# start_hds_agent.sh
# HDS Agent Startup Script
# Запускає основне ядро з усіма 6 модулями

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$BASE_DIR/agent"

echo "═══════════════════════════════════════════════════════════"
echo "  HDS NUCLEUS - FULL SYSTEM STARTUP"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Components:"
echo "  ✓ Knowledge Gatekeeper (TKT-004)"
echo "  ✓ AI Experience (TKT-005)"
echo "  ✓ AST Validator (TKT-003a)"
echo "  ✓ Token Wallet (TKT-003b)"
echo "  ✓ Fallback Model Chain (TKT-003c)"
echo "  ✓ Hibernation Daemon (TKT-003d)"
echo "  ✓ Microkernel IPC (TKT-006)"
echo ""

# Перевіряємо чи демони запущені
echo "Checking daemon status..."
if ! curl -s http://localhost:9001/health > /dev/null 2>&1; then
    echo "⚠️  Vision Daemon (9001) not running"
    echo "   → Run: python3 agent/vision_daemon.py 9001 &"
fi

if ! curl -s http://localhost:9002/health > /dev/null 2>&1; then
    echo "⚠️  Browser Daemon (9002) not running"
    echo "   → Run: python3 agent/browser_daemon.py 9002 &"
fi

echo ""
echo "Starting HDS Agent..."
echo "═══════════════════════════════════════════════════════════"
echo ""

cd "$BASE_DIR"

# Запускаємо агент
if [ "$1" == "--monitor" ]; then
    echo "Mode: MONITOR (continuous)"
    python3 -c "
import sys
sys.path.insert(0, 'agent')
from agent import HDSAgent
agent = HDSAgent()
agent.monitor()
    "
elif [ "$1" == "--once" ]; then
    echo "Mode: ONCE (single cycle)"
    python3 -c "
import sys
sys.path.insert(0, 'agent')
from agent import HDSAgent
agent = HDSAgent()
agent.run()
    "
else
    echo "Mode: INTERACTIVE"
    echo ""
    echo "Usage:"
    echo "  ./start_hds_agent.sh --monitor   (continuous mode)"
    echo "  ./start_hds_agent.sh --once      (single cycle)"
    echo ""
    python3 -c "
import sys
sys.path.insert(0, 'agent')
from agent import HDSAgent
print('[HDS] Agent initialized. Type Ctrl+C to exit.')
agent = HDSAgent()
agent.run()
    "
fi
