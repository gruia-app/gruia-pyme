#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
fi

python3 cli.py init
python3 -m unittest discover -s tests -v
python3 cli.py doctor
echo "Listo. Arranca con: python3 run.py"
