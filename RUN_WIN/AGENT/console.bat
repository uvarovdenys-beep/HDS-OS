@echo off
rem Live console: plan, pipeline control, dialogue (port 8114)
rem HDS OS launcher - runs from the project root.
cd /d "%~dp0..\.."
echo -- console: Live console: plan, pipeline control, dialogue (port 8114)
set HDS_CONSOLE_PORT=8114
python console_server.py
pause
