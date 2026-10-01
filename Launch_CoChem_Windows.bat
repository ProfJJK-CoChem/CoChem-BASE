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
wsl -e bash -c "python3 -m venv ~/.cochem_venv || (sudo apt-get update && sudo apt-get install -y python3-venv && python3 -m venv ~/.cochem_venv); source ~/.cochem_venv/bin/activate; cd \"$(wslpath '%CD%')\"; pip install --upgrade pip; pip install pydantic ipywidgets voila numpy scipy ase h5py traitlets filelock psutil requests pynacl mendeleev; echo ''; echo 'WSL Backend Ready! Please open the following URL in your Windows browser:'; voila Start_Here.ipynb --no-browser"
pause
exit

:win_launch
echo.
echo Launching Native Windows Environment...
voila Start_Here.ipynb --enable_nbextensions=True
pause
exit
