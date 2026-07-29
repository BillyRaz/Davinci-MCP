#!/usr/bin/env sh
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/scripts/offline_validate.py"
