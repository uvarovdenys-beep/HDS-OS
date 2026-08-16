@echo off
rem The agent interface: live plan rail + dialogue (port 8253)
rem HDS OS launcher - runs from the project root.
cd /d "%~dp0..\.."
echo -- agent-ui: The agent interface: live plan rail + dialogue (port 8253)
cd storage\mockup
python -m http.server 8253
pause
