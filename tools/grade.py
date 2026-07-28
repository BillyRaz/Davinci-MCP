"""Grade application, catalog, batch, and look MCP tools."""

from typing import Any

from resolve.models import GradeTemplate

from .context import Services


def register(mcp: Any, services: Services) -> None:
    @mcp.tool()
    def apply_grade(
        track_index: int, item_index: int, drx_path: str, grade_mode: int = 0
    ) -> dict[str, Any]:
        """Apply a DRX grade to a clip. Modes: 0 none, 1 source TC, 2 start aligned."""
        return services.colors.apply_drx(track_index, item_index, drx_path, grade_mode)

    @mcp.tool()
    def set_cdl(
        track_index: int,
        item_index: int,
        node_index: int,
        slope: str = "1 1 1",
        offset: str = "0 0 0",
        power: str = "1 1 1",
        saturation: float = 1.0,
    ) -> dict[str, Any]:
        """Set ASC CDL values on an existing color node."""
        return services.colors.set_cdl(
            track_index, item_index, node_index, slope, offset, power, saturation
        )

    @mcp.tool()
    def register_powergrade(
        name: str,
        drx_path: str,
        description: str = "",
        category: str = "custom",
        favorite: bool = False,
    ) -> dict[str, Any]:
        """Register or replace a named DRX template in the local grade catalog."""
        return services.grades.register(
            GradeTemplate(
                name=name,
                drx_path=drx_path,
                description=description,
                category=category,
                favorite=favorite,
            )
        )

    @mcp.tool()
    def search_powergrades(
        query: str = "", category: str | None = None
    ) -> list[dict[str, Any]]:
        """Search registered DRX templates by text and optional exact category."""
        return services.grades.search(query, category)

    @mcp.tool()
    def load_powergrade(
        name: str, track_index: int, item_index: int, grade_mode: int = 0
    ) -> dict[str, Any]:
        """Apply a registered PowerGrade DRX template to a timeline clip."""
        return services.grades.apply(name, track_index, item_index, grade_mode)

    @mcp.tool()
    def batch_grade_clips(
        template: str, clips: list[dict[str, int]], grade_mode: int = 0
    ) -> dict[str, Any]:
        """Apply one registered DRX template to explicit timeline clip addresses."""
        return services.workflows.batch_apply(template, clips, grade_mode)

    def look_tool(tool_name: str, look: str, description: str) -> None:
        @mcp.tool(name=tool_name, description=description)
        def create(
            track_index: int, item_index: int, grade_mode: int = 0
        ) -> dict[str, Any]:
            return services.workflows.create(look, track_index, item_index, grade_mode)

    look_tool("create_cinematic_grade", "cinematic", "Apply registered cinematic DRX.")
    look_tool(
        "create_luxury_bridal_grade",
        "luxury_bridal",
        "Apply registered luxury bridal DRX with protected skin and warm golds.",
    )
    look_tool("create_editorial_grade", "editorial", "Apply registered editorial DRX.")
    look_tool("create_dark_moody_grade", "dark_moody", "Apply registered dark-moody DRX.")
    look_tool("create_music_video_grade", "music_video", "Apply registered music-video DRX.")
    look_tool("create_commercial_grade", "commercial", "Apply registered commercial DRX.")

    @mcp.tool()
    def analyze_clip_scopes() -> None:
        """Explain why numerical image analysis cannot use the official scripting API."""
        services.colors.inspect_clip_limitation()
