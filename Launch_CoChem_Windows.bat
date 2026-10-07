@echo off
setlocal
title CoChem Base Launcher
pushd "%~dp0"
if errorlevel 1 exit /b 1
set "COCHEM_LAUNCH_STATUS=0"
set "COCHEM_LAUNCH_CHECK=0"

if not "%~3"=="" goto usage_error
if /i "%~1"=="--help" goto help
if /i "%~1"=="--check" goto native_check
if /i "%~1"=="--native" goto native_options
if /i "%~1"=="--wsl" goto wsl_options
if not "%~1"=="" goto usage_error

echo ========================================================
echo CoChem interface environment
echo ========================================================
echo [1] Native Windows interface, including GitHub Actions jobs
echo [2] WSL2 interface and compatible Linux calculation engines
echo [3] Exit
choice /c 123 /n /m "Enter choice (1, 2 or 3): "
if errorlevel 3 goto finished
if errorlevel 2 goto wsl_launch
if errorlevel 1 goto native_launch
goto usage_error

:native_options
if "%~2"=="" goto native_launch
if /i "%~2"=="--check" goto native_check
goto usage_error

:wsl_options
if "%~2"=="" goto wsl_launch
if /i not "%~2"=="--check" goto usage_error
set "COCHEM_LAUNCH_CHECK=1"
goto wsl_launch

:native_check
if /i "%~1"=="--check" if not "%~2"=="" goto usage_error
set "COCHEM_LAUNCH_CHECK=1"

:native_launch
rem Prefer the tested Python 3.12 environment, then an available Python 3.
py -3.12 -c "import sys; sys.exit(sys.version_info[:2] != (3, 12))" >nul 2>&1
if not errorlevel 1 goto native_py312
python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 goto native_python
echo Python 3.11 or newer is required. Python 3.12 is the tested setup version.
set "COCHEM_LAUNCH_STATUS=1"
goto finished

:native_py312
if "%COCHEM_LAUNCH_CHECK%"=="1" goto check_py312
py -3.12 scripts\bootstrap_environment.py --launch
set "COCHEM_LAUNCH_STATUS=%ERRORLEVEL%"
goto finished

:native_python
if "%COCHEM_LAUNCH_CHECK%"=="1" goto check_python
python scripts\bootstrap_environment.py --launch
set "COCHEM_LAUNCH_STATUS=%ERRORLEVEL%"
goto finished

:check_py312
py -3.12 scripts\bootstrap_environment.py --help
set "COCHEM_LAUNCH_STATUS=%ERRORLEVEL%"
goto check_finished

:check_python
python scripts\bootstrap_environment.py --help
set "COCHEM_LAUNCH_STATUS=%ERRORLEVEL%"
goto check_finished

:wsl_launch
where wsl >nul 2>&1
if errorlevel 1 goto wsl_unavailable
rem --cd safely passes the Windows repository path, including spaces, to WSL.
if "%COCHEM_LAUNCH_CHECK%"=="1" goto check_wsl
wsl --cd "%CD%" --exec bash -c "exec python3 scripts/bootstrap_environment.py --venv ~/.cochem_venv --launch --no-browser"
set "COCHEM_LAUNCH_STATUS=%ERRORLEVEL%"
goto finished

:check_wsl
wsl --cd "%CD%" --exec python3 scripts/bootstrap_environment.py --help
set "COCHEM_LAUNCH_STATUS=%ERRORLEVEL%"
goto check_finished

:wsl_unavailable
echo WSL is unavailable. Install WSL2 or choose the native Windows interface.
set "COCHEM_LAUNCH_STATUS=1"
goto finished

:check_finished
if not "%COCHEM_LAUNCH_STATUS%"=="0" goto finished
echo Launcher prerequisites verified; GUI dependencies and chemistry were not tested.
goto finished

:help
if not "%~2"=="" goto usage_error
echo Usage: Launch_CoChem_Windows.bat [--native ^| --wsl] [--check]
echo        Launch_CoChem_Windows.bat --check
echo With no arguments, choose the interface environment interactively.
echo --check reads the real Python bootstrap help without installing or launching.
goto finished

:usage_error
echo Invalid launcher arguments. Use --help for supported options.
set "COCHEM_LAUNCH_STATUS=2"

:finished
popd
exit /b %COCHEM_LAUNCH_STATUS%
