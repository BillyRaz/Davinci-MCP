# Architecture

```text
MCP client <-> stdio FastMCP server
                       |
                  tool adapters
                       |
                 service container
                       |
             official Resolve objects
```

`server.py` owns transport and registration only. `tools/` defines the typed MCP
boundary and delegates to services in `resolve/`. The services validate
addresses, convert Resolve failures into domain errors, and avoid leaking
Resolve proxy objects into protocol responses.

`ResolveConnection` imports Blackmagic's module lazily, so discovery and unit
tests work while Resolve is closed. It serializes connection setup with a lock.
Resolve mutations remain synchronous because the official API is synchronous.

## Identity and addressing

Resolve proxy objects are valid only within the current process/context. Tools
therefore return serializable dictionaries. Timeline mutation accepts 1-based
track/item addresses and callers must refresh them after structural edits.

## Error model

Domain errors distinguish connection, not-found, validation, rejected
operation, and unavailable official capability. FastMCP serializes raised
errors as failed tool calls, preserving their actionable messages.

## Safety

The implementation invokes documented scripting methods only. It does not use
AppleScript, accessibility APIs, mouse/keyboard events, computer vision, OCR,
or screenshots. Render and grading operations are never silently retried.
