#!/usr/bin/env bash
# Quality history across releases: record or show
# HDS OS launcher — runs from the project root regardless of where
# it is double-clicked.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PATH="$HOME/.local/bin:$PATH"
echo "── history: quality across releases"
python3 hds_snapshot.py
echo
read -n 1 -s -r -p "Натисни будь-яку клавішу, щоб закрити..."
