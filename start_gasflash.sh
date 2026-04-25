#!/bin/bash
# GASFLASH PRO (beta version) - Universal Smart Launcher for Mac/Linux

echo "==================================================="
echo "    GASFLASH PRO: ADVANCED INSTALLATION"
echo "    Numerical Core: Numba-Accelerated Roe/MUSCL"
echo "==================================================="
echo ""

# Inizializzazione
NEEDS_FULL_REBUILD=0
REPO_URL="https://github.com/Matteobeo/Iterative-1D-Gasdynamic-Solver"
API_URL="https://api.github.com/repos/Matteobeo/Iterative-1D-Gasdynamic-Solver/commits/main"

# --- CONTROLLO AGGIORNAMENTI (SMART) ---
GIT_AVAILABLE=0
if git --version &> /dev/null; then
    GIT_AVAILABLE=1
fi

if [ "$GIT_AVAILABLE" -eq 1 ]; then
    echo "[1/5] Controllo aggiornamenti via Git..."
    if git fetch origin &> /dev/null; then
        BEHIND_COUNT=$(git rev-list HEAD..origin/main --count 2>/dev/null)
        if [ "${BEHIND_COUNT:-0}" -gt 0 ]; then
            echo "[INFO] Aggiornamento Git rilevato ($BEHIND_COUNT commit). Sincronizzazione..."
            git reset --hard origin/main
            git clean -fd
            NEEDS_FULL_REBUILD=1
        else
            echo "[INFO] Codice già aggiornato (Git)."
        fi
    else
        echo "[INFO] GitHub non raggiungibile. Procedo offline."
    fi
else
    echo "[1/5] Git non trovato. Controllo SMART via GitHub API..."
    LOCAL_SHA="none"
    [ -f .last_commit ] && LOCAL_SHA=$(cat .last_commit)

    REMOTE_SHA=$(curl -s "$API_URL" | grep -m 1 '"sha":' | cut -d'"' -f4)

    if [ -z "$REMOTE_SHA" ]; then
        echo "[INFO] Impossibile verificare aggiornamenti (offline)."
    elif [ "$REMOTE_SHA" != "$LOCAL_SHA" ]; then
        echo "[INFO] Nuova versione rilevata su GitHub. Download ZIP..."
        curl -L "$REPO_URL/archive/refs/heads/main.zip" -o update.zip
        unzip -q update.zip -d temp_update
        cp -rf temp_update/Iterative-1D-Gasdynamic-Solver-main/* .
        rm -rf update.zip temp_update
        echo "$REMOTE_SHA" > .last_commit
        echo "[INFO] Aggiornamento completato."
        NEEDS_FULL_REBUILD=1
    else
        echo "[INFO] Codice già aggiornato (SMART ZIP)."
    fi
fi

# --- SEZIONE BACKEND ---
echo "[2/5] Gestione dipendenze Python..."
cd backend || exit
if [ "$NEEDS_FULL_REBUILD" -eq 1 ]; then
    python3 -m pip install --upgrade --force-reinstall -r requirements.txt
else
    python3 -m pip install -r requirements.txt
fi
cd ..

# --- SEZIONE FRONTEND ---
echo "[3/5] Gestione moduli Node.js..."
cd frontend || exit

FRONTEND_BROKEN=0
[ ! -f "node_modules/.bin/vite" ] && FRONTEND_BROKEN=1
[ "$NEEDS_FULL_REBUILD" -eq 1 ] && FRONTEND_BROKEN=1

if [ "$FRONTEND_BROKEN" -eq 1 ]; then
    echo "[INFO] Ripristino moduli frontend..."
    rm -rf node_modules
    npm install
else
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
(cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000) &
(cd frontend && npm run dev) &

# --- ATTESA E BROWSER ---
echo "[5/5] In attesa che i server siano pronti..."
sleep 8

if [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:5173
else
    xdg-open http://localhost:5173 || echo "Apri manualmente: http://localhost:5173"
fi

echo ""
echo "==================================================="
echo "    SYSTEM READY!" 
echo "==================================================="
echo ""

wait
