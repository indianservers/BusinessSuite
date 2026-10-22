@echo off
setlocal

cd /d "%~dp0backend"

if exist "%~dp0.local\postgresql\data\PG_VERSION" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0backend\scripts\local_postgres.ps1" start
    if errorlevel 1 exit /b 1
)

echo Starting Business Suite backend on http://localhost:1534
echo.

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" main.py
) else (
    python main.py
)

endlocal
