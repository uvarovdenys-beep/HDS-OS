#!/usr/bin/env bash
# The agent interface: live plan rail + dialogue (port 8253)
# HDS OS launcher — runs from the project root regardless of where
# it is double-clicked.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PATH="$HOME/.local/bin:$PATH"
echo "── agent-ui: The agent interface: live plan rail + dialogue (port 8253)"
cd storage/mockup && python3 -m http.server 8253
echo
read -n 1 -s -r -p "Натисни будь-яку клавішу, щоб закрити..."
