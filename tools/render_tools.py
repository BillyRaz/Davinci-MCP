"""Render queue MCP tools."""

from typing import Any

from resolve.models import RenderSettings

from .context import Services


def register(mcp: Any, services: Services) -> None:
    @mcp.tool()
    def list_render_presets() -> list[Any]:
        """List render presets visible to the active project."""
        return services.renders.presets()

    @mcp.tool()
    def create_render_preset(
        name: str,
        target_dir: str,
        custom_name: str = "",
        format: str | None = None,
        codec: str | None = None,
        mode: str = "single",
        export_video: bool = True,
        export_audio: bool = True,
    ) -> dict[str, Any]:
        """Configure supported render settings and save them as a named preset."""
        settings = RenderSettings(
            target_dir=target_dir,
            custom_name=custom_name,
            format=format,
            codec=codec,
            mode=mode,
            export_video=export_video,
            export_audio=export_audio,
        )
        configured = services.renders.configure(settings)
        saved = services.renders.save_preset(name)
        return {**configured, **saved}

    @mcp.tool()
    def add_render_job(
        target_dir: str,
        custom_name: str = "",
        preset: str | None = None,
        format: str | None = None,
        codec: str | None = None,
        mode: str = "single",
        export_video: bool = True,
        export_audio: bool = True,
    ) -> dict[str, Any]:
        """Configure the current timeline and append a job to Resolve's render queue."""
        configured = services.renders.configure(
            RenderSettings(
                target_dir=target_dir,
                custom_name=custom_name,
                preset=preset,
                format=format,
                codec=codec,
                mode=mode,
                export_video=export_video,
                export_audio=export_audio,
            )
        )
        return {**configured, **services.renders.add_job()}

    @mcp.tool()
    def list_render_jobs() -> list[Any]:
        """List queued and completed render jobs."""
        return services.renders.jobs()

    @mcp.tool()
    def start_render(job_ids: list[str] | None = None) -> dict[str, Any]:
        """Start selected render job IDs, or all queued jobs when omitted."""
        return services.renders.start(job_ids)

    @mcp.tool()
    def monitor_render(job_id: str | None = None) -> dict[str, Any]:
        """Return one job's completion/status or the overall queue state."""
        return services.renders.status(job_id)
