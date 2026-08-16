@echo off
rem Quality history across releases
cd /d "%~dp0..\.."
echo -- history: quality across releases
python hds_snapshot.py
pause
