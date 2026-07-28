# Installation guide

## Requirements

- macOS on Apple Silicon or Intel
- DaVinci Resolve Studio 20 or newer
- Python 3.12+
- An MCP client that supports stdio servers

Enable local External scripting in Resolve Preferences, restart Resolve if the
setting changed, and open a project.

Create a virtual environment:

```bash
cd "/Applications/DaVinci Resolve/davinci-mcp"
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -e .
```

Run a protocol server:

```bash
.venv/bin/python server.py
```

Do not expect human-readable stdout: stdio is reserved for MCP messages.

## Troubleshooting

- **Module cannot load:** check `RESOLVE_SCRIPT_API` and the installed
  `Developer/Scripting/Modules/DaVinciResolveScript.py`.
- **No scripting handle:** keep Studio running and verify External scripting.
- **No project/timeline:** open them in Resolve before calling contextual tools.
- **Operation rejected:** confirm the active page/context, valid clip address,
  output folder, render format/codec, or DRX path.
- **Node creation unavailable:** author/export a DRX; this is an API limitation,
  not a missing permission.
