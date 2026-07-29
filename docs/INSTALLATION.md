# Installation guide

See the repository [README](../README.md) for the complete Windows-first guide,
MCP client examples, platform paths, and troubleshooting.

## Requirements

- Windows 11 (primary), macOS Apple Silicon/Intel, or Linux (best effort)
- Python 3.12+
- DaVinci Resolve; external live scripting may require Resolve Studio
- An MCP client that supports stdio servers

Use the platform setup launcher from a writable clone:

```powershell
# Windows
.\setup-davinci-mcp.ps1
```

```zsh
# macOS
./setup-davinci-mcp.command
```

```sh
# Linux
./setup-davinci-mcp.sh
```

Each launcher creates `.venv`, installs `.[dev]`, generates the user
`config.toml`, and runs tests, Ruff, and offline validation. Resolve preferences
are never changed automatically.

For live tools, open Resolve with a project and timeline and enable supported
local External scripting. Stdio stdout is reserved for MCP protocol messages.
