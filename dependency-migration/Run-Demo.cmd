@echo off
setlocal
start "Dependency Migration Demo" powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0demo-controller.ps1"
endlocal