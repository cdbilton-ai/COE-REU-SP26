@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo CFD Visualizer - Select Configuration
echo =====================================
echo 1. setup.json (OpenFOAM)
echo 2. setup_ansys.json (ANSYS)
echo 3. Custom file
echo.

set /p choice="Select option (1-3): "

if "%choice%"=="1" (
    set CONFIG_FILE=setup.json
) else if "%choice%"=="2" (
    set CONFIG_FILE=setup_ansys.json
) else if "%choice%"=="3" (
    set /p CONFIG_FILE="Enter full path to JSON file: "
) else (
    echo Invalid choice!
    pause
    exit /b 1
)

if not exist "%CONFIG_FILE%" (
    echo Error: File "%CONFIG_FILE%" not found!
    pause
    exit /b 1
)

echo.
echo Starting CFD Visualizer with: %CONFIG_FILE%
echo.
pvpython cfd_visualizer.py "%CONFIG_FILE%"

pause