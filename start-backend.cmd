@echo off
setlocal

cd /d "%~dp0backend"

echo Starting Business Suite backend on http://localhost:1534
echo.

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" main.py
) else (
    python main.py
)

endlocal
