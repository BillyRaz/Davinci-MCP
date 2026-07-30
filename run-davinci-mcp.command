#!/bin/zsh

PROJECT_DIR="${0:A:h}"
PYTHON_PATH="$PROJECT_DIR/.venv/bin/python"
OUTPUT_ROOT="${DAVINCI_MCP_OUTPUT_DIR:-$HOME/Library/Application Support/DavinciMCP}"
LOG_PATH="$OUTPUT_ROOT/logs/davinci-mcp-$(date -u +%Y%m%dT%H%M%SZ).log"

export RESOLVE_SCRIPT_API="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
export RESOLVE_SCRIPT_LIB="/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$RESOLVE_SCRIPT_API/Modules"
export DAVINCI_MCP_OUTPUT_DIR="$OUTPUT_ROOT"

mkdir -p \
  "$OUTPUT_ROOT/captures" \
  "$OUTPUT_ROOT/comparisons" \
  "$OUTPUT_ROOT/validation" \
  "$OUTPUT_ROOT/logs" \
  "$OUTPUT_ROOT/reports" \
  "$OUTPUT_ROOT/presets" \
  "$OUTPUT_ROOT/cache"

if [[ ! -x "$PYTHON_PATH" ]]; then
  print -u2 "DaVinci Resolve MCP cannot start: missing $PYTHON_PATH"
  print -u2 "Run \"$PROJECT_DIR/setup-davinci-mcp.command\" first."
  if [[ -t 0 ]]; then
    print -u2 "Press any key to close this window."
    read -k 1
  fi
  exit 1
fi

print -u2 "Starting DaVinci Resolve MCP"
print -u2 "Server: $PROJECT_DIR/server.py"
print -u2 "Python: $PYTHON_PATH"
print -u2 "Output: $OUTPUT_ROOT"
print -u2 "Log: $LOG_PATH"
print -u2 "Resolve must be open with local External scripting enabled for live tools."

"$PYTHON_PATH" "$PROJECT_DIR/server.py" 2> >(tee -a "$LOG_PATH" >&2)
exit_status=$?

if (( exit_status != 0 )); then
  print -u2 "DaVinci Resolve MCP exited with status $exit_status. See: $LOG_PATH"
  if [[ -t 0 ]]; then
    print -u2 "Press any key to close this window."
    read -k 1
  fi
fi
exit "$exit_status"
