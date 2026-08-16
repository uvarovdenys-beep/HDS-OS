@echo off
rem Stop the agent daemon and unload models
rem HDS OS launcher - runs from the project root.
cd /d "%~dp0..\.."
echo -- stop-agent: Stop the agent daemon and unload models
taskkill /F /IM python.exe /FI "WINDOWTITLE eq hds-agent" >nul 2>&1
echo agent stopped
pause
