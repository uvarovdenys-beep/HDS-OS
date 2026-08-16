#!/usr/bin/env bash
# MCP server — connect Cursor / VS Code / Cline to HDS (14 tools)
# HDS OS launcher — runs from the project root regardless of where
# it is double-clicked.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PATH="$HOME/.local/bin:$PATH"
echo "── mcp-server: MCP server — connect Cursor / VS Code / Cline to HDS (14 tools)"
python3 mcp_server.py
echo
read -n 1 -s -r -p "Натисни будь-яку клавішу, щоб закрити..."
