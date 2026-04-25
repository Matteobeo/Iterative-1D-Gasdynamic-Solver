@echo off
setlocal EnableDelayedExpansion

TITLE GASFLASH PRO (beta version) - High-Performance CFD Suite
COLOR 0B

:: Posizionamento nella cartella dello script
cd /d "%~dp0"

echo ===================================================
echo     GASFLASH PRO: ADVANCED INSTALLATION
echo     Numerical Core: Numba-Accelerated Roe/MUSCL
echo ===================================================
echo.

:: Inizializzazione variabili
set NEEDS_FULL_REBUILD=0
set BEHIND_COUNT=0

:: --- CONTROLLO GIT ---
git --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ATTENZIONE] Git non rilevato. Saltando aggiornamenti...
    goto SKIP_GIT
)

:: --- AGGIORNAMENTO DA GITHUB ---
echo [1/5] Controllo aggiornamenti da GitHub...
git fetch origin > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Impossibile contattare GitHub. Procedo in modalita' offline.
    goto SKIP_GIT
)

:: Recupera il numero di commit mancanti
for /f "tokens=*" %%i in ('git rev-list HEAD..origin/main --count 2^>nul') do set BEHIND_COUNT=%%i

:: Se BEHIND_COUNT e' nullo o non numerico, forziamo a 0 per sicurezza
set "var="&for /f "delims=0123456789" %%a in ("!BEHIND_COUNT!") do set "var=%%a"
if defined var set BEHIND_COUNT=0
if "!BEHIND_COUNT!"=="" set BEHIND_COUNT=0

if !BEHIND_COUNT! GTR 0 (
    echo [INFO] Rilevato aggiornamento (!BEHIND_COUNT! nuovi commit).
    echo [INFO] Esecuzione "FORCE CLEAN UPDATE": sincronizzazione completa...
    git reset --hard origin/main
    git clean -fd
    set NEEDS_FULL_REBUILD=1
) else (
    echo [INFO] Il codice e' gia' aggiornato all'ultima versione di GitHub.
)

:SKIP_GIT

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
:: Uso di start /b con titoli espliciti per stabilita'
start "GASFLASH_BACKEND" /b cmd /c "cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000"
start "GASFLASH_FRONTEND" /b cmd /c "cd frontend && npm run dev"

:: --- ATTESA E BROWSER ---
echo [5/5] In attesa che i server siano pronti...
timeout /t 8 /nobreak > nul

echo Apertura del simulatore...
start http://localhost:5173

echo.
echo ===================================================
echo     SYSTEM READY! 
echo     Mantieni questa finestra aperta durante l'uso.
echo ===================================================
echo.
pause
