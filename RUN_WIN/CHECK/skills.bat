@echo off
rem List the orchestrator skills and their triggers
rem HDS OS launcher - runs from the project root.
cd /d "%~dp0..\.."
echo -- skills: List the orchestrator skills and their triggers
python skills.py
pause
