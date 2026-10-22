@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" android\tools\build.py
if errorlevel 1 exit /b 1
echo APK tersedia di outputs\android\ChessLab-Coach-Android.apk
