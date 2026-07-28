"""Read-only validation tools and report access."""

from typing import Any

from .context import Services


def register(mcp: Any, services: Services) -> None:
    @mcp.tool()
    def validate_resolve_connection() -> dict[str, Any]:
        """Check the live Resolve API connection without changing Resolve state."""
        return services.validation.connection_check()

    @mcp.tool()
    def validate_current_project() -> dict[str, Any]:
        """Check that a current Resolve project is available."""
        return services.validation.project_check()

    @mcp.tool()
    def validate_current_timeline() -> dict[str, Any]:
        """Check that a current Resolve timeline and playhead are available."""
        return services.validation.timeline_check()

    @mcp.tool()
    def validate_current_clip() -> dict[str, Any]:
        """Check the timeline clip under the playhead."""
        return services.validation.clip_check()

    @mcp.tool()
    def validate_capture_support() -> dict[str, Any]:
        """Inspect official frame-export, Gallery, and render capabilities without capture."""
        return services.validation.capture_support_check()

    @mcp.tool()
    def validate_grade_application(
        track_index: int,
        item_index: int,
        drx_path: str,
        operation_succeeded: bool,
        before_reference: str | None = None,
        after_reference: str | None = None,
    ) -> dict[str, Any]:
        """Validate supported observable grade state; makes no color-quality claim."""
        return services.validation.grade_application_check(
            track_index,
            item_index,
            drx_path,
            operation_succeeded,
            before_reference,
            after_reference,
        )

    @mcp.tool()
    def validate_render_configuration() -> dict[str, Any]:
        """Inspect supported render API methods without changing settings or rendering."""
        return services.validation.render_configuration_check()

    @mcp.tool()
    def run_full_validation(live: bool = True) -> dict[str, Any]:
        """Run offline plus optional read-only live checks and write JSON/Markdown reports."""
        return services.validation.run_full(live)

    @mcp.tool()
    def get_latest_validation_report() -> dict[str, Any]:
        """Return the latest persisted validation report and its absolute path."""
        return services.validation.latest()

