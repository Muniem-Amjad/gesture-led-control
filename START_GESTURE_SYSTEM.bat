@echo off
title Gesture Control System Launcher
color 0A

echo ================================================
echo      GESTURE CONTROL SYSTEM - STARTING UP
echo ================================================
echo.

REM Navigate to project folder
cd /d "%~dp0"

REM Step 1: Open VS Code (settings.json will auto-start Wokwi)
echo [1/3] Opening VS Code + Wokwi Simulator...
start "" code .

REM Wait for VS Code and Wokwi to fully load
echo      Waiting for Wokwi to initialize (12 seconds)...
timeout /t 12 /nobreak >nul

REM Step 2: Start Flask app
echo [2/3] Starting Flask Dashboard...
start "Gesture Control - Flask" cmd /k "cd /d "%~dp0" && python app.py"
timeout /t 4 /nobreak >nul

REM Step 3: Open Chrome
echo [3/3] Opening Dashboard in Chrome...
start "" "chrome.exe" "http://localhost:5000"

echo.
echo ================================================
echo   System is ready!
echo   1. VS Code + Wokwi should be running
echo   2. Chrome opened at localhost:5000
echo   3. Click "Start System" in the dashboard
echo ================================================
echo.
pause