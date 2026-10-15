@echo off
rem GameLink Agent launcher.
rem Lets you run `gla <command>` from the repository root without activating the venv.
rem It always runs from the repo root so `.env` and relative project paths resolve.

cd /d "%~dp0"

if exist ".venv\Scripts\gla.exe" (
    ".venv\Scripts\gla.exe" %*
) else if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m gamelink %*
) else (
    python -m gamelink %*
)
