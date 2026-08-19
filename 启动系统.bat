@echo off
title Academy System
cd /d D:\Desktop\shuyuan\yuzhang-academy-main\backend

echo [1/3] Starting backend...
start /b "" D:\Anaconda\envs\geogemma\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

echo [2/3] Starting worker...
start /b "" D:\Anaconda\envs\geogemma\python.exe -m celery -A app.workers.celery_app worker --loglevel=info --pool=solo

cd /d D:\Desktop\shuyuan\yuzhang-academy-main\frontend
echo [3/3] Starting frontend...
start /b "" cmd /c "npm run dev"

timeout /t 6 /nobreak >nul
start "" "http://localhost:5173"

echo.
echo All services are running in this one window.
echo Close this window (X) to stop all services.

:loop
timeout /t 60 /nobreak >nul
goto loop
