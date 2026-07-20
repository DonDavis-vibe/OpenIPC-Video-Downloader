@echo off
title OpenIPC VRX Flight Downloader
cd /d "%~dp0"
python openipc_downloader.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred running the script.
    pause
)
