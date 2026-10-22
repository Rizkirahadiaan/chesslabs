@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build-windows.ps1"
if errorlevel 1 goto failed
echo.
echo Selesai: outputs\licensed\ChessLab-Coach.exe
pause
exit /b 0
:failed
echo Build gagal. Periksa pesan di atas.
pause
exit /b 1
