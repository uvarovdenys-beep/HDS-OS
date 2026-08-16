#!/usr/bin/env bash
# Generation quality, failure reasons and telemetry
# HDS OS launcher — runs from the project root regardless of where
# it is double-clicked.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PATH="$HOME/.local/bin:$PATH"
echo "── stats: Generation quality, failure reasons and telemetry"
python3 hds_stats.py
echo
python3 hds_failures.py
echo
python3 telemetry.py
echo
read -n 1 -s -r -p "Натисни будь-яку клавішу, щоб закрити..."
