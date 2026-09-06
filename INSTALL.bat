@echo off
setlocal EnableExtensions
title APLOS Screen OCR - Complete Automatic Installer
color 0A

echo ============================================================
echo.
echo        APLOS SCREEN OCR - FULL AUTO INSTALLER
echo.
echo ============================================================
echo.
echo This installer will automatically setup:
echo.
echo   [1] Python
echo   [2] pip
echo   [3] OpenCV
echo   [4] MSS
echo   [5] NumPy
echo   [6] PyTesseract
echo   [7] Requests
echo   [8] Pillow
echo   [9] Tesseract OCR
echo  [10] Screen OCR files
echo  [11] Saved ROI
echo  [12] Silent Windows Auto Start
echo.
echo ============================================================
echo.


REM ============================================================
REM ADMINISTRATOR CHECK
REM ============================================================

net session >nul 2>&1

if %errorlevel% neq 0 (
    echo Administrator permission required...
    echo.
    powershell -NoProfile -Command ^
    "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)


REM ============================================================
REM VARIABLES
REM ============================================================

set "INSTALL_DIR=C:\ScreenOCR"
set "SOURCE_DIR=%~dp0"
set "PY_INSTALLER=%TEMP%\python_screenocr.exe"

echo Source:
echo %SOURCE_DIR%

echo.
echo Install:
echo %INSTALL_DIR%
echo.


REM ============================================================
REM CHECK REQUIRED SOURCE FILES
REM ============================================================

echo ============================================================
echo Checking installation files...
echo ============================================================

if not exist "%SOURCE_DIR%live_ocr.py" (
    echo.
    echo ERROR:
    echo live_ocr.py not found.
    echo.
    echo Keep these files together:
    echo.
    echo INSTALL.bat
    echo live_ocr.py
    echo roi.json
    echo.
    pause
    exit /b 1
)

if not exist "%SOURCE_DIR%roi.json" (
    echo.
    echo ERROR:
    echo roi.json not found.
    echo.
    pause
    exit /b 1
)

echo Files OK.
echo.


REM ============================================================
REM CREATE INSTALLATION DIRECTORY
REM ============================================================

echo ============================================================
echo [1/9] Creating ScreenOCR directory...
echo ============================================================

if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
)

if /i not "%SOURCE_DIR%"=="%INSTALL_DIR%\" if /i not "%SOURCE_DIR%"=="%INSTALL_DIR%" (
    copy /Y "%SOURCE_DIR%live_ocr.py" "%INSTALL_DIR%\live_ocr.py" >nul
    copy /Y "%SOURCE_DIR%roi.json" "%INSTALL_DIR%\roi.json" >nul

    if exist "%SOURCE_DIR%.env.example" (
        copy /Y "%SOURCE_DIR%.env.example" "%INSTALL_DIR%\.env.example" >nul
    )

    if exist "%SOURCE_DIR%.env" (
        if not exist "%INSTALL_DIR%\.env" (
            copy /Y "%SOURCE_DIR%.env" "%INSTALL_DIR%\.env" >nul
        )
    )
)

echo.
echo Files copied successfully (.env, live_ocr.py, roi.json).
echo.


REM ============================================================
REM CHECK PYTHON
REM ============================================================

echo ============================================================
echo [2/9] Checking Python...
echo ============================================================

where py >nul 2>&1

if %errorlevel% equ 0 (
    echo Python Launcher already installed.
    goto PYTHON_READY
)

where python >nul 2>&1

if %errorlevel% equ 0 (
    echo Python already installed.
    goto PYTHON_READY
)

echo.
echo Python not found.
echo Downloading Python...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.13.7/python-3.13.7-amd64.exe' -OutFile '%PY_INSTALLER%'"

if not exist "%PY_INSTALLER%" (
    echo.
    echo ERROR: Python download failed.
    echo Check internet connection.
    echo.
    pause
    exit /b 1
)

echo.
echo Installing Python...
echo.

"%PY_INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1 Include_launcher=1 Include_test=0

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Python installation failed.
    pause
    exit /b 1
)

