@echo off
cd /d "D:\EE-Finance-Agent"

set PORT=28711

echo Starting EE Finance Agent...
echo.

echo Freeing port %PORT% if in use...
for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%p >nul 2>&1
)

for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
    set LAN_IP=%%a
)
setlocal enabledelayedexpansion
set LAN_IP=!LAN_IP: =!
echo   On this PC:      http://localhost:%PORT%
echo   From other PCs:  http://!LAN_IP!:%PORT%
echo.
echo Leave this window open while using the app. Close it to stop the server.
echo.

".venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port %PORT%
pause
