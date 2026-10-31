@echo off
title VORTEX Suite — System Health & Diagnostics
color 0b
cd /d "%~dp0"

echo =====================================================================
echo           VORTEX SUITE -- SYSTEM HEALTH & DIAGNOSTICS AUDIT
echo =====================================================================
echo.

python -m core.diagnostics

echo.
pause
