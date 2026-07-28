"""Timeline, clip, marker, and batch MCP tools."""

from typing import Any

from resolve.models import MarkerInput

from .context import Services


def register(mcp: Any, services: Services) -> None:
    @mcp.tool()
    def list_timelines() -> list[dict[str, Any]]:
        """List all timelines and indicate which one is active."""
        return services.projects.timelines()

    @mcp.tool()
    def switch_timeline(name: str) -> dict[str, Any]:
        """Make the uniquely named project timeline current."""
        return services.projects.switch_timeline(name)

    @mcp.tool()
    def list_clips(track_index: int | None = None) -> list[dict[str, Any]]:
        """List addressable video timeline clips, optionally on one 1-based track."""
        return services.timelines.clips(track_index)

    @mcp.tool()
    def current_playhead() -> dict[str, str]:
        """Return the active timeline playhead timecode."""
        return {"timecode": services.connection.timeline().GetCurrentTimecode()}

    @mcp.tool()
    def jump_to_timecode(timecode: str) -> dict[str, str]:
        """Move the timeline playhead to an HH:MM:SS:FF timecode."""
        return services.timelines.jump(timecode)

    @mcp.tool()
    def current_clip() -> dict[str, Any]:
        """Return the current video timeline item under the playhead."""
        return services.clips.current()

    @mcp.tool()
    def list_markers() -> list[dict[str, Any]]:
        """List active timeline markers with frame offsets and metadata."""
        return services.markers.list()

    @mcp.tool()
    def add_marker(
        frame: int,
        color: str = "Blue",
        name: str = "",
        note: str = "",
        duration: int = 1,
        custom_data: str = "",
    ) -> dict[str, Any]:
        """Add a marker at a zero-based frame offset in the active timeline."""
        return services.markers.add(
            MarkerInput(
                frame=frame,
                color=color,
                name=name,
                note=note,
                duration=duration,
                custom_data=custom_data,
            )
        )

    @mcp.tool()
    def delete_marker(frame: int) -> dict[str, int]:
        """Delete the active timeline marker at a frame offset."""
        return services.markers.delete(frame)

    @mcp.tool()
    def jump_marker(frame: int) -> dict[str, Any]:
        """Move the playhead to a timeline marker identified by frame offset."""
        return services.markers.jump(frame)

    @mcp.tool()
    def copy_grade(
        source_track: int,
        source_item: int,
        targets: list[dict[str, int]],
    ) -> dict[str, int]:
        """Copy a source clip's current grade to explicitly addressed target clips."""
        return services.clips.copy_grade(source_track, source_item, targets)

    @mcp.tool()
    def batch_rename_clips(items: list[dict[str, Any]]) -> dict[str, Any]:
        """Rename timeline clips. Each item needs track_index, item_index, and name."""
        changed = []
        for entry in items:
            item = services.timelines.item(entry["track_index"], entry["item_index"])
            if not item.SetName(entry["name"]):
                raise RuntimeError(f"Resolve could not rename clip to {entry['name']!r}")
            changed.append(entry)
        return {"renamed": len(changed), "items": changed}
