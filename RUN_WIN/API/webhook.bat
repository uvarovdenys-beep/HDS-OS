@echo off
rem HTTP webhook API for external task submission (port 8110)
rem HDS OS launcher - runs from the project root.
cd /d "%~dp0..\.."
echo -- webhook: HTTP webhook API for external task submission (port 8110)
python agent\webhook_server_enhanced.py
pause
