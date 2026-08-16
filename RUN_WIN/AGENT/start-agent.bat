@echo off
rem Start the HDS agent daemon (one instance only)
rem HDS OS launcher - runs from the project root.
cd /d "%~dp0..\.."
echo -- start-agent: Start the HDS agent daemon (one instance only)
taskkill /F /IM python.exe /FI "WINDOWTITLE eq hds-agent" >nul 2>&1
set HDS_SILENT=1
python agent\agent.py --monitor
pause
