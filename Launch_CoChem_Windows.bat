@echo off
title CoChem Base Launcher
echo ========================================================
echo CoChem Execution Environment Selector
echo ========================================================
echo.

:: Detect WSL
wsl -l -q >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Windows Subsystem for Linux (WSL2) is NOT detected!
    echo Heavy Quantum Chemistry calculations (ORCA/CFOUR) require massive stack
    echo memory and high-speed POSIX file I/O (HDF5). Native Windows will
    echo operate in a safe DEGRADED mode.
    echo.
    echo To install WSL2 for maximum performance, open PowerShell as Admin and run:
    echo     wsl --install
    echo.
    echo [1] Launch using Native Windows (DEGRADED mode)
    echo [2] Abort and exit
    echo.
    set /p choice="Enter choice (1 or 2): "
    if "%choice%"=="1" goto win_launch
    exit
) else (
    echo We have detected you are on Windows, and WSL2 is available.
    echo Because heavy Quantum Chemistry calculations require massive stack memory
    echo (ulimit) and high-speed POSIX I/O, native Windows operates in a safe
    echo DEGRADED mode.
    echo.
    echo For maximum performance on this workstation, we strongly
    echo recommend routing the backend through your WSL2 instance.
    echo.
    echo [1] Launch using Native Windows (DEGRADED mode)
    echo [2] Setup and Launch via WSL2 (OPTIMAL mode - RECOMMENDED)
    echo.
    set /p choice="Enter choice (1 or 2): "
    if "%choice%"=="2" goto wsl_launch
    goto win_launch
)

:wsl_launch
echo.
echo Initializing Windows Subsystem for Linux (WSL2)...
echo If this is your first time, WSL will install the necessary isolated Python packages.
wsl -e bash -lc "cd \"$(wslpath '%CD%')\" && python3 scripts/bootstrap_environment.py --venv ~/.cochem_venv --launch --no-browser"
pause
exit

:win_launch
echo.
echo Launching Native Windows Environment...
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3 scripts\bootstrap_environment.py --launch
) else (
    python scripts\bootstrap_environment.py --launch
)
pause
exit
