@echo off
rem GameLink Agent launcher.
rem
rem A fresh clone is runnable with one command: `gla.cmd` (in PowerShell use
rem `.\gla.cmd`). The first run provisions everything automatically:
rem   * a usable Python (an existing 3.10+ install, or a private copy in .python)
rem   * the .venv virtual environment
rem   * the package with every optional dependency (CLI + local web UI)
rem
rem NOTE: messages are intentionally ASCII-only - cmd.exe decodes .cmd files with
rem the OEM code page, so non-ASCII text would garble on many systems.

setlocal EnableExtensions
cd /d "%~dp0"

set "VENV_PY=%~dp0.venv\Scripts\python.exe"

rem Fast path: an existing venv that can import the full dependency set.
if exist "%VENV_PY%" (
    "%VENV_PY%" -c "import gamelink, fastapi, uvicorn" >nul 2>nul
    if not errorlevel 1 goto :run
)

call :setup
if errorlevel 1 exit /b 1

:run
"%VENV_PY%" -m gamelink %*
exit /b %errorlevel%

:setup
where powershell >nul 2>nul
if errorlevel 1 (
    echo [GameLink Agent] ERROR: Windows PowerShell was not found.
    echo                   Install Python 3.10+ from https://www.python.org/downloads/
    echo                   ^(tick "Add python.exe to PATH"^), then run gla.cmd again.
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\bootstrap.ps1"
exit /b %errorlevel%
