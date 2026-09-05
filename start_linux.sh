#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -f .env ]]; then
  echo "[ERROR] Copy .env.example to .env and configure it first."
  exit 1
fi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
exec python run.py
