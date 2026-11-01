@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo   NetVisor - Process and Logs Cleaner
echo ===================================================
echo.
echo Stopping any running capture or server processes...

REM Terminate any dangling capture engines
taskkill /F /IM dumpcap.exe >nul 2>&1
taskkill /F /IM tshark.exe >nul 2>&1

REM Terminate any processes holding NetVisor ports 8000 and 8765
for /f "tokens=5" %%p in ('netstat -aon 2^>nul ^| findstr ":8765 :8000" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%p >nul 2>&1
)

echo Cleaning temporary logs and capture files...
powershell -NoProfile -Command "Get-ChildItem -Path '%~dp0logs', '%~dp0captures' -File | Where-Object { $_.Name -ne '.gitkeep' } | Remove-Item -Force" >nul 2>&1

echo [SUCCESS] All NetVisor processes terminated and logs cleared!
echo.
pause
