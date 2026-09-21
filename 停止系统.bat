@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Yuzhang Academy - stopping
echo Stopping Yuzhang Academy services ...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_services.ps1" -Root "%~dp0"
echo.
echo Done.
pause
