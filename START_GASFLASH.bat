@echo off
setlocal EnableDelayedExpansion

:: GASFLASH PRO (beta version) - Universal Launcher
:: Numerical Core: Numba-Accelerated Roe/MUSCL

echo ===================================================
echo     GASFLASH PRO: ADVANCED INSTALLATION
echo     Numerical Core: Numba-Accelerated Roe/MUSCL
echo ===================================================
echo.

:: Inizializzazione
set NEEDS_FULL_REBUILD=0
set BEHIND_COUNT=0

:: --- CONTROLLO AGGIORNAMENTI (UNIVERSALE) ---
set GIT_AVAILABLE=0
git --version >nul 2>&1
if %ERRORLEVEL% EQU 0 set GIT_AVAILABLE=1

if %GIT_AVAILABLE% EQU 1 (
    echo [1/5] Controllo aggiornamenti via Git...
    git fetch origin >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        for /f "tokens=*" %%i in ('git rev-list HEAD..origin/main --count 2^>nul') do set BEHIND_COUNT=%%i
        if "!BEHIND_COUNT!"=="" set BEHIND_COUNT=0
        
        if !BEHIND_COUNT! GTR 0 (
            echo [INFO] Rilevato aggiornamento (!BEHIND_COUNT! nuovi commit). Sincronizzazione...
            git reset --hard origin/main >nul 2>&1
            git clean -fd >nul 2>&1
            set NEEDS_FULL_REBUILD=1
        ) else (
            echo [INFO] Codice gia' aggiornato (Git).
        )
    ) else (
        echo [INFO] GitHub non raggiungibile. Procedo offline.
    )
) else (
    echo [1/5] Git non trovato. Tentativo di aggiornamento via ZIP (PowerShell)...
    powershell -Command "try { $url = 'https://github.com/Matteobeo/Iterative-1D-Gasdynamic-Solver/archive/refs/heads/main.zip'; Write-Host 'Download aggiornamento in corso...'; Invoke-WebRequest -Uri $url -OutFile 'update.zip'; Write-Host 'Estrazione...'; Expand-Archive -Path 'update.zip' -DestinationPath 'temp_update' -Force; Copy-Item -Path 'temp_update\Iterative-1D-Gasdynamic-Solver-main\*' -Destination '.' -Recurse -Force; Remove-Item 'update.zip'; Remove-Item 'temp_update' -Recurse; Write-Host 'Aggiornamento completato.'; exit 0 } catch { exit 1 }"
    if %ERRORLEVEL% EQU 0 (
        set NEEDS_FULL_REBUILD=1
    ) else (
        echo [ATTENZIONE] Impossibile aggiornare via ZIP. Procedo con la versione locale.
    )
)

:: --- SEZIONE BACKEND ---
echo [2/5] Gestione dipendenze Python...
cd /d "%~dp0backend"
if "!NEEDS_FULL_REBUILD!"=="1" (
    echo [INFO] Reinstallazione forzata pacchetti...
    python -m pip install --upgrade --force-reinstall -r requirements.txt
) else (
    python -m pip install -r requirements.txt
)
if %ERRORLEVEL% NEQ 0 echo [!] Nota: Errore minore durante l'installazione Python.
cd /d "%~dp0"

:: --- SEZIONE FRONTEND ---
echo [3/5] Gestione moduli Node.js...
cd /d "%~dp0frontend"

rem Verifica se Vite è presente (indicatore di installazione corretta)
set FRONTEND_BROKEN=0
if not exist node_modules\.bin\vite set FRONTEND_BROKEN=1

if "!NEEDS_FULL_REBUILD!"=="1" set FRONTEND_BROKEN=1

if "!FRONTEND_BROKEN!"=="1" (
    echo [INFO] Rilevata installazione incompleta o corrotta. Ripristino in corso...
    if exist node_modules rd /s /q node_modules
    call npm install
) else (
    if exist package-lock.json (
        call npm ci
    ) else (
        call npm install
    )
)
if %ERRORLEVEL% NEQ 0 echo [!] Nota: Errore durante l'installazione Node.js.
cd /d "%~dp0"

echo.
echo ===================================================
echo     AVVIO DEI SERVIZI
echo ===================================================
echo.

:: --- AVVIO SERVER ---
echo [4/5] Lancio dei server in background...
start /b cmd /c "cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000"
start /b cmd /c "cd frontend && npm run dev"

:: --- ATTESA E BROWSER ---
echo [5/5] In attesa che i server siano pronti...
timeout /t 8 /nobreak >nul

echo Apertura del simulatore...
start http://localhost:5173

echo.
echo ===================================================
echo     SYSTEM READY! 
echo     Mantieni questa finestra aperta durante l'uso.
echo ===================================================
echo.
pause
