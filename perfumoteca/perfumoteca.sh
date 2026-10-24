#!/usr/bin/env bash
# Abre a Perfumoteca no Mac/Linux: ./perfumoteca.sh
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "Primeira execução: instalando, aguarde alguns minutos..."
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
  .venv/bin/python -m playwright install chromium
fi
exec .venv/bin/python main.py
