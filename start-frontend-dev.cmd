@echo off
setlocal
cd /d "%~dp0frontend"
set "VITE_DEV_API_PROXY_TARGET=http://127.0.0.1:1534"
set "VITE_API_BASE_URL="
echo Starting editable development app on http://localhost:5174
call npm run dev
endlocal
