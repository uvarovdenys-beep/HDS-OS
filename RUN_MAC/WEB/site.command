#!/usr/bin/env bash
# The public site, 5 languages (port 8231)
# HDS OS launcher — runs from the project root regardless of where
# it is double-clicked.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PATH="$HOME/.local/bin:$PATH"
echo "── site: The public site, 5 languages (port 8231)"
cd storage/site && python3 -m http.server 8231
echo
read -n 1 -s -r -p "Натисни будь-яку клавішу, щоб закрити..."
