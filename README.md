# DaVinci Resolve MCP

A 64-tool stdio MCP server for DaVinci Resolve’s documented scripting API. Windows
11 is the primary platform, macOS is supported, and Linux support is best effort.
The project does not use UI automation, OCR, simulated input, or undocumented
Resolve methods.

## Windows Quick Start

Requirements: Windows 11, Python 3.12 or newer, Git, and DaVinci Resolve. Live
external control may require Resolve Studio, depending on the installed edition
and Blackmagic’s scripting support.

Use a writable source location—not `Program Files`:

```powershell
cd "$env:USERPROFILE\Documents\GitHub"
git clone https://github.com/BillyRaz/Davinci-MCP.git
cd Davinci-MCP
.\setup-davinci-mcp.ps1
```

Setup prefers `py -3.12`, falls back to a compatible `python`, creates `.venv`,
installs `.[dev]`, generates the user config, and runs pytest, Ruff, and offline
validation. It never installs packages silently, requests Administrator access,
or changes execution policy globally.

Run and validate:

```powershell
.\run-davinci-mcp.ps1
.\validate-davinci-mcp.ps1
.\validate-davinci-mcp.ps1 -Live
```

The `.cmd` wrappers provide equivalent double-click entry points. The live option
is read-only and should only be used with Resolve Studio open. Resolve Free
external scripting limitations are reported as warnings/unsupported capability,
not MCP defects.

To create an optional Desktop shortcut:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\create_windows_shortcut.ps1
```

The script only creates `Run DaVinci MCP.lnk`; it does not alter security settings.

## Windows Codex and MCP Configuration

Keep executable and argument as separate values. Replace the example clone path:

```json
{
  "mcpServers": {
    "davinci-resolve": {
      "command": "C:\\Users\\YOUR_NAME\\Documents\\GitHub\\Davinci-MCP\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\Users\\YOUR_NAME\\Documents\\GitHub\\Davinci-MCP\\server.py"
      ]
    }
  }
}
```

For Codex, add the server to the MCP configuration used by your Codex installation;
inspect and preserve existing servers before editing it. Generic stdio and VS
Code-compatible clients can use the same `command`/`args` object.

Windows troubleshooting:

- “Missing `.venv`”: run `.\setup-davinci-mcp.ps1`.
- Python not found: install Python 3.12+ with the `py` launcher, then reopen the shell.
- Resolve connection unavailable: open Resolve Studio and enable local External
  scripting in Resolve Preferences. Do not change preferences automatically.
- Permission errors: clone under Documents or Developer, not `Program Files`.
- Paths are discovered from `ProgramFiles`, `ProgramData`, `APPDATA`,
  `LOCALAPPDATA`, and `USERPROFILE`; explicit environment overrides take priority.

## macOS Installation

Existing macOS users can continue using:

```zsh
cd "/Applications/DaVinci Resolve/davinci-mcp"
./setup-davinci-mcp.command
./run-davinci-mcp.command
```

Apple Silicon and Intel are detected automatically. The launcher retains
Blackmagic’s official scripting locations:

```zsh
export RESOLVE_SCRIPT_API="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
export RESOLVE_SCRIPT_LIB="/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$RESOLVE_SCRIPT_API/Modules"
```

`RESOLVE_SCRIPT_API` accepts either the parent `Scripting` directory or its direct
`Modules` directory. A generic/Codex macOS configuration is:

```json
{
  "mcpServers": {
    "davinci-resolve": {
      "command": "/Applications/DaVinci Resolve/davinci-mcp/.venv/bin/python",
      "args": ["/Applications/DaVinci Resolve/davinci-mcp/server.py"]
    }
  }
}
```

## Linux Installation (Best Effort)

Linux discovery checks `/opt/resolve`, `/opt/resolve/Developer/Scripting`, and
common libraries under `/opt/resolve/libs`, while honoring all overrides:

```sh
./setup-davinci-mcp.sh
./run-davinci-mcp.sh
./validate-davinci-mcp.sh
```

Linux paths and launchers are mock-tested, but live Resolve behavior is not claimed
as fully validated.

## Capture Support

Capture tools export genuine Resolve output only:

- `capture_current_frame`
- `capture_clip_reference`
- `capture_before_after_reference`
- `list_captured_references`
- `open_capture_folder`
- `delete_captured_reference`

Capture uses documented current-frame export when exposed, Gallery still
export/delete as a fallback, or a supported temporary one-frame render path. Pillow
is used only to combine already-exported images or calculate technical image-change
metrics. A “before” is never claimed unless it was actually captured first.

Every generated file result includes its absolute path. Metadata includes the
project, timeline, frame/timecode, timestamp, and actual capture method.

## Validation

Offline validation checks Python, dependencies, platform discovery, scripting
paths, native library, writable output, config, presets, and MCP registration.
Live validation additionally inspects the read-only connection/project/timeline/
clip/Gallery/render capabilities. It does not apply grades, start renders, or
change the active timeline.

Reports use `passed`, `warning`, `failed`, `skipped`, and `unsupported`, and are
written as JSON and Markdown with timestamped copies.

## Configuration and Output Paths

Default config:

| Platform | Config |
|---|---|
| Windows | `%APPDATA%\DavinciMCP\config.toml` |
| macOS | `~/Library/Application Support/DavinciMCP/config.toml` |
| Linux | `${XDG_CONFIG_HOME:-~/.config}/davinci-mcp/config.toml` |

Default output root:

| Platform | Output |
|---|---|
| Windows | `%LOCALAPPDATA%\DavinciMCP` |
| macOS | `~/Library/Application Support/DavinciMCP` |
| Linux | `${XDG_DATA_HOME:-~/.local/share}/DavinciMCP` |

Each root contains `captures`, `comparisons`, `validation`, `logs`, `reports`,
`presets`, and `cache`.

Older macOS artifacts at
`/Applications/DaVinci Resolve/davinci-mcp/output` are left untouched. Copy wanted
files manually into the new Application Support subdirectories; no automatic move
or deletion occurs.

Environment variables override TOML configuration:

- `DAVINCI_RESOLVE_HOME`
- `RESOLVE_SCRIPT_API`
- `RESOLVE_SCRIPT_LIB`
- `DAVINCI_MCP_OUTPUT_DIR`
- `DAVINCI_MCP_PRESET_DIR`
- `DAVINCI_MCP_LOG_LEVEL`
- `DAVINCI_MCP_CONNECTION_MODE`
- `DAVINCI_MCP_CAPTURE_FORMAT`
- `DAVINCI_MCP_TEMP_RENDER_DIR`
- `DAVINCI_MCP_CONNECTION_TIMEOUT`
- `DAVINCI_MCP_RENDER_TIMEOUT`

Discovery priority is explicit override, existing discovered installation, known
platform default, then a clear validation failure when the selected path is absent.

## Development and Testing

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python scripts/offline_validate.py
```

On Windows, replace `.venv/bin/python` with
`.venv\Scripts\python.exe`. GitHub Actions runs Python 3.12 tests and Ruff on
Windows, macOS, and Ubuntu without attempting a live Resolve connection.
