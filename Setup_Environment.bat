@echo off
title VORTEX Suite — Automated Environment Setup
color 0b
cd /d "%~dp0"

echo =====================================================================
echo           VORTEX SUITE -- AUTOMATED 1-CLICK ENVIRONMENT SETUP
echo =====================================================================
echo.

:: 1. Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0c
    echo [!] ERROR: Python is not installed or not in your Windows PATH!
    echo.
    echo Please install Python 3.10+ from https://www.python.org/
    echo IMPORTANT: Make sure to check the box "Add python.exe to PATH" during install.
    echo.
    pause
    exit /b 1
)

echo [*] Python detected:
python --version
echo.

:: 2. Upgrade pip
echo [*] Step 1/4: Checking and upgrading pip...
python -m pip install --upgrade pip --quiet

:: 3. Install Requirements
echo [*] Step 2/4: Installing core libraries (Playwright, Requests, ZXing-CPP, Pillow, ixBrowser API)...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    color 0c
    echo [!] Warning: Some dependencies had issues installing. Retrying...
    python -m pip install requests playwright zxing-cpp pillow ixbrowser-local-api
)

:: 4. Install Playwright Chromium Browser
echo.
echo [*] Step 3/4: Downloading isolated Chromium automation browser for Playwright...
python -m playwright install chromium

:: 5. Initialize Vault Database
echo.
echo [*] Step 4/4: Initializing SQLite Vault and WAL Mode...
python -c "from core import database; database.init_db(); print('Database schema and WAL initialized successfully!')"

echo.
color 0a
echo =====================================================================
echo   [SUCCESS] VORTEX SUITE ENVIRONMENT IS 100%% READY ON THIS PC!
echo =====================================================================
echo.
echo You can now run the software at any time by double-clicking:
echo   --> Launch_Suite.bat
echo.
pause
