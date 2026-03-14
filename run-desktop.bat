@echo off
cd /d "%~dp0"

if /i "%cd%"=="C:\Windows\System32" (
    color 0C
    echo George Michael Voice Converter does not require administrator permissions and should be run as a regular user.
    echo.
    pause
    exit /b 1
)

if not exist env (
    echo Please run 'run-install.bat' first to set up the environment.
    pause
    exit /b 1
)

env\python.exe desktop.py
echo.
pause

