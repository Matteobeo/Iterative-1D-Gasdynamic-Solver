#!/bin/bash
# GASFLASH PRO (beta version) - Launcher for Mac/Linux

echo "==================================================="
echo "    GASFLASH PRO: ADVANCED INSTALLATION"
echo "    Numerical Core: Numba-Accelerated Roe/MUSCL"
echo "==================================================="
echo ""

# Inizializzazione
NEEDS_FULL_REBUILD=0

# --- CONTROLLO GIT ---
if ! command -v git &> /dev/null
then
    echo "[ATTENZIONE] Git non rilevato. Saltando aggiornamenti..."
    NEEDS_FULL_REBUILD=0
else
    # --- AGGIORNAMENTO DA GITHUB ---
    echo "[1/5] Controllo aggiornamenti da GitHub..."
    if git fetch origin > /dev/null 2>&1; then
        BEHIND_COUNT=$(git rev-list HEAD..origin/main --count 2>/dev/null)
        
        if [ "${BEHIND_COUNT:-0}" -gt 0 ]; then
            echo "[INFO] Rilevato aggiornamento ($BEHIND_COUNT nuovi commit)."
            echo "[INFO] Esecuzione \"FORCE CLEAN UPDATE\": sincronizzazione completa..."
            git reset --hard origin/main
            git clean -fd
            NEEDS_FULL_REBUILD=1
        else
            echo "[INFO] Il codice è già aggiornato all'ultima versione di GitHub."
            NEEDS_FULL_REBUILD=0
        fi
    else
        echo "[INFO] Impossibile contattare GitHub. Procedo in modalità offline."
        NEEDS_FULL_REBUILD=0
    fi
fi

# --- SEZIONE BACKEND ---
echo "[2/5] Gestione dipendenze Python..."
cd backend || exit
if [ "$NEEDS_FULL_REBUILD" -eq 1 ]; then
    echo "[INFO] Reinstallazione forzata..."
    python3 -m pip install --upgrade --force-reinstall -r requirements.txt
else
    python3 -m pip install -r requirements.txt
fi
cd ..

# --- SEZIONE FRONTEND ---
echo "[3/5] Gestione moduli Node.js..."
cd frontend || exit

# Verifica se Vite è presente (indicatore di installazione corretta)
FRONTEND_BROKEN=0
if [ ! -f "node_modules/.bin/vite" ]; then
    FRONTEND_BROKEN=1
fi

if [ "$NEEDS_FULL_REBUILD" -eq 1 ] || [ "$FRONTEND_BROKEN" -eq 1 ]; then
    echo "[INFO] Rilevata installazione incompleta o corrotta. Ripristino in corso..."
    if [ -d "node_modules" ]; then
        echo "[INFO] Pulizia moduli frontend..."
        rm -rf node_modules
    fi
    npm install
else
    echo "[3/5] Controllo moduli Node.js (Rapido)..."
    if [ -f "package-lock.json" ]; then
        npm ci
    else
        npm install
    fi
fi
cd ..

echo ""
echo "==================================================="
echo "    AVVIO DEI SERVIZI"
echo "==================================================="
echo ""

# --- AVVIO SERVER ---
echo "[4/5] Lancio dei server in background..."
(cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000) &
(cd frontend && npm run dev) &

# --- ATTESA E BROWSER ---
echo "[5/5] In attesa che i server siano pronti..."
sleep 8

echo "Apertura del simulatore..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:5173
else
    xdg-open http://localhost:5173 || echo "Apri manualmente: http://localhost:5173"
fi

echo ""
echo "==================================================="
echo "    SYSTEM READY!" 
echo "    Mantieni aperto il terminale durante l'uso."
echo "==================================================="
echo ""

# Wait for background processes
wait
