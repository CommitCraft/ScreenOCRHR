@echo off
setlocal EnableExtensions
cd /d "%~dp0"

:: Create stop signal file so OCR shuts down gracefully
type nul > "%~dp0stop.signal"

:: Terminate running Screen OCR processes
taskkill /F /IM pythonw.exe >nul 2>&1
powershell -NoProfile -Command "Get-Process -Name pythonw -ErrorAction SilentlyContinue | Stop-Process -Force" >nul 2>&1

:: Close terminal immediately
exit 0
