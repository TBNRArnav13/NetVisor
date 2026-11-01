@echo off
setlocal enabledelayedexpansion

REM Ensure current working directory is the script directory
cd /d "%~dp0"

REM If server.py not found in current folder, check common fallback paths
if not exist "server.py" if not exist "Server1.py" (
    if exist "E:\Coding\College\NetVisor\server.py" (
        cd /d "E:\Coding\College\NetVisor"
    )
)

chcp 65001 >nul 2>&1
title NetVisor - Live Network Packet Analysis Platform

echo ===================================================
echo   NetVisor - Live Network Packet Analysis Platform
echo ===================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in system PATH.
    echo Please install Python 3.8+ and try again.
    echo.
    pause
    exit /b 1
)

REM Verify we are in the correct directory
if not exist "server.py" if not exist "Server1.py" (
    echo [ERROR] server.py not found in: %CD%
    echo Please ensure start_live_dashboard.bat is placed inside the NetVisor folder.
    echo.
    pause
    exit /b 1
)

if not exist "netcap_manager.py" (
    echo [ERROR] netcap_manager.py not found in: %CD%
    echo Please ensure start_live_dashboard.bat is placed inside the NetVisor folder.
    echo.
    pause
    exit /b 1
)

REM Free any dangling previous instances holding the ports or capture handles
taskkill /F /IM dumpcap.exe >nul 2>&1
taskkill /F /IM tshark.exe >nul 2>&1
for /f "tokens=5" %%p in ('netstat -aon 2^>nul ^| findstr ":8765 :8000" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%p >nul 2>&1
)

echo Available network interfaces:
echo ---------------------------------------------------
python netcap_manager.py interfaces
echo ---------------------------------------------------
echo.
echo Choose run mode:
echo   [1] Live Packet Capture on Wi-Fi (Default - press Enter)
echo   [2] Live Packet Capture on custom interface
echo   [3] Simulation / Demo Mode (No admin rights required)
echo   [4] Server only (Web and WebSocket)
echo.

set "CHOICE="
set /p CHOICE="Select option [1-4, Enter for 1]: "

if "%CHOICE%"=="2" (
    echo.
    set /p INTERFACE="Enter interface name (e.g. Ethernet, Wi-Fi, Ethernet 3): "
    if "!INTERFACE!"=="" set "INTERFACE=Wi-Fi"
    echo.
    echo Starting NetVisor with interface: !INTERFACE!
    python start_live_dashboard.py --interface "!INTERFACE!"
) else if "%CHOICE%"=="3" (
    echo.
    echo Starting NetVisor in Simulation / Demo Mode...
    python start_live_dashboard.py --demo
) else if "%CHOICE%"=="4" (
    echo.
    echo Starting NetVisor Web and WebSocket server only...
    python start_live_dashboard.py --no-capture
) else (
    echo.
    echo Starting NetVisor Live Capture on Wi-Fi...
    python start_live_dashboard.py --interface "Wi-Fi"
)

if %errorlevel% neq 0 (
    echo.
    echo [NOTE] If capture failed due to permissions, try right-clicking
    echo        this .bat file and selecting "Run as administrator".
    echo.
)

REM Clean up all child processes and lingering sockets on exit
taskkill /F /IM dumpcap.exe >nul 2>&1
taskkill /F /IM tshark.exe >nul 2>&1
for /f "tokens=5" %%p in ('netstat -aon 2^>nul ^| findstr ":8765 :8000" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%p >nul 2>&1
)
