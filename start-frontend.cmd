@echo off
setlocal

cd /d "%~dp0frontend"

set "VITE_DEV_API_PROXY_TARGET=http://localhost:1534"
set "VITE_API_BASE_URL="

echo Starting Business Suite frontend on http://localhost:5173
echo Backend proxy: %VITE_DEV_API_PROXY_TARGET%
echo.

npm run dev

endlocal