echo.
echo Python installation completed.
echo.

timeout /t 10 /nobreak >nul


REM ============================================================
REM REFRESH PATH
REM ============================================================

set "PATH=C:\Program Files\Python313;C:\Program Files\Python313\Scripts;%PATH%"


:PYTHON_READY

echo.
echo Python ready.
echo.


REM ============================================================
REM FIND PYTHON COMMAND
REM ============================================================

where py >nul 2>&1

if %errorlevel% equ 0 (
    set "PYCMD=py"
) else (
    set "PYCMD=python"
)

echo Python command:
echo %PYCMD%

echo.


REM ============================================================
REM TEST PYTHON
REM ============================================================

%PYCMD% --version

if %errorlevel% neq 0 (
    echo.
    echo ERROR:
    echo Python is installed but could not be started.
    echo.
    echo Restart Windows and run INSTALL.bat again.
    echo.
    pause
    exit /b 1
)


REM ============================================================
REM SETUP PIP
REM ============================================================

echo.
echo ============================================================
echo [3/9] Setting up PIP...
echo ============================================================

%PYCMD% -m ensurepip --upgrade

%PYCMD% -m pip install --upgrade pip

if %errorlevel% neq 0 (
    echo.
    echo ERROR: pip installation failed.
    pause
    exit /b 1
)

echo.
echo PIP ready.
echo.


REM ============================================================
REM INSTALL PYTHON PACKAGES
REM ============================================================

echo.
echo ============================================================
echo [4/9] Installing Python OCR packages...
echo ============================================================
echo.
echo Please wait...
echo.

%PYCMD% -m pip install ^
opencv-python ^
mss ^
numpy ^
pytesseract ^
requests ^
pillow

if %errorlevel% neq 0 (
    echo.
    echo ERROR:
    echo Python package installation failed.
    echo.
    echo Check internet connection.
    echo.
    pause
    exit /b 1
)

echo.
echo Python OCR packages installed.
echo.


REM ============================================================
REM TEST PYTHON MODULES
REM ============================================================

echo.
echo ============================================================
echo [5/9] Testing Python modules...
echo ============================================================

%PYCMD% -c "import cv2,mss,numpy,pytesseract,requests,PIL; print('ALL PYTHON MODULES OK')"

if %errorlevel% neq 0 (
    echo.
    echo ERROR:
    echo Python module test failed.
    echo.
    pause
    exit /b 1
)

echo.
echo All Python modules OK.
echo.


REM ============================================================
REM TESSERACT CHECK
REM ============================================================

echo.
echo ============================================================
echo [6/9] Checking Tesseract OCR...
echo ============================================================

if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    echo Tesseract already installed.
    goto TESSERACT_READY
)

if exist "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe" (
    echo Tesseract already installed.
    goto TESSERACT_READY
)

where tesseract >nul 2>&1

if %errorlevel% equ 0 (
    echo Tesseract already available.
    goto TESSERACT_READY
)


REM ============================================================
REM INSTALL TESSERACT USING WINGET
REM ============================================================

echo.
echo Tesseract not found.
echo Installing Tesseract OCR...
echo.

where winget >nul 2>&1

if %errorlevel% neq 0 (
    echo.
    echo ERROR:
    echo Winget not available on this Windows PC.
    echo.
    echo Python has been installed successfully,
    echo but Tesseract could not be installed automatically.
    echo.
    pause
    exit /b 1
)

winget install ^
--id UB-Mannheim.TesseractOCR ^
-e ^
--silent ^
--accept-package-agreements ^
--accept-source-agreements

timeout /t 5 /nobreak >nul


:TESSERACT_READY

echo.
echo Checking Tesseract...

if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    echo Tesseract OK.
    goto FIND_PYTHONW
)

if exist "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe" (
    echo Tesseract OK.
    goto FIND_PYTHONW
)

where tesseract >nul 2>&1

if %errorlevel% neq 0 (
    echo.
    echo ERROR:
    echo Tesseract installation was not detected.
    echo.
    pause
    exit /b 1
)


REM ============================================================
REM FIND PYTHONW
REM ============================================================

