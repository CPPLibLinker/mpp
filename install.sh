#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BIN_DIR="${HOME}/.local/bin"
TARGET="${BIN_DIR}/mpp"
SOURCE="${SCRIPT_DIR}/bin/mpp"

mkdir -p "$BIN_DIR"
ln -sfn "$SOURCE" "$TARGET"
chmod +x "$SOURCE"

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *)
    echo "warning: $BIN_DIR is not in PATH"
    echo "add this to your shell profile:"
    echo "  export PATH=\"$BIN_DIR:\$PATH\""
    ;;
esac

echo "installed mpp -> $TARGET"
echo "run: mpp --version"
