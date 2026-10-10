#!/bin/bash
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed. Install it from https://www.python.org/downloads/ and run this again."
  exit 1
fi

if [ ! -f "data/mumbai_air_quality.csv" ]; then
  echo "The file data/mumbai_air_quality.csv was not found."
  echo "Put your CSV in the data folder, then run this again."
  exit 1
fi

if [ ! -f ".venv/installed.flag" ]; then
  echo "First-time setup. This takes a few minutes, only once..."
  python3 -m venv .venv || exit 1
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt || { echo "Install failed. Check your internet."; exit 1; }
  echo done > .venv/installed.flag
fi

.venv/bin/python -m streamlit run app.py
