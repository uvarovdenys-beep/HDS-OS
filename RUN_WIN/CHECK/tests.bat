@echo off
rem Full test suite plus the three structural audits
rem HDS OS launcher - runs from the project root.
cd /d "%~dp0..\.."
echo -- tests: Full test suite plus the three structural audits
python -m pytest tests\ -q
python write_path_audit.py
python exec_path_audit.py
python decompose_audit.py
python benchmark.py
pause
