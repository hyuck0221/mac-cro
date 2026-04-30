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

print_help() {
    cat <<EOF
mac-cro $CURRENT_VERSION

Usage:
  mac-cro                 Open the app
  mac-cro run             Open the app
  mac-cro upgrade         Update mac-cro to the latest version
  mac-cro update          Same as upgrade
  mac-cro version         Show the installed version
  mac-cro help            Show this help

Environment:
  MAC_CRO_AUTO_UPDATE=0   Skip the startup update check
EOF
}

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

update_repo() {
    MODE="${1:-manual}"

    if ! command -v git >/dev/null 2>&1 || [ ! -d "$DIR/.git" ]; then
        if [ "$MODE" = "manual" ]; then
            echo "Update is only available for git-based installations."
        fi
        return
    fi

    cd "$DIR"

    if ! git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
        if [ "$MODE" = "manual" ]; then
            echo "No upstream branch is configured."
        fi
        return
    fi

    echo "Checking for mac-cro updates..."

    if ! git fetch --quiet; then
        echo "Update check failed."
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
        echo "Update failed. The installed version is still $CURRENT_VERSION."
    fi
}

auto_update() {
    if [ "${MAC_CRO_AUTO_UPDATE:-1}" = "0" ]; then
        return
    fi

    update_repo auto
}

COMMAND="${1:-run}"

case "$COMMAND" in
    help|--help|-h)
        print_help
        exit 0
        ;;
    version|--version|-v)
        echo "$CURRENT_VERSION"
        exit 0
        ;;
    upgrade|update)
        update_repo
        exit 0
        ;;
    run|open|start)
        shift || true
        ;;
    *)
        if [ "$#" -gt 0 ]; then
            echo "Unknown command: $COMMAND"
            echo ""
            print_help
            exit 1
        fi
        ;;
esac

auto_update
ensure_python_env

exec "$PY" "$DIR/macro_recorder.py" "$@"
