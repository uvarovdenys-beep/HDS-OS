#!/usr/bin/env bash
# Start the HDS agent daemon (one instance only)
# HDS OS launcher — runs from the project root regardless of where
# it is double-clicked.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PATH="$HOME/.local/bin:$PATH"
echo "── start-agent: Start the HDS agent daemon (one instance only)"
pkill -f "agent/agent.py" 2>/dev/null; HDS_SILENT=1 python3 agent/agent.py --monitor
echo
read -n 1 -s -r -p "Натисни будь-яку клавішу, щоб закрити..."
