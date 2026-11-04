@echo off
setlocal

cd /d "%~dp0frontend"

set "VITE_DEV_API_PROXY_TARGET=http://127.0.0.1:1534"
set "VITE_API_BASE_URL="

echo Starting optimized Business Suite on http://localhost:5173
echo Backend proxy: %VITE_DEV_API_PROXY_TARGET%
echo.

call npm start

endlocal
