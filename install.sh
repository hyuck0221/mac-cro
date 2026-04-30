#!/usr/bin/env bash
set -euo pipefail

APP_NAME="mac-cro"
REPO_URL="${MAC_CRO_REPO_URL:-https://github.com/shimhyuck/mac-cro.git}"
APP_DIR="${MAC_CRO_HOME:-$HOME/.mac-cro}"
BIN_DIR="${MAC_CRO_BIN_DIR:-$HOME/.local/bin}"
LAUNCHER="$BIN_DIR/$APP_NAME"

need_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Error: $1 is required."
        exit 1
    fi
}

need_command git
need_command python3

mkdir -p "$BIN_DIR"

if [ -d "$APP_DIR/.git" ]; then
    echo "Updating $APP_NAME..."
    git -C "$APP_DIR" pull --ff-only
else
    if [ -e "$APP_DIR" ]; then
        echo "Error: $APP_DIR already exists and is not a git repository."
        echo "Move it away or set MAC_CRO_HOME to another directory."
        exit 1
    fi

    echo "Installing $APP_NAME..."
    git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"

echo "Setting up Python environment..."
python3 -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt

cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
exec "$APP_DIR/.venv/bin/python" "$APP_DIR/macro_recorder.py" "\$@"
EOF

chmod +x "$LAUNCHER"

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        ZSHRC="$HOME/.zshrc"
        PROFILE="$HOME/.profile"
        EXPORT_LINE="export PATH=\"\$HOME/.local/bin:\$PATH\""

        if [ -n "${ZSH_VERSION:-}" ] || [ "$(basename "${SHELL:-}")" = "zsh" ]; then
            TARGET_RC="$ZSHRC"
        else
            TARGET_RC="$PROFILE"
        fi

        touch "$TARGET_RC"
        if ! grep -Fq "$EXPORT_LINE" "$TARGET_RC"; then
            {
                echo ""
                echo "# mac-cro"
                echo "$EXPORT_LINE"
            } >> "$TARGET_RC"
            echo "Added $BIN_DIR to PATH in $TARGET_RC."
        fi
        ;;
esac

echo ""
echo "$APP_NAME installed successfully."
echo "Run it with:"
echo "  $APP_NAME"
echo ""
echo "If the command is not found in this terminal, run:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo "or open a new terminal window."
