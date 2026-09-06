@echo off
setlocal EnableExtensions
cd /d "%~dp0"

:: Terminate running Screen OCR processes
taskkill /F /IM pythonw.exe >nul 2>&1
powershell -NoProfile -Command "Get-Process -Name pythonw -ErrorAction SilentlyContinue | Stop-Process -Force" >nul 2>&1

:: Close terminal immediately
exit 0
