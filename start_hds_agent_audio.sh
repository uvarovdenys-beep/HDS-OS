#!/bin/bash
# start_hds_agent_audio.sh
# HDS Agent Startup Script - WITH AUDIO
# Запускає основне ядро з усіма 6 модулями ЗІ ЗВУКОМ

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$BASE_DIR/agent"

echo "═══════════════════════════════════════════════════════════"
echo "  HDS NUCLEUS - WITH AUDIO (ENABLED)"
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
echo "🔊 Audio: ENABLED"
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
echo "Starting HDS Agent (WITH AUDIO)..."
echo "═══════════════════════════════════════════════════════════"
echo ""

cd "$BASE_DIR"

# Audio mode is default - no need to set HDS_SILENT
# HDS_SILENT is NOT set, so audio is ENABLED

# Запускаємо агент
if [ "$1" == "--monitor" ]; then
    echo "Mode: MONITOR (continuous) - WITH AUDIO"
    python3 -c "
import sys
sys.path.insert(0, 'agent')
from agent import HDS6Agent
agent = HDS6Agent()
agent.monitor()
    "
elif [ "$1" == "--once" ]; then
    echo "Mode: ONCE (single cycle) - WITH AUDIO"
    python3 -c "
import sys
sys.path.insert(0, 'agent')
from agent import HDS6Agent
agent = HDS6Agent()
agent.run()
    "
else
    echo "Mode: INTERACTIVE - WITH AUDIO"
    echo ""
    echo "Usage:"
    echo "  ./start_hds_agent_audio.sh --monitor   (continuous mode)"
    echo "  ./start_hds_agent_audio.sh --once      (single cycle)"
    echo ""
    python3 -c "
import sys
sys.path.insert(0, 'agent')
from agent import HDS6Agent
print('[HDS-AUDIO] Agent initialized. Type Ctrl+C to exit.')
agent = HDS6Agent()
agent.run()
    "
fi
