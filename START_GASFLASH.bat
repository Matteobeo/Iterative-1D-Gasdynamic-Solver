@echo off
setlocal EnableDelayedExpansion

:: GASFLASH PRO (beta) - Universal Smart Launcher V2.2
:: Numerical Core: Numba-Accelerated Roe/MUSCL
title GASFLASH PRO Launcher

echo ===================================================
echo     GASFLASH PRO: ADVANCED INSTALLATION
echo     Numerical Core: Numba-Accelerated Roe/MUSCL
echo ===================================================
echo.

:: --- CONFIGURAZIONE PERCORSI ---
set "ROOT=%~dp0"
set "BACKEND_DIR=%ROOT%backend"
set "FRONTEND_DIR=%ROOT%frontend"
set "REPO_NAME=Iterative-1D-Gasdynamic-Solver"
set "REPO_URL=https://github.com/Matteobeo/%REPO_NAME%"
set "API_URL=https://api.github.com/repos/Matteobeo/%REPO_NAME%/commits/main"
set "NEEDS_FULL_REBUILD=0"

:: --- PREREQUISITI ---
where python >nul 2>&1 || ( echo [ERRORE] Python non trovato. & pause & exit /b 1 )
where npm    >nul 2>&1 || ( echo [ERRORE] Node.js/npm non trovato. & pause & exit /b 1 )

echo [1/5] Verifica aggiornamenti sistema...

git --version >nul 2>&1
if !ERRORLEVEL! EQU 0 ( goto GIT_MODE ) else ( goto ZIP_MODE )

:GIT_MODE
echo [INFO] Modalita' Git.
git -C "%ROOT%." fetch origin >nul 2>&1
if !ERRORLEVEL! NEQ 0 ( echo [INFO] GitHub non raggiungibile. & goto SETUP_BACKEND )

for /f "tokens=*" %%i in ('git -C "%ROOT%." rev-list HEAD..origin/main --count 2^>nul') do set "BEHIND_COUNT=%%i"
if not defined BEHIND_COUNT set "BEHIND_COUNT=0"

if !BEHIND_COUNT! GTR 0 (
    echo [INFO] Aggiornamento Git (!BEHIND_COUNT! commit)...
    git -C "%ROOT%." reset --hard origin/main >nul 2>&1
    git -C "%ROOT%." clean -fd >nul 2>&1
    set "NEEDS_FULL_REBUILD=1"
) else (
    echo [INFO] Sistema aggiornato.
)
goto SETUP_BACKEND

:ZIP_MODE
echo [INFO] Modalita' ZIP (Smart Update).
set "LOCAL_SHA=none"
if exist "%ROOT%.last_commit" set /p LOCAL_SHA=<"%ROOT%.last_commit"

for /f "usebackq tokens=* delims=" %%a in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "(Invoke-RestMethod -Uri '%API_URL%').sha.Trim()" 2^>nul`) do set "REMOTE_SHA=%%a"

if not defined REMOTE_SHA ( echo [INFO] Verifica online fallita. & goto SETUP_BACKEND )

if /I "!REMOTE_SHA!"=="!LOCAL_SHA!" ( echo [INFO] Gia' aggiornato. & goto SETUP_BACKEND )

echo [INFO] Nuova versione su GitHub. Download...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Invoke-WebRequest -Uri '%REPO_URL%/archive/refs/heads/main.zip' -OutFile 'update.zip'; Expand-Archive -Path 'update.zip' -DestinationPath 'temp_update' -Force; Copy-Item -Path 'temp_update\%REPO_NAME%-main\*' -Destination '.' -Recurse -Force; Remove-Item 'update.zip'; Remove-Item 'temp_update' -Recurse -Force"

if !ERRORLEVEL! EQU 0 (
    echo !REMOTE_SHA! > "%ROOT%.last_commit"
    echo [INFO] Aggiornamento completato.
    set "NEEDS_FULL_REBUILD=1"
)
goto SETUP_BACKEND

:SETUP_BACKEND
echo [2/5] Ambiente Python...
cd /d "%BACKEND_DIR%"
if "!NEEDS_FULL_REBUILD!"=="1" (
    python -m pip install --upgrade -r requirements.txt
) else (
    python -m pip install -r requirements.txt
)

echo [3/5] Ambiente Frontend...
cd /d "%FRONTEND_DIR%"
set "FRONTEND_BROKEN=0"
if not exist "node_modules\.bin\vite.cmd" set "FRONTEND_BROKEN=1"
if "!NEEDS_FULL_REBUILD!"=="1" set "FRONTEND_BROKEN=1"

if "!FRONTEND_BROKEN!"=="1" (
    echo [INFO] Installazione moduli...
    if exist node_modules rd /s /q node_modules
    call npm install
) else (
    if exist package-lock.json ( call npm ci ) else ( call npm install )
)

echo.
echo ===================================================
echo     AVVIO GASDYNAMICS SIMULATOR
echo ===================================================
echo [4/5] Lancio motori di calcolo...

:: --- PULIZIA ---
taskkill /F /IM node.exe >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1

:: --- AVVIO (Sintassi robusta) ---
start "GASFLASH_BACKEND" cmd /k "cd /d "%BACKEND_DIR%" && uvicorn app.main:app --host 127.0.0.1 --port 8000"
start "GASFLASH_FRONTEND" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev"

echo [5/5] In attesa che l'interfaccia sia pronta...
set "TRIES=0"
:WAIT_LOOP
set /a TRIES+=1
echo [ATTESA] Tentativo !TRIES!/30...
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:5173' -UseBasicParsing -TimeoutSec 1; if($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if !ERRORLEVEL! EQU 0 goto OPEN_BROWSER
if !TRIES! GEQ 30 ( echo [WARN] Timeout, apro comunque. & goto OPEN_BROWSER )
timeout /t 1 /nobreak >nul
goto WAIT_LOOP

:OPEN_BROWSER
echo [OK] Interfaccia pronta. Apertura browser...
start http://localhost:5173

echo.
echo ===================================================
echo     PRONTO! ⚡
echo     Mantieni aperte le finestre dei server.
echo ===================================================
pause
