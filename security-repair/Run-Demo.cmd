@echo off
setlocal
start "Security Repair Demo" powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0..\dependency-migration\demo-controller.ps1" -Workflow security-repair
endlocal