#!/bin/zsh
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
  echo "Preparando DOMO Content Lab por primera vez..."
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
.venv/bin/python launch.py
