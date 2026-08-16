@echo off
rem MCP server — connect Cursor / VS Code / Cline to HDS (14 tools)
rem HDS OS launcher - runs from the project root.
cd /d "%~dp0..\.."
echo -- mcp-server: MCP server — connect Cursor / VS Code / Cline to HDS (14 tools)
python mcp_server.py
pause
