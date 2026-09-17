@echo off
title Academy System
cd /d D:\Desktop\shuyuan\yuzhang-academy-main\backend

echo [1/4] Starting backend...
start /b "" D:\Anaconda\envs\geogemma\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

echo [2/4] Starting worker...
start /b "" D:\Anaconda\envs\geogemma\python.exe -m celery -A app.workers.celery_app worker --loglevel=info --pool=solo

echo [3/4] Starting LiveTalking digital human (wav2lip: jiangwanli / luocongyan)...
cd /d D:\Desktop\shuyuan\LiveTalking
start /b "" D:\Anaconda\envs\echomimic\python.exe app.py --transport webrtc --model wav2lip --avatar_id jiangwanli_lt --customvideo_config custom_jiangwanli.json

cd /d D:\Desktop\shuyuan\yuzhang-academy-main\frontend
echo [4/4] Starting frontend...
start /b "" cmd /c "npm run dev"

timeout /t 15 /nobreak >nul
start "" "http://localhost:5173"

echo.
echo All services are running in this one window.
echo Close this window (X) to stop all services.

:loop
timeout /t 60 /nobreak >nul
goto loop