:FIND_PYTHONW

echo.
echo ============================================================
echo [7/9] Configuring silent background mode...
echo ============================================================

for /f "delims=" %%i in ('%PYCMD% -c "import sys,os; print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))"') do (
    set "PYTHONW=%%i"
)

echo PythonW:
echo %PYTHONW%

if not exist "%PYTHONW%" (
    echo.
    echo ERROR:
    echo pythonw.exe not found.
    echo.
    pause
    exit /b 1
)


REM ============================================================
REM CREATE SILENT VBS LAUNCHER
REM ============================================================

echo.
echo Creating silent launcher...

(
echo Set WshShell = CreateObject^("WScript.Shell"^)
echo WScript.Sleep 15000
echo WshShell.CurrentDirectory = "%INSTALL_DIR%"
echo WshShell.Run """%PYTHONW%"" ""%INSTALL_DIR%\live_ocr.py""", 0, False
) > "%INSTALL_DIR%\start_ocr_hidden.vbs"


REM ============================================================
REM WINDOWS STARTUP
REM ============================================================

echo.
echo ============================================================
echo [8/9] Configuring Windows Auto Start...
echo ============================================================

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

if exist "%STARTUP%\ScreenOCR_AutoStart.bat" (
    del /F /Q "%STARTUP%\ScreenOCR_AutoStart.bat"
)

if exist "%STARTUP%\ScreenOCR_AutoStart.vbs" (
    del /F /Q "%STARTUP%\ScreenOCR_AutoStart.vbs"
)

copy /Y ^
"%INSTALL_DIR%\start_ocr_hidden.vbs" ^
"%STARTUP%\ScreenOCR_AutoStart.vbs" >nul

if %errorlevel% neq 0 (
    echo.
    echo ERROR:
    echo Could not configure Windows Startup.
    echo.
    pause
    exit /b 1
)

echo.
echo Windows Auto Start configured.
echo.


REM ============================================================
REM FINAL FILE CHECK
REM ============================================================

echo.
echo ============================================================
echo [9/9] Final system check...
echo ============================================================

if not exist "%INSTALL_DIR%\live_ocr.py" (
    echo ERROR: live_ocr.py missing.
    pause
    exit /b 1
)

if not exist "%INSTALL_DIR%\roi.json" (
    echo ERROR: roi.json missing.
    pause
    exit /b 1
)

if not exist "%INSTALL_DIR%\start_ocr_hidden.vbs" (
    echo ERROR: startup launcher missing.
    pause
    exit /b 1
)

echo.
echo Final check OK.


REM ============================================================
REM START OCR NOW
REM ============================================================

echo.
echo Starting Screen OCR...

start "" wscript.exe "%INSTALL_DIR%\start_ocr_hidden.vbs"


REM ============================================================
REM CLEANUP
REM ============================================================

if exist "%PY_INSTALLER%" (
    del /F /Q "%PY_INSTALLER%" >nul 2>&1
)


REM ============================================================
REM COMPLETE
REM ============================================================

echo.
echo.
echo ============================================================
echo.
echo          APLOS SCREEN OCR INSTALLATION COMPLETE
echo.
echo ============================================================
echo.
echo Installation Folder:
echo.
echo     C:\ScreenOCR
echo.
echo Installed:
echo.
echo     Python
echo     PIP
echo     OpenCV
echo     MSS
echo     NumPy
echo     PyTesseract
echo     Requests
echo     Pillow
echo     Tesseract OCR
echo     Live OCR
echo     Saved ROI
echo     Silent Auto Start
echo.
echo ------------------------------------------------------------
echo.
echo OCR will automatically start after Windows Login.
echo.
echo NO CMD POPUP
echo NO OCR PREVIEW
echo NO ROI SELECTION
echo.
echo Node-RED API:
echo.
echo     http://0.0.0.0:1880/api/screen-ocr
echo.
echo Node-RED can listen on:
echo.
echo     0.0.0.0:1880
echo.
echo ============================================================
echo.
echo You can now restart the PC.
echo.
pause

exit /b 0