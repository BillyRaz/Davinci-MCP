#!/bin/zsh

set -e
PROJECT_DIR="${0:A:h}"
PYTHON_312="${DAVINCI_MCP_PYTHON:-$(command -v python3.12)}"
OUTPUT_ROOT="${DAVINCI_MCP_OUTPUT_DIR:-$HOME/Library/Application Support/DavinciMCP}"

cd "$PROJECT_DIR"

if [[ -z "$PYTHON_312" ]] || [[ ! -x "$PYTHON_312" ]]; then
  print -u2 "Python 3.12 was not found. Install it, then run this setup again."
  exit 1
fi

version="$("$PYTHON_312" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$version" != "3.12" ]]; then
  print -u2 "Expected Python 3.12, found Python $version at $PYTHON_312"
  exit 1
fi

print "Project: $PROJECT_DIR"
print "Python: $PYTHON_312"
if [[ ! -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  print "Creating .venv..."
  "$PYTHON_312" -m venv "$PROJECT_DIR/.venv"
else
  print "Using existing .venv."
fi

print "Installing declared development dependencies..."
"$PROJECT_DIR/.venv/bin/python" -m pip install -e '.[dev]'
"$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/scripts/platform_info.py" --create-config

mkdir -p \
  "$OUTPUT_ROOT/captures" \
  "$OUTPUT_ROOT/comparisons" \
  "$OUTPUT_ROOT/validation" \
  "$OUTPUT_ROOT/logs" \
  "$OUTPUT_ROOT/reports" \
  "$OUTPUT_ROOT/presets" \
  "$OUTPUT_ROOT/cache"

export DAVINCI_MCP_OUTPUT_DIR="$OUTPUT_ROOT"
export RESOLVE_SCRIPT_API="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
export RESOLVE_SCRIPT_LIB="/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$RESOLVE_SCRIPT_API/Modules"

print "Running unit tests..."
"$PROJECT_DIR/.venv/bin/python" -m pytest
print "Running Ruff..."
"$PROJECT_DIR/.venv/bin/python" -m ruff check .
print "Running offline validation..."
"$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/scripts/offline_validate.py"

print
print "Setup complete. Resolve preferences were not changed."
print "Open DaVinci Resolve with a project and timeline for live validation:"
print "  \"$PROJECT_DIR/.venv/bin/python\" \"$PROJECT_DIR/scripts/live_validate.py\""
