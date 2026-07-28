# Extension guide

1. Add Resolve-specific behavior to a focused service under `resolve/`.
2. Validate all user inputs before invoking Resolve.
3. Convert `False`/`None` results into a domain error with useful context.
4. Return only JSON-serializable data; never return a Resolve proxy.
5. Register a thin, typed MCP wrapper in the matching `tools/` module.
6. Add fake-based unit tests and a manual disposable-project integration test.
7. Verify every new method against the installed official scripting README.

Do not fill API gaps with UI automation. If Blackmagic adds a capability in a
future SDK, isolate it behind a feature check and retain a clear fallback error
for earlier versions.

For shot analysis, add an explicitly authorized media-analysis pipeline that
reads exported frames through supported project media paths. Keep it separate
from the Resolve adapter and document that results are estimates. The current
server deliberately performs no implicit exports or pixel analysis.
