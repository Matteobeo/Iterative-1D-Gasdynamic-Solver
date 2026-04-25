@echo off
TITLE GASFLASH PRO Launcher
COLOR 0A

:: Ensure we are in the script's directory
cd /d "%~dp0"

echo ===================================================
echo     GASFLASH PRO: HIGH-PERFORMANCE CFD SUITE
echo     JIT-Compiled Roe/MUSCL Solver Ready
echo ===================================================
echo.

:: --- AGGIORNAMENTO DA GITHUB ---
echo [0/3] Controllo aggiornamenti da GitHub...
git pull origin main
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Impossibile aggiornare (nessuna connessione o repository non configurato).
)

echo [1/3] Avvio del Backend (FastAPI)...
start /b cmd /c "cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo [2/3] Avvio del Frontend (Vite/React)...
start /b cmd /c "cd frontend && npm run dev"

echo.
echo [3/3] In attesa che i server siano pronti...
timeout /t 5 /nobreak > nul

echo.
echo Apertura del simulatore nel browser...
start http://localhost:5173

echo.
echo ===================================================
echo     SIMULATORE ATTIVO! Chiudi questa finestra
echo     solo quando hai finito la sessione.
echo ===================================================
echo.
pause
