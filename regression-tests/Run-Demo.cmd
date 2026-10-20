@echo off
setlocal
start "Requests Regression Tests Demo" powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0..\dependency-migration\demo-controller.ps1" -Workflow regression-tests
endlocal