@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title SnapTranscript
color 0a
cls

cd /d "%~dp0"

echo [INFO] Starting SnapTranscript...
echo.

:: ======================================
:: [1/3] Check Python
:: ======================================
echo [1/3] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Python not found. Python is required to run this tool.
    echo.
    set /p INSTALL_PY=Install Python now? [Y/n] - Press Enter to agree:
    if "!INSTALL_PY!"=="" set INSTALL_PY=Y
    if /i "!INSTALL_PY!" neq "Y" ( echo Cancelled. & pause & exit /b 1 )
    winget --version >nul 2>&1
    if !errorlevel! equ 0 (
        echo [INFO] Installing Python via winget, please wait...
        winget install --id Python.Python.3 -e --silent --accept-source-agreements --accept-package-agreements
    ) else (
        echo [ERROR] winget not found. Please install Python manually: https://www.python.org/
        pause & exit /b 1
    )
    for /f "tokens=*" %%i in ('powershell -NoProfile -Command "[System.Environment]::GetEnvironmentVariable(\"PATH\",\"Machine\")"') do set "PATH=%%i;%PATH%"
    python --version >nul 2>&1
    if !errorlevel! neq 0 ( echo [INFO] Done! Please close and double-click the bat again. & pause & exit /b 0 )
    echo [OK] Python installation complete.
) else (
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo [OK] %%v is installed.
)

:: ======================================
:: [2/3] Check uv
:: ======================================
echo [2/3] Checking uv...
uv --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [WARNING] uv not found. Installing...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    for /f "tokens=*" %%i in ('powershell -NoProfile -Command "[System.Environment]::GetEnvironmentVariable(\"PATH\",\"User\")"') do set "PATH=%%i;%PATH%"
    uv --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo [ERROR] uv install failed. Please close and double-click the bat again.
        pause
        exit /b 1
    )
    echo [OK] uv installed.
) else (
    for /f "tokens=*" %%v in ('uv --version') do echo [OK] %%v is installed.
)

:: ======================================
:: [3/3] Check virtual environment
:: ======================================
echo [3/3] Checking virtual environment...
if not exist venv (
    echo [WARNING] Virtual environment not found.
    set /p CONFIRM=Create venv and install packages now? [Y/n] - Press Enter to agree:
    if "!CONFIRM!"=="" set CONFIRM=Y
    if /i "!CONFIRM!" neq "Y" ( echo Cancelled. Run uv venv venv manually then restart. & pause & exit /b 1 )
    echo [INFO] Creating virtual environment...
    uv venv venv
    echo [INFO] Installing packages...
    uv pip install -r requirements.txt --python venv\Scripts\python.exe
    if !errorlevel! neq 0 (
        echo [ERROR] Package installation failed. Check your network and retry.
        pause & exit /b 1
    )
    echo [OK] Packages installed.
) else (
    echo [OK] Virtual environment ready.
)
call venv\Scripts\activate

echo.
echo [START] Launching... keep this window open.
echo.

python main.py
set EXIT_CODE=%errorlevel%

if exist __pycache__ rmdir /s /q __pycache__

if %EXIT_CODE% neq 0 (
    echo.
    echo [ERROR] Program stopped unexpectedly. Please report the error above.
    pause
) else (
    echo.
    echo Closing in 5 seconds...
    timeout /t 5
)
