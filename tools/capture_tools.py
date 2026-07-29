"""Reference-frame capture tools backed by documented Resolve exports."""

from typing import Any

from .context import Services


def register(mcp: Any, services: Services) -> None:
    @mcp.tool()
    def capture_current_frame(
        output_name: str | None = None,
        output_format: str = "png",
        include_metadata: bool = True,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Export the current Resolve timeline frame and matching JSON metadata."""
        return services.captures.capture_current(
            output_name, output_format, include_metadata, overwrite
        )

    @mcp.tool()
    def capture_clip_reference(
        clip_identifier: str,
        frame_strategy: str = "middle",
        custom_frame: int | None = None,
        output_name: str | None = None,
        output_format: str = "png",
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Export a frame from an explicit clip, restoring the original playhead afterward."""
        return services.captures.capture_clip(
            clip_identifier,
            frame_strategy,  # type: ignore[arg-type]
            custom_frame,
            output_name,
            output_format,
            overwrite,
        )

    @mcp.tool()
    def capture_before_after_reference(
        before_reference: str,
        after_reference: str,
        output_name: str | None = None,
        create_side_by_side: bool = True,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Preserve two genuine exported frames and optionally combine them side by side."""
        return services.captures.compare(
            before_reference,
            after_reference,
            output_name,
            create_side_by_side,
            overwrite,
        )

    @mcp.tool()
    def list_captured_references() -> list[dict[str, Any]]:
        """List generated capture/comparison artifacts with absolute paths."""
        return services.captures.list_references()

    @mcp.tool()
    def open_capture_folder() -> dict[str, str]:
        """Open the generated capture directory with the platform file manager."""
        return services.captures.open_folder()

    @mcp.tool()
    def delete_captured_reference(reference: str) -> dict[str, Any]:
        """Delete one generated artifact and paired capture metadata when present."""
        return services.captures.delete_reference(reference)
