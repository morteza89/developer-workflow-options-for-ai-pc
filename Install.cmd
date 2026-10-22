@echo off
setlocal EnableExtensions DisableDelayedExpansion
title AI PC Workflows - Setup
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\install.ps1" %*
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="3010" echo Restart Windows to continue setup. Your files have been retained.
if not "%RESULT%"=="0" if not "%RESULT%"=="3010" echo Setup did not complete. Review the message and the .installer logs, then run this file again.
pause
exit /b %RESULT%