@echo off
setlocal
"%~dp0python\python.exe" -I "%~dp0local_workspace.py"
if errorlevel 1 pause
