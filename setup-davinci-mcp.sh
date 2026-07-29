#!/usr/bin/env sh
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON=${DAVINCI_MCP_PYTHON:-$(command -v python3.12 || true)}
[ -n "$PYTHON" ] || { echo "Python 3.12 is required." >&2; exit 1; }
[ -x "$PROJECT_DIR/.venv/bin/python" ] || "$PYTHON" -m venv "$PROJECT_DIR/.venv"
cd "$PROJECT_DIR"
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python scripts/platform_info.py --create-config
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python scripts/offline_validate.py
