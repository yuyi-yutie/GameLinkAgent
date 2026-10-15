@echo off
rem GameLink Agent launcher.
rem
rem Runs `gla <command>` from the repository root without activating the venv.
rem On first use (no .venv yet) it creates the virtual environment and installs
rem the package automatically, so a fresh clone works out of the box.
rem
rem NOTE: messages are intentionally ASCII-only - cmd.exe decodes .cmd files with
rem the OEM code page, so non-ASCII text would garble on many systems.

setlocal EnableExtensions
cd /d "%~dp0"

set "VENV_PY=%~dp0.venv\Scripts\python.exe"

if not exist "%VENV_PY%" call :make_venv
if not exist "%VENV_PY%" exit /b 1

"%VENV_PY%" -c "import gamelink" >nul 2>nul
if errorlevel 1 call :install
"%VENV_PY%" -c "import gamelink" >nul 2>nul
if errorlevel 1 (
    echo [GameLink Agent] Setup did not complete; see the messages above.
    exit /b 1
)

if exist "%~dp0.venv\Scripts\gla.exe" (
    "%~dp0.venv\Scripts\gla.exe" %*
) else (
    "%VENV_PY%" -m gamelink %*
)
exit /b %errorlevel%


:make_venv
echo.
echo [GameLink Agent] First run: creating the virtual environment (.venv) ...
where python >nul 2>nul
if errorlevel 1 (
    echo [GameLink Agent] ERROR: python was not found on PATH.
    echo                   Install Python 3.10+ ^(tick "Add python.exe to PATH"^),
    echo                   then run gla again.
    exit /b 1
)
python -m venv "%~dp0.venv"
exit /b %errorlevel%


:install
echo [GameLink Agent] Installing dependencies ^(needs network, may take a minute^) ...
"%VENV_PY%" -m pip install --upgrade pip
"%VENV_PY%" -m pip install -e .
if errorlevel 1 (
    echo [GameLink Agent] ERROR: dependency installation failed.
    echo                   Run this manually and check the output:
    echo                       .venv\Scripts\python -m pip install -e .
    exit /b 1
)
echo [GameLink Agent] Setup complete.
exit /b 0
