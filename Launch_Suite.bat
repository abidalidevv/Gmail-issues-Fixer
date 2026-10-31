@echo off
title VORTEX Identity Orchestrator & Recovery Suite
color 0b
cd /d "%~dp0"

echo =====================================================================
echo           VORTEX IDENTITY ORCHESTRATOR & RECOVERY SUITE
echo =====================================================================
echo.

:: 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0c
    echo [!] ERROR: Python is not detected in your PATH!
    echo Please install Python 3.10+ and check "Add python.exe to PATH".
    echo Or double-click "Setup_Environment.bat" first.
    echo.
    pause
    exit /b 1
)

:: 2. Quick dependency check
python -c "import requests, playwright, zxingcpp, PIL" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] First time running on this machine? Missing some libraries.
    echo [*] Running automated environment setup...
    call Setup_Environment.bat
)

echo [*] Launching VORTEX Local Web Server on port 8765...
echo [*] Live Dashboard URL: http://127.0.0.1:8765
echo [*] Press Ctrl+C in this terminal window to stop the server.
echo.

python app.py

pause
