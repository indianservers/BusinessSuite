@echo off
setlocal

cd /d "%~dp0"

echo Starting Business Suite backend and frontend...
echo Backend:  http://localhost:1534
echo Frontend: http://localhost:5173
echo.

start "Business Suite Backend" cmd /k "%~dp0start-backend.cmd"
start "Business Suite Frontend" cmd /k "%~dp0start-frontend.cmd"

endlocal
