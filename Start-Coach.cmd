@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Environment proyek belum ada. Jalankan scripts\setup-windows.ps1 dahulu.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -E -s -m chesslab.cli --config config.json coach
if errorlevel 1 pause
