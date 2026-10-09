@echo off
setlocal
title OVMS - qwen3.8-27b-ov
set "PYTHONHOME="
set "PYTHONPATH="
set "VIRTUAL_ENV="
set "OVMS_DIR=%~dp0..\ovms_downloaded\windows-2026.4.0-python-on\ovms"
set "MODEL_DIR=%~dp0morteza89-qwen3.8-27b-int4-ov"
set "OV_CACHE_DIR=%~dp0ov-cache-morteza89-27b"
if not exist "%OVMS_DIR%\setupvars.bat" exit /b 1
call "%OVMS_DIR%\setupvars.bat"
if errorlevel 1 exit /b 1
if /i "%~1"=="--version" (
    "%OVMS_DIR%\ovms.exe" --version
    exit /b
)
if not exist "%MODEL_DIR%\openvino_language_model.xml" (
    echo Model download is missing: %MODEL_DIR%
    exit /b 1
)
if not exist "%OV_CACHE_DIR%" mkdir "%OV_CACHE_DIR%"
if errorlevel 1 exit /b 1
"%OVMS_DIR%\ovms.exe" ^
  --rest_port 8000 ^
  --rest_bind_address 127.0.0.1 ^
  --model_name qwen3.8-27b-ov ^
  --model_path "%MODEL_DIR%" ^
  --task text_generation ^
  --target_device GPU ^
  --enable_prefix_caching true ^
  --cache_dir "%OV_CACHE_DIR%" ^
  --log_level INFO
exit /b %ERRORLEVEL%