#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$DIR/.venv/bin/python"

if [ ! -x "$PY" ]; then
    if ! command -v python3 >/dev/null 2>&1; then
        echo "python3 is required. Install it from https://www.python.org/downloads/ or Homebrew."
        exit 1
    fi

    echo "Setting up virtual environment..."
    python3 -m venv "$DIR/.venv"
    "$PY" -m pip install --quiet --upgrade pip

    if [ -f "$DIR/requirements.txt" ]; then
        "$PY" -m pip install --quiet -r "$DIR/requirements.txt"
    else
        "$PY" -m pip install --quiet pynput
    fi
fi

exec "$PY" "$DIR/macro_recorder.py"
