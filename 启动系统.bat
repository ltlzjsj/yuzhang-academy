@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Yuzhang Academy - starting

rem ==========================================================================
rem  One-click launcher. Every path is derived from this script's own location,
rem  so the repository can sit in any folder after "git clone".
rem
rem  Optional environment variables:
rem    PYTHON           python.exe used for the backend
rem    LIVETALKING_DIR  path of the LiveTalking checkout (default ..\LiveTalking)
rem ==========================================================================

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "LIVETALK_DIR=%ROOT%..\LiveTalking"
if not "%LIVETALKING_DIR%"=="" set "LIVETALK_DIR=%LIVETALKING_DIR%"

echo ==============================================
echo   Yuzhang Academy - starting all services
echo   repo: %ROOT%
echo ==============================================
echo.

if not exist "%BACKEND%\app\main.py" (
  echo [x] Cannot find the backend at "%BACKEND%".
  echo     Please keep this .bat file in the repository root.
  echo.
  pause
  exit /b 1
)

rem ---------------------------------------------------------------- python ---
set "PY="
if not "%PYTHON%"=="" if exist "%PYTHON%" set "PY=%PYTHON%"
for %%D in (
  "%BACKEND%\.venv\Scripts\python.exe"
  "%CONDA_PREFIX%\python.exe"
  "D:\Anaconda\envs\geogemma\python.exe"
  "%USERPROFILE%\anaconda3\envs\geogemma\python.exe"
  "%USERPROFILE%\miniconda3\envs\geogemma\python.exe"
  "%ProgramData%\Anaconda3\envs\geogemma\python.exe"
) do if not defined PY if exist %%D set "PY=%%~D"
if not defined PY for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"

if not defined PY (
  echo [x] Python interpreter not found.
  echo     Install Python 3.10+ ^(or run the 安装依赖.bat helper^), then retry.
  echo.
  pause
  exit /b 1
)
echo [i] backend python : %PY%

"%PY%" -c "import fastapi, uvicorn, sqlalchemy" >nul 2>nul
if errorlevel 1 (
  echo.
  echo [x] Backend dependencies are missing for this interpreter.
  echo     Run 安装依赖.bat first, or install them manually:
  echo         "%PY%" -m pip install -r "%BACKEND%\requirements.txt"
  echo.
  pause
  exit /b 1
)

rem ------------------------------------------------------------------ .env ---
if not exist "%BACKEND%\.env" (
  echo [!] backend\.env not found - creating it from .env.example
  copy /y "%BACKEND%\.env.example" "%BACKEND%\.env" >nul
  echo     Remember to fill in MIMO_API_KEY before using chat or voice.
)

rem ------------------------------------------------------- port occupation ---
powershell -NoProfile -Command "Get-NetTCPConnection -State Listen -LocalPort 8000,5173,8010 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host ('[!] port {0} is already in use (PID {1})' -f $_.LocalPort, $_.OwningProcess) }"

rem ----------------------------------------------------------------- start ---
set "RUN=%ROOT%.run"
if not exist "%RUN%" mkdir "%RUN%"
del /q "%RUN%\*.pid" >nul 2>nul

echo.
echo [1/4] backend  (FastAPI :8000)
cd /d "%BACKEND%"
powershell -NoProfile -Command "$p = Start-Process -FilePath '%PY%' -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory '%BACKEND%' -NoNewWindow -PassThru; Set-Content -Path '%RUN%\backend.pid' -Value $p.Id"

echo [2/4] worker   (Celery, needs Redis)
powershell -NoProfile -Command "$p = Start-Process -FilePath '%PY%' -ArgumentList @('-m','celery','-A','app.workers.celery_app','worker','--loglevel=info','--pool=solo') -WorkingDirectory '%BACKEND%' -NoNewWindow -PassThru; Set-Content -Path '%RUN%\worker.pid' -Value $p.Id"

rem -------------------------------------------------- digital human (opt.) ---
echo [3/4] digital human (LiveTalking :8010)
if not exist "%LIVETALK_DIR%\app.py" (
  echo       - skipped: no LiveTalking checkout at "%LIVETALK_DIR%"
  echo         see docs\数字人实时引擎.md to enable the realtime avatar
  goto :frontend
)
if not exist "%LIVETALK_DIR%\models\wav2lip.pth" (
  echo       - skipped: models\wav2lip.pth is missing in the LiveTalking folder
  goto :frontend
)
if not exist "%LIVETALK_DIR%\data\avatars" (
  echo       - skipped: no avatar data under data\avatars - build it first
  goto :frontend
)

set "LTPY="
if not "%LIVETALKING_PYTHON%"=="" if exist "%LIVETALKING_PYTHON%" set "LTPY=%LIVETALKING_PYTHON%"
for %%D in (
  "%LIVETALK_DIR%\.venv\Scripts\python.exe"
  "%CONDA_PREFIX%\python.exe"
  "D:\Anaconda\envs\livetalking\python.exe"
  "D:\Anaconda\envs\echomimic\python.exe"
  "%USERPROFILE%\anaconda3\envs\livetalking\python.exe"
  "%USERPROFILE%\miniconda3\envs\livetalking\python.exe"
  "%USERPROFILE%\anaconda3\envs\echomimic\python.exe"
  "%USERPROFILE%\miniconda3\envs\echomimic\python.exe"
) do if not defined LTPY if exist %%D set "LTPY=%%~D"

if not defined LTPY (
  echo       - skipped: no Python with the LiveTalking dependencies was found
  echo         set LIVETALKING_PYTHON to a working python.exe if you have one
  goto :frontend
)
"%LTPY%" -c "import torch, aiortc, cv2" >nul 2>nul
if errorlevel 1 (
  echo       - skipped: this interpreter lacks torch / aiortc / opencv
  echo         set LIVETALKING_PYTHON to a working python.exe, see docs
  goto :frontend
)
echo       using %LTPY%
cd /d "%LIVETALK_DIR%"
powershell -NoProfile -Command "$p = Start-Process -FilePath '%LTPY%' -ArgumentList @('app.py','--transport','webrtc','--model','wav2lip','--avatar_id','jiangwanli_lt','--customvideo_config','custom_jiangwanli.json') -WorkingDirectory '%LIVETALK_DIR%' -NoNewWindow -PassThru; Set-Content -Path '%RUN%\livetalking.pid' -Value $p.Id"

:frontend
rem -------------------------------------------------------------- frontend ---
echo [4/4] frontend (Vite :5173)
cd /d "%FRONTEND%"
if not exist "node_modules" (
  echo       - node_modules missing, running "npm install" first...
  call npm install
  if errorlevel 1 (
    echo [x] npm install failed. Is Node.js 18+ installed?
    pause
    exit /b 1
  )
)
powershell -NoProfile -Command "$p = Start-Process -FilePath 'cmd.exe' -ArgumentList @('/c','npm run dev') -WorkingDirectory '%FRONTEND%' -NoNewWindow -PassThru; Set-Content -Path '%RUN%\frontend.pid' -Value $p.Id"

echo.
echo Waiting for the services to come up...
timeout /t 15 /nobreak >nul

powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:8000/health -TimeoutSec 5; Write-Host ('[ok] backend /health -> ' + $r.StatusCode) } catch { Write-Host '[!] backend did not answer on :8000 - is MySQL / Redis running and backend\.env correct?' }"

echo.
echo   site     : http://localhost:5173
echo   api docs : http://127.0.0.1:8000/docs
echo   health   : http://127.0.0.1:8000/health
echo.
echo Close this window (X) to stop all services.
start "" "http://localhost:5173"

:loop
timeout /t 60 /nobreak >nul
goto loop
