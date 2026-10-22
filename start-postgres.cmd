@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0backend\scripts\local_postgres.ps1" start
