#!/usr/bin/env sh
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON="$PROJECT_DIR/.venv/bin/python"
[ -x "$PYTHON" ] || { echo "Missing .venv; run setup-davinci-mcp.sh first." >&2; exit 1; }
exec "$PYTHON" "$PROJECT_DIR/server.py"
