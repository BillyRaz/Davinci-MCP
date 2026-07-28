"""Gallery and still MCP tools."""

from typing import Any

from .context import Services


def register(mcp: Any, services: Services) -> None:
    @mcp.tool()
    def list_gallery_albums(powergrades: bool = False) -> list[dict[str, Any]]:
        """List Gallery still albums or PowerGrade albums."""
        return services.gallery.albums(powergrades)

    @mcp.tool()
    def list_stills(
        album_index: int, powergrades: bool = False
    ) -> list[dict[str, Any]]:
        """List still labels and stable-in-call indices in a Gallery album."""
        return services.gallery.stills(album_index, powergrades)

    @mcp.tool()
    def save_powergrade(label: str = "") -> dict[str, Any]:
        """Grab a still from the current Color-page clip into the current album."""
        return services.gallery.grab(label)

    @mcp.tool()
    def export_still(
        album_index: int,
        still_indices: list[int],
        folder: str,
        prefix: str,
        format: str = "drx",
        powergrades: bool = False,
    ) -> dict[str, Any]:
        """Export selected Gallery stills, including DRX for later grade application."""
        return services.gallery.export(
            album_index, still_indices, folder, prefix, format, powergrades
        )
