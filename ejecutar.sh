#!/bin/bash
# Bashkar Station v10 — Lanzador Linux/macOS
cd "$(dirname "$0")"

if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 no encontrado."
    echo "Instala con: sudo apt install python3 python3-pip"
    exit 1
fi

if [ ! -f ".installed" ]; then
    echo "Primer inicio — instalando dependencias..."
    python3 instalar.py
    touch .installed
fi

python3 app.py
