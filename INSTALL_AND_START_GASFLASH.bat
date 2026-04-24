@echo off
TITLE GASFLASH PRO - High-Performance CFD Suite
COLOR 0B

:: Posizionamento nella cartella dello script
cd /d "%~dp0"

echo ===================================================
echo     GASFLASH PRO: ADVANCED INSTALLATION
echo     Numerical Core: Numba-Accelerated Roe/MUSCL
echo ===================================================
echo.

:: Verifica se la cartella del progetto esiste
if not exist "gasdynamics-sim" (
    echo [ERRORE] Cartella 'gasdynamics-sim' non trovata!
    pause
    exit /b
)

:: --- AGGIORNAMENTO DA GITHUB ---
echo [1/5] Controllo aggiornamenti da GitHub...
cd /d "gasdynamics-sim"
git pull origin main
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Impossibile aggiornare da GitHub. Procedo con la versione locale.
)
cd /d "%~dp0"

:: --- SEZIONE BACKEND ---
echo [2/5] Installazione dipendenze Python (Backend)...
cd /d "gasdynamics-sim\backend"
python -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ATTENZIONE] Errore durante l'installazione Python. 
    echo Assicurati di avere Python installato e nel PATH.
)
cd /d "%~dp0"

:: --- SEZIONE FRONTEND ---
echo [3/5] Installazione moduli Node.js (Frontend)...
cd /d "gasdynamics-sim\frontend"
call npm install
if %ERRORLEVEL% NEQ 0 (
    echo [ATTENZIONE] Errore durante l'installazione Node.js.
    echo Assicurati di avere Node.js installato e nel PATH.
)
cd /d "%~dp0"

echo.
echo ===================================================
echo     AVVIO DEI SERVIZI
echo ===================================================
echo.

:: --- AVVIO SERVER ---
echo [4/5] Lancio dei server in background...
start /b cmd /c "cd gasdynamics-sim\backend && uvicorn app.main:app --host 127.0.0.1 --port 8000"
start /b cmd /c "cd gasdynamics-sim\frontend && npm run dev"

:: --- ATTESA E BROWSER ---
echo [5/5] In attesa che i server siano pronti...
timeout /t 8 /nobreak > nul

echo Apertura del simulatore...
start http://localhost:5173

echo.
echo ===================================================
echo     SYSTEM READY! 
echo     High-Performance CFD Core is now active.
echo     Close this window only after your session.
echo ===================================================
echo.
pause
