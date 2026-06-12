@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  set "PYTHON=.venv\Scripts\python.exe"
) else (
  set "PYTHON=python"
)

echo Starting MicroScore...
"%PYTHON%" -m microscore_api.dev

if errorlevel 1 (
  echo.
  echo MicroScore did not start.
  echo Install dependencies with:
  echo   .venv\Scripts\python -m pip install -r requirements.txt
  echo.
  pause
)
