@echo off
TITLE GASFLASH PRO (beta version) - High-Performance CFD Suite
COLOR 0B

:: Posizionamento nella cartella dello script
cd /d "%~dp0"

echo ===================================================
echo     GASFLASH PRO: ADVANCED INSTALLATION
echo     Numerical Core: Numba-Accelerated Roe/MUSCL
echo ===================================================
echo.

:: --- AGGIORNAMENTO DA GITHUB ---
echo [1/5] Controllo aggiornamenti da GitHub...
git fetch origin
git merge origin/main --no-edit
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Conflitto o errore git. Procedo con la versione locale.
)

:: --- SEZIONE BACKEND ---
echo [2/5] Installazione dipendenze Python (Backend)...
cd /d "%~dp0backend"
python -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ATTENZIONE] Errore durante l'installazione Python. 
    echo Assicurati di avere Python installato e nel PATH.
)
cd /d "%~dp0"

:: --- SEZIONE FRONTEND ---
echo [3/5] Installazione moduli Node.js (Frontend)...
cd /d "%~dp0frontend"
:: Usa ci se package-lock esiste, altrimenti install
if exist package-lock.json (
    call npm ci
) else (
    call npm install
)
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
start /b cmd /c "cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000"
start /b cmd /c "cd frontend && npm run dev"

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
