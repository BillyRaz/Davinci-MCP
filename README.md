# DaVinci Resolve MCP

A modular stdio MCP server for DaVinci Resolve on macOS. It uses Blackmagic
Design's documented `DaVinciResolveScript` module and filesystem operations
exclusively. It never simulates clicks, captures the macOS screen, uses OCR, or
claims unsupported Resolve API capabilities.

Server location:

```text
/Applications/DaVinci Resolve/davinci-mcp
```

## Quick Start

First-time setup:

```bash
cd "/Applications/DaVinci Resolve/davinci-mcp"
./setup-davinci-mcp.command
```

Then start the stdio server:

```bash
./run-davinci-mcp.command
```

The launchers never change Resolve preferences and never install anything
silently.

## First-Time Setup

Requirements:

- macOS on Apple Silicon or Intel
- Python 3.12
- DaVinci Resolve with external scripting support
- an MCP client supporting stdio

The setup launcher creates `.venv`, installs the runtime and development
dependencies, then runs pytest, Ruff, and offline validation:

```text
/Applications/DaVinci Resolve/davinci-mcp/setup-davinci-mcp.command
```

Equivalent manual commands:

```bash
cd "/Applications/DaVinci Resolve/davinci-mcp"
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python scripts/offline_validate.py
```

The `dev` extra is required for pytest, Ruff, and mypy. Runtime-only installation
can use `.venv/bin/python -m pip install -e .`.

## Running the Server

Main launcher:

```text
/Applications/DaVinci Resolve/davinci-mcp/run-davinci-mcp.command
```

The launcher resolves its own directory safely, checks `.venv/bin/python`,
creates all output folders, exports Blackmagic's official environment
variables, prints the log path, and preserves stdio for MCP. It does not install
packages.

An MCP client should normally execute `.venv/bin/python` and `server.py`
directly, as shown below.

## Running by Double-Click

Double-click either:

```text
/Applications/DaVinci Resolve/davinci-mcp/run-davinci-mcp.command
~/Desktop/Run DaVinci MCP.command
```

The Desktop launcher only forwards to the main launcher. A `.command` window is
useful for diagnostics, but a configured MCP client is needed to call tools.
When startup fails in an interactive Terminal, the window waits for a keypress.

## Connecting Codex

Codex reads personal configuration from:

```text
~/.codex/config.toml
```

Add this table while preserving every existing setting and MCP server:

```toml
[mcp_servers.davinci-resolve]
command = "/Applications/DaVinci Resolve/davinci-mcp/.venv/bin/python"
args = ["/Applications/DaVinci Resolve/davinci-mcp/server.py"]

[mcp_servers.davinci-resolve.env]
DAVINCI_MCP_LOG_LEVEL = "INFO"
DAVINCI_MCP_OUTPUT_DIR = "/Applications/DaVinci Resolve/davinci-mcp/output"
RESOLVE_SCRIPT_API = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
RESOLVE_SCRIPT_LIB = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
PYTHONPATH = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"
```

A trusted repository can instead use a project-local `.codex/config.toml`.
Inspect either file before editing it; do not replace unrelated configuration.

For a generic stdio client using JSON, place this object in that client's
documented MCP configuration file:

```json
{
  "mcpServers": {
    "davinci-resolve": {
      "command": "/Applications/DaVinci Resolve/davinci-mcp/.venv/bin/python",
      "args": [
        "/Applications/DaVinci Resolve/davinci-mcp/server.py"
      ],
      "env": {
        "DAVINCI_MCP_LOG_LEVEL": "INFO",
        "DAVINCI_MCP_OUTPUT_DIR": "/Applications/DaVinci Resolve/davinci-mcp/output",
        "RESOLVE_SCRIPT_API": "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting",
        "RESOLVE_SCRIPT_LIB": "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so",
        "PYTHONPATH": "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"
      }
    }
  }
}
```

Paths containing spaces remain single JSON strings: `command` and each `args`
element are separate values. Generic clients choose their own configuration
location; consult that client's documentation rather than guessing a filename.

## Screenshot and Reference Capture

These are Resolve-exported reference frames, not operating-system screenshots.
The installed API's documented `Project.ExportCurrentFrameAsStill(filePath)` is
the primary capture method.

- `capture_current_frame` exports the active timeline frame and JSON metadata.
- `capture_clip_reference` finds a clip by Resolve unique ID or exact name,
  temporarily moves the playhead to `current`, `first`, `middle`, `last`, or a
  `custom` timeline frame, exports it, and restores the original playhead.
- `capture_before_after_reference` requires two already-exported images. It
  preserves genuine before/after files and optionally uses Pillow to place them
  side by side. It never invents a missing before frame.
- `list_captured_references` reports every file with its absolute path.
- `open_capture_folder` opens the capture folder through the macOS `open`
  filesystem command.
