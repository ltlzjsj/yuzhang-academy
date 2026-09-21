@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Yuzhang Academy - setup

rem ==========================================================================
rem  First-run setup for a freshly cloned repository:
rem    1. check Python / Node
rem    2. install backend requirements (into backend\.venv when needed)
rem    3. create backend\.env from .env.example
rem    4. install frontend packages
rem    5. create / upgrade the database schema
rem  Safe to run again - every step is skipped when it is already done.
rem ==========================================================================

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"

echo ==============================================
echo   Yuzhang Academy - dependency setup
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
  echo [x] Python not found. Install Python 3.10 - 3.12 first:
  echo     https://www.python.org/downloads/   ^(tick "Add python.exe to PATH"^)
  echo.
  pause
  exit /b 1
)
echo [i] python : %PY%

rem --------------------------------------------- backend dependencies -------
set "VENV_PY=%BACKEND%\.venv\Scripts\python.exe"
"%PY%" -c "import fastapi, uvicorn, sqlalchemy, alembic" >nul 2>nul
if not errorlevel 1 if not exist "%VENV_PY%" (
  echo [i] this interpreter already has the backend dependencies - skipping pip.
  goto :env
)

if not exist "%VENV_PY%" (
  echo [1/5] creating virtual environment backend\.venv ...
  "%PY%" -m venv "%BACKEND%\.venv"
  if errorlevel 1 (
    echo [x] Could not create the virtual environment.
    pause
    exit /b 1
  )
) else (
  echo [1/5] reusing existing backend\.venv
)

echo [2/5] installing backend requirements (a few minutes) ...
"%VENV_PY%" -m pip install --upgrade pip
"%VENV_PY%" -m pip install -r "%BACKEND%\requirements.txt"
if errorlevel 1 (
  echo       - retrying with the Tsinghua mirror ...
  "%VENV_PY%" -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r "%BACKEND%\requirements.txt"
  if errorlevel 1 (
    echo [x] pip install failed.
    pause
    exit /b 1
  )
)
set "PY=%VENV_PY%"

:env
rem ------------------------------------------------------------- backend env -
if not exist "%BACKEND%\.env" (
  echo [3/5] creating backend\.env from .env.example
  copy /y "%BACKEND%\.env.example" "%BACKEND%\.env" >nul
  echo       - edit backend\.env and set MIMO_API_KEY ^(chat / voice^),
  echo         and JWT_SECRET ^(any long random string^).
) else (
  echo [3/5] backend\.env already exists - kept as is.
)

rem --------------------------------------------------------------- frontend -
echo [4/5] frontend packages
cd /d "%FRONTEND%"
where npm >nul 2>nul
if errorlevel 1 (
  echo [x] npm not found. Install Node.js 18+ from https://nodejs.org and retry.
  pause
  exit /b 1
)
if exist "node_modules" (
  echo       - node_modules already present - skipping npm install
) else (
  call npm ci 2>nul || call npm install
  if errorlevel 1 (
    echo [x] npm install failed.
    pause
    exit /b 1
  )
)

rem ------------------------------------------------------------------- lfs --
for %%F in ("%FRONTEND%\public\models\zhuxi_ue5.glb") do set "GLB_SIZE=%%~zF"
if not defined GLB_SIZE set "GLB_SIZE=0"
if %GLB_SIZE% LSS 1000000 (
  echo [!] the 3D models look like Git LFS pointers ^(not real files^).
  echo     Run:  git lfs install  ^&^&  git lfs pull
)

rem -------------------------------------------------------------- database --
echo [5/5] database schema
cd /d "%BACKEND%"
for /f "delims=" %%i in ('where docker 2^>nul') do set "HAS_DOCKER=1"
"%PY%" -c "import socket,sys; sys.exit(0 if socket.socket().connect_ex(('127.0.0.1',3306))==0 else 1)" >nul 2>nul
if errorlevel 1 (
  echo       - MySQL is not answering on 127.0.0.1:3306 yet.
  echo         start it with Docker:  docker compose -f docker/docker-compose.yml up -d mysql redis
  echo         ^(or install MySQL 8 + Redis yourself and match backend\.env^)
  echo         then run:  "%PY%" -m alembic upgrade head
) else (
  "%PY%" -m alembic upgrade head
  if errorlevel 1 (
    echo [!] alembic failed - check DB_USER / DB_PASSWORD / DB_NAME in backend\.env
  ) else (
    echo       - schema is up to date.
  )
)

echo.
echo ==============================================
echo   setup finished
echo ==============================================
echo   next steps:
echo     1. edit backend\.env  ^(MIMO_API_KEY, JWT_SECRET^)
echo     2. make sure MySQL and Redis are running
echo     3. double-click 启动系统.bat
echo     4. register an account on the site, then grant yourself admin:
echo          cd backend ^&^& ".venv\Scripts\python.exe" -m scripts.set_admin ^<username^>
echo.
echo   optional extras:
echo     - 书院图片 : point ACADEMY_IMAGES_DIR in backend\.env at your image folder
echo     - 实时数字人: see docs\数字人实时引擎.md
echo.
pause
