@echo off
rem Generation quality, failure reasons and telemetry
rem HDS OS launcher - runs from the project root.
cd /d "%~dp0..\.."
echo -- stats: Generation quality, failure reasons and telemetry
python hds_stats.py
python hds_failures.py
python telemetry.py
pause
