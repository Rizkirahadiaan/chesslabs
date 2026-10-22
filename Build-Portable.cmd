@echo off
setlocal
cd /d "%~dp0"
set "BUILD_PYTHON=.venv\Scripts\python.exe"
if not exist "%BUILD_PYTHON%" (
  echo Virtual environment belum ada. Ikuti instalasi Windows pada README.md dahulu.
  pause
  exit /b 1
)
"%BUILD_PYTHON%" -m pip install -r requirements-build.txt
if errorlevel 1 goto failed
"%BUILD_PYTHON%" packaging\build_portable.py
if errorlevel 1 goto failed
echo.
echo Selesai: outputs\licensed\ChessLab-Coach.exe
pause
exit /b 0
:failed
echo Build gagal. Periksa pesan di atas.
pause
exit /b 1
