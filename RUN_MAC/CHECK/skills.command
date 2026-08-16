#!/usr/bin/env bash
# List the orchestrator skills and their triggers
# HDS OS launcher — runs from the project root regardless of where
# it is double-clicked.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PATH="$HOME/.local/bin:$PATH"
echo "── skills: List the orchestrator skills and their triggers"
python3 skills.py
echo
read -n 1 -s -r -p "Натисни будь-яку клавішу, щоб закрити..."
