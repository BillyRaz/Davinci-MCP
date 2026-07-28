"""Read-only connection, project, clip, and media MCP tools."""

from typing import Any

from .context import Services


def register(mcp: Any, services: Services) -> None:
    @mcp.tool()
    def connect_to_resolve(force: bool = False) -> dict[str, Any]:
        """Connect to running Resolve Studio and return product/project context."""
        services.connection.connect(force=force)
        return services.connection.status()

    @mcp.tool()
    def current_project() -> dict[str, Any]:
        """Return the active project's identity, timeline count, and render state."""
        return services.projects.current()

    @mcp.tool()
    def current_timeline() -> dict[str, Any]:
        """Return active timeline bounds, playhead, and track counts."""
        return services.timelines.current()

    @mcp.tool()
    def inspect_clip() -> dict[str, Any]:
        """Inspect the current clip's metadata; image-scope analysis is not API-accessible."""
        metadata = services.clips.current()
        metadata["analysis_availability"] = (
            "Resolve metadata is available. Numerical scopes/exposure/noise/skin analysis "
            "is not exposed by the official scripting API."
        )
        return metadata

    @mcp.tool()
    def inspect_media_pool(include_clips: bool = True) -> dict[str, Any]:
        """Return the recursive media-pool bin tree, optionally including clip metadata."""
        return services.media.tree(include_clips)

    @mcp.tool()
    def search_clips(query: str) -> list[dict[str, Any]]:
        """Search clip names and properties recursively across all media-pool bins."""
        return services.media.search(query)

    @mcp.tool()
    def selected_clips() -> list[dict[str, Any]]:
        """Return selected Media Pool clips (timeline multi-selection is not API-exposed)."""
        return services.clips.selected()
