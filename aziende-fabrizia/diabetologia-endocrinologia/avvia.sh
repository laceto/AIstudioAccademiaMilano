#!/usr/bin/env bash
# Avvio Studio Digitale — Dott.ssa Fabrizia Aceto
# Uso: ./avvia.sh
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Carica .env se esiste
if [ -f ".env" ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Installa dipendenze se mancanti
if ! python -c "import streamlit" 2>/dev/null; then
  echo "Installazione dipendenze..."
  pip install -q -r requirements.txt
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   Studio Digitale — Dott.ssa Fabrizia Aceto  ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
streamlit run app.py --server.headless false
