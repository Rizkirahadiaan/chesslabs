@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m chesslab.cli --config config.json coach
) else (
  python -m chesslab.cli --config config.json coach
)
if errorlevel 1 pause
