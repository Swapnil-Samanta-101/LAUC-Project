@echo off
title 2D Navier-Stokes CFD Simulator
cd /d "%~dp0"
echo ===================================================
echo   2D Navier-Stokes CFD Simulator (LAUC Project)
echo ===================================================
echo Starting server on http://127.0.0.1:8000 ...
start "" http://127.0.0.1:8000
python -m uvicorn web.server:app --host 127.0.0.1 --port 8000
pause
