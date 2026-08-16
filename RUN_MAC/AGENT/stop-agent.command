#!/usr/bin/env bash
# Stop the agent daemon and unload models
# HDS OS launcher — runs from the project root regardless of where
# it is double-clicked.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PATH="$HOME/.local/bin:$PATH"
echo "── stop-agent: Stop the agent daemon and unload models"
pkill -f "agent/agent.py" && echo "agent stopped" || echo "no agent running"
echo
read -n 1 -s -r -p "Натисни будь-яку клавішу, щоб закрити..."
