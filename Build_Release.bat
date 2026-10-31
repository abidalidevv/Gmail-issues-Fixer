@echo off
title VORTEX Suite — Build Portable Release
color 0b
cd /d "%~dp0"

echo =====================================================================
echo           VORTEX SUITE -- BUILD PORTABLE RELEASE PACKAGE
echo =====================================================================
echo.

python build_release.py

echo.
pause

