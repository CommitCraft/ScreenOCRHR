@echo off
setlocal EnableExtensions
cd /d "%~dp0"

:: Python executable paths
set "PY_EXE="
set "PYW_EXE="

if exist "%~dp0venv\Scripts\pythonw.exe" (
    set "PYW_EXE=%~dp0venv\Scripts\pythonw.exe"
    set "PY_EXE=%~dp0venv\Scripts\python.exe"
) else if exist "C:\Program Files\Python314\pythonw.exe" (
    set "PYW_EXE=C:\Program Files\Python314\pythonw.exe"
    set "PY_EXE=C:\Program Files\Python314\python.exe"
) else (
    where pythonw >nul 2>&1 && set "PYW_EXE=pythonw"
    where python >nul 2>&1 && set "PY_EXE=python"
)
if "%PYW_EXE%"=="" set "PYW_EXE=pythonw"
if "%PY_EXE%"=="" set "PY_EXE=python"

:: If ROI is not set yet, ask to select area first
if not exist "%~dp0roi.json" (
    echo ============================================================
    echo First Time Setup: Please select the number area.
    echo Drag a box around the number and press ENTER or SPACE.
    echo ============================================================
    "%PY_EXE%" "%~dp0live_ocr.py" --select
)

:: Clear any stop signal
if exist "%~dp0stop.signal" del /f /q "%~dp0stop.signal" >nul 2>&1

:: Start a new local logging session with S.No 1.
> "%~dp0ocr_log.csv" echo S.No,Date,Time,Machine Name,Line,Detected Value,Previous Value,API Status

:: Stop any old OCR process to avoid duplicate running
taskkill /F /IM pythonw.exe >nul 2>&1
powershell -NoProfile -Command "Get-Process -Name pythonw -ErrorAction SilentlyContinue | Stop-Process -Force" >nul 2>&1

:: Start OCR silently in background
start "" "%PYW_EXE%" "%~dp0live_ocr.py"

:: Immediately close terminal so nothing stays visible
exit 0