- `delete_captured_reference` deletes only an artifact resolved beneath the
  configured output root.

Side-by-side reports may include a mean absolute RGB difference. This is a
technical image-change measurement, not pixel-level color validation or an
artistic-quality judgment.

Gallery `GrabStill`, `ExportStills`, and `DeleteStills` are capability-checked
where available. A one-frame render is not started by validation and is never
started without an explicit capture request.

## Validation

Read-only validation tools:

```text
validate_resolve_connection
validate_current_project
validate_current_timeline
validate_current_clip
validate_capture_support
validate_grade_application
validate_render_configuration
run_full_validation
get_latest_validation_report
```

Statuses are `passed`, `warning`, `failed`, `skipped`, or `unsupported`.
Unsupported public API features are not failures. Each item includes its check
name, message, technical detail, suggested fix, and UTC timestamp.

Offline validation:

```bash
.venv/bin/python scripts/offline_validate.py
```

Optional read-only live validation:

```bash
.venv/bin/python scripts/live_validate.py
```

Live validation does not apply grades, export frames, start renders, move the
playhead, or modify the timeline. `validate_grade_application` checks only
observable state supplied after a real operation: the DRX exists, the operation
reported success, the target still exists, version information where exposed,
and genuine before/after artifacts exist.

## Output File Locations

Default locations:

```text
Generated captures:
/Applications/DaVinci Resolve/davinci-mcp/output/captures

Comparisons:
/Applications/DaVinci Resolve/davinci-mcp/output/comparisons

Validation reports:
/Applications/DaVinci Resolve/davinci-mcp/output/validation

Logs:
/Applications/DaVinci Resolve/davinci-mcp/output/logs

Additional reports:
/Applications/DaVinci Resolve/davinci-mcp/output/reports
```

Set `DAVINCI_MCP_OUTPUT_DIR` to override the common output root. Every tool that
creates a file returns its exact absolute path. Full validation writes:

```text
output/validation/latest-validation.json
output/validation/latest-validation.md
output/validation/validation-<UTC timestamp>.json
output/validation/validation-<UTC timestamp>.md
```

## Resolve Must Be Open

Resolve must be running with a project and timeline for live inspection or
capture. In Resolve, enable local external scripting under:

```text
DaVinci Resolve > Preferences > System > General > External scripting
```

Restart Resolve if that preference changed. Offline tests and validation do not
need Resolve.

## Free vs Studio limitations

API availability and scripting permissions vary by Resolve edition and version.
This server feature-checks installed proxy objects and returns `unsupported`
when a documented method is absent. Studio-only AI features are not used.
External scripting may require Resolve Studio depending on the installed
Resolve release and licensing.

The official API does not create or rewire color nodes, change node labels,
report timeline multi-selection, apply an in-memory Gallery still as a grade,
or expose numerical scopes/pixel statistics. Authored `.drx` templates are used
for grading through documented `Graph.ApplyGradeFromDRX`.

## Troubleshooting

- **Missing `.venv`:** run `setup-davinci-mcp.command`.
- **Module cannot load:** verify the official paths below and the installed
  `DaVinciResolveScript.py`.
- **No scripting handle:** open Resolve and enable local External scripting.
- **No project/timeline:** open both before live validation or capture.
- **No clip:** move the playhead over a video clip or use its unique ID.
- **Capture rejected:** confirm the project/timeline is active and choose a
  writable output directory.
- **Duplicate output:** choose another name or pass `overwrite=true`.
- **No registered look:** register an existing `.drx` using
  `register_powergrade`.
- **Protocol output looks unreadable:** stdout is reserved for MCP messages;
  inspect `output/logs`.

## macOS permissions

The project needs write permission only for its output directory and local
catalog. `open_capture_folder` asks Finder to open a directory, but capture does
not use Screen Recording, Accessibility, camera, microphone, AppleScript,
Automator, or mouse/keyboard control. The project does not alter macOS security
settings.

## Official Resolve environment variables

Blackmagic's installed scripting README defines:

```bash
export RESOLVE_SCRIPT_API="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
export RESOLVE_SCRIPT_LIB="/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$RESOLVE_SCRIPT_API/Modules"
```

The server accepts `RESOLVE_SCRIPT_API` as either this official Scripting root
or the final `Modules` directory.

## Existing capabilities

The server also supports project/timeline/clip inspection, media-pool search,
timeline markers, documented color-node inspection and enable state, ASC CDL,
DRX grade application, Gallery album/still export, render configuration and
queue control, and explicit clip-addressed batch workflows.

See [Architecture](docs/ARCHITECTURE.md), [tool reference](docs/TOOLS.md),
[installation](docs/INSTALLATION.md), and [extension guide](docs/EXTENDING.md).
