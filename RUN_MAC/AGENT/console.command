#!/usr/bin/env bash
# Live console: plan, pipeline control, dialogue (port 8114)
# HDS OS launcher — runs from the project root regardless of where
# it is double-clicked.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PATH="$HOME/.local/bin:$PATH"
echo "── console: Live console: plan, pipeline control, dialogue (port 8114)"
HDS_CONSOLE_PORT=8114 python3 console_server.py
echo
read -n 1 -s -r -p "Натисни будь-яку клавішу, щоб закрити..."
