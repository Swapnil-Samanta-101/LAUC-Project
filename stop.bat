@echo off
title Stop 2D Navier-Stokes CFD Simulator
cd /d "%~dp0"
echo ===================================================
echo   Stop 2D Navier-Stokes CFD Simulator (LAUC Project)
echo ===================================================
echo.

set "FOUND=0"

echo [1/2] Checking for server listening on port 8000...
for /f "tokens=5" %%p in ('netstat -aon ^| findstr /r /c:":8000 .*LISTENING"') do (
    echo Terminating PID %%p listening on port 8000...
    taskkill /F /PID %%p >nul 2>&1
    set "FOUND=1"
)

echo [2/2] Checking for simulator console window...
taskkill /FI "WINDOWTITLE eq 2D Navier-Stokes CFD Simulator*" /T /F >nul 2>&1
if not errorlevel 1 (
    set "FOUND=1"
)

echo.
if "%FOUND%"=="1" (
    echo ===================================================
    echo   CFD Simulator server stopped successfully.
    echo ===================================================
) else (
    echo ===================================================
    echo   No running server found on port 8000.
    echo ===================================================
)

echo.
pause
