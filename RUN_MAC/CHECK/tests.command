#!/usr/bin/env bash
# Full test suite plus the three structural audits
# HDS OS launcher — runs from the project root regardless of where
# it is double-clicked.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PATH="$HOME/.local/bin:$PATH"
echo "── tests: Full test suite plus the three structural audits"
python3 -m pytest tests/ -q | tail -1
python3 write_path_audit.py | tail -1
python3 exec_path_audit.py | tail -1
python3 decompose_audit.py | tail -1
python3 benchmark.py | tail -3
echo
read -n 1 -s -r -p "Натисни будь-яку клавішу, щоб закрити..."
