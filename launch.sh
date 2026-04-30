#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$DIR/.venv/bin/python"
VERSION_FILE="$DIR/VERSION"
REQ_FILE="$DIR/requirements.txt"
REQ_STAMP="$DIR/.venv/.requirements-installed"
CURRENT_VERSION="unknown"

if [ -f "$VERSION_FILE" ]; then
    CURRENT_VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"
fi

ensure_python_env() {
    NEED_INSTALL=0

    if [ ! -x "$PY" ]; then
        if ! command -v python3 >/dev/null 2>&1; then
            echo "python3 is required. Install it from https://www.python.org/downloads/ or Homebrew."
            exit 1
        fi

        echo "Setting up Python environment..."
        python3 -m venv "$DIR/.venv"
        NEED_INSTALL=1
    fi

    if [ ! -f "$REQ_STAMP" ] || [ "$REQ_FILE" -nt "$REQ_STAMP" ]; then
        NEED_INSTALL=1
    fi

    if [ "$NEED_INSTALL" = "1" ]; then
        "$PY" -m pip install --quiet --upgrade pip
        "$PY" -m pip install --quiet -r "$REQ_FILE"
        touch "$REQ_STAMP"
    fi
}

auto_update() {
    if [ "${MAC_CRO_AUTO_UPDATE:-1}" = "0" ]; then
        return
    fi

    if ! command -v git >/dev/null 2>&1 || [ ! -d "$DIR/.git" ]; then
        return
    fi

    cd "$DIR"

    if ! git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
        return
    fi

    echo "Checking for mac-cro updates..."

    if ! git fetch --quiet; then
        echo "Update check failed. Starting mac-cro $CURRENT_VERSION."
        return
    fi

    LOCAL_REV="$(git rev-parse HEAD)"
    REMOTE_REV="$(git rev-parse '@{u}')"

    if [ "$LOCAL_REV" = "$REMOTE_REV" ]; then
        echo "mac-cro $CURRENT_VERSION is up to date."
        return
    fi

    echo "Updating mac-cro..."

    if git pull --ff-only; then
        chmod +x "$DIR/launch.sh" "$DIR/run.sh" 2>/dev/null || true
        ensure_python_env
        if [ -f "$VERSION_FILE" ]; then
            NEW_VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"
            echo "Updated mac-cro $CURRENT_VERSION -> $NEW_VERSION."
        else
            echo "Updated mac-cro."
        fi
    else
        echo "Automatic update failed. Starting installed version $CURRENT_VERSION."
    fi
}

auto_update
ensure_python_env

exec "$PY" "$DIR/macro_recorder.py" "$@"
