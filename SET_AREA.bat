@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PY_EXE="
set "PYW_EXE="

if exist "%~dp0venv\Scripts\pythonw.exe" (
    set "PYW_EXE=%~dp0venv\Scripts\pythonw.exe"
    set "PY_EXE=%~dp0venv\Scripts\python.exe"
) else (
    where pythonw >nul 2>&1 && set "PYW_EXE=pythonw"
    where python >nul 2>&1 && set "PY_EXE=python"
)

:: Stop any currently running OCR
taskkill /F /IM pythonw.exe >nul 2>&1
powershell -NoProfile -Command "Get-Process -Name pythonw -ErrorAction SilentlyContinue | Stop-Process -Force" >nul 2>&1

:: Select area
"%PY_EXE%" "%~dp0live_ocr.py" --select

:: Start OCR silently in background with new area
start "" "%PYW_EXE%" "%~dp0live_ocr.py"

:: Close terminal immediately
exit 0
