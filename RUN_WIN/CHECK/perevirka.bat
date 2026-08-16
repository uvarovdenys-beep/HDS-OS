@echo off
rem Перевiрка стану HDS українською
cd /d "%~dp0..\.."
python hds_perevirka.py %*
pause
