@echo off
rem The public site, 5 languages (port 8231)
rem HDS OS launcher - runs from the project root.
cd /d "%~dp0..\.."
echo -- site: The public site, 5 languages (port 8231)
cd storage\site && python -m http.server 8231
pause
