"""Node graph inspection and supported state changes."""

from typing import Any

from .context import Services


def register(mcp: Any, services: Services) -> None:
    @mcp.tool()
    def inspect_node_tree(
        track_index: int, item_index: int, layer: int = 1
    ) -> dict[str, Any]:
        """Inspect count, labels, LUTs, tools, and cache mode for a clip node graph."""
        return services.nodes.inspect(track_index, item_index, layer)

    @mcp.tool()
    def list_nodes(track_index: int, item_index: int, layer: int = 1) -> list[dict[str, Any]]:
        """List nodes in a clip color graph using 1-based node indices."""
        return services.nodes.inspect(track_index, item_index, layer)["nodes"]

    @mcp.tool()
    def set_node_enabled(
        track_index: int, item_index: int, node_index: int, enabled: bool
    ) -> dict[str, Any]:
        """Enable or bypass a color node through the official Graph API."""
        return services.nodes.set_enabled(track_index, item_index, node_index, enabled)

    def unsupported(name: str, description: str) -> None:
        @mcp.tool(name=name, description=description)
        def operation() -> None:
            services.nodes.unsupported_edit(name)

    unsupported("add_serial_node", "Report the official API limitation for adding serial nodes.")
    unsupported("add_parallel_node", "Report the official API limitation for parallel nodes.")
    unsupported("add_layer_mixer", "Report the official API limitation for layer mixers.")
    unsupported("label_node", "Report the official API limitation for changing node labels.")
