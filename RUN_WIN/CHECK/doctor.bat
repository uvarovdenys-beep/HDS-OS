@echo off
rem Readiness: isolation, toolchains, models, free RAM
rem HDS OS launcher - runs from the project root.
cd /d "%~dp0..\.."
echo -- doctor: Readiness: isolation, toolchains, models, free RAM
python hds_doctor.py
pause
