#!/usr/bin/env bash
set -euo pipefail

PYTHON="${PYTHON:-python3}"
cd "$(dirname "$0")"

echo "========================================"
echo "   Stock Tracker"
echo "========================================"
echo ""
echo "1) Collect data"
echo "2) Start dashboard"
echo "3) Collect + start dashboard"
echo ""
read -rp "Choose [1-3]: " choice

case "$choice" in
  1)
    echo "Collecting data..."
    $PYTHON collector.py
    echo "Done."
    ;;
  2)
    echo "Starting dashboard..."
    $PYTHON -m streamlit run dashboard.py
    ;;
  3)
    echo "Collecting data..."
    $PYTHON collector.py
    echo "Starting dashboard..."
    $PYTHON -m streamlit run dashboard.py
    ;;
  *)
    echo "Invalid choice"
    exit 1
    ;;
esac
