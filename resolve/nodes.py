"""Color node graph inspection within the official API's limits."""

from typing import Any

from .connection import ResolveConnection
from .errors import CapabilityError, OperationError, ValidationError
from .timeline import TimelineService


class NodeService:
    def __init__(self, connection: ResolveConnection) -> None:
        self.connection = connection
        self.timelines = TimelineService(connection)

    def inspect(self, track_index: int, item_index: int, layer: int = 1) -> dict[str, Any]:
        item = self.timelines.item(track_index, item_index)
        graph = item.GetNodeGraph(layer)
        if graph is None:
            raise OperationError("Resolve did not return a node graph")
        nodes = [
            {
                "index": index,
                "label": graph.GetNodeLabel(index),
                "lut": graph.GetLUT(index),
                "tools": graph.GetToolsInNode(index) or [],
                "cache_mode": graph.GetNodeCacheMode(index),
            }
            for index in range(1, graph.GetNumNodes() + 1)
        ]
        return {"layer": layer, "count": len(nodes), "nodes": nodes}

    def set_enabled(
        self, track_index: int, item_index: int, node_index: int, enabled: bool
    ) -> dict[str, Any]:
        graph = self.timelines.item(track_index, item_index).GetNodeGraph()
        if node_index < 1 or node_index > graph.GetNumNodes():
            raise ValidationError(f"Node index must be between 1 and {graph.GetNumNodes()}")
        if not graph.SetNodeEnabled(node_index, enabled):
            raise OperationError("Resolve could not change the node enabled state")
        return {"node_index": node_index, "enabled": enabled}

    @staticmethod
    def unsupported_edit(operation: str) -> None:
        raise CapabilityError(
            f"{operation} is not exposed by Resolve 20's official scripting API. "
            "Create the node tree in Resolve, export it as DRX, then apply it with apply_grade."
        )
