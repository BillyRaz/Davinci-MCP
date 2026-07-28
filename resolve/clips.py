"""Clip selection, grade copy, and batch metadata operations."""

from typing import Any

from .connection import ResolveConnection
from .errors import CapabilityError, OperationError
from .timeline import TimelineService


class ClipService:
    def __init__(self, connection: ResolveConnection) -> None:
        self.connection = connection
        self.timelines = TimelineService(connection)

    def current(self) -> dict[str, Any]:
        item = self.timelines.current_item()
        media = item.GetMediaPoolItem()
        return {
            "name": item.GetName(),
            "unique_id": item.GetUniqueId(),
            "start": item.GetStart(),
            "end": item.GetEnd(),
            "duration": item.GetDuration(),
            "properties": item.GetProperty(),
            "media_properties": media.GetClipProperty() if media else {},
        }

    def selected(self) -> list[dict[str, Any]]:
        """Return Media Pool selection; timeline multi-selection is not exposed."""
        selected = self.connection.project().GetMediaPool().GetSelectedClips() or []
        return [
            {
                "name": clip.GetName(),
                "unique_id": clip.GetUniqueId(),
                "properties": clip.GetClipProperty(),
            }
            for clip in selected
        ]

    def copy_grade(
        self, source_track: int, source_item: int, targets: list[dict[str, int]]
    ) -> dict[str, int]:
        source = self.timelines.item(source_track, source_item)
        target_items = [
            self.timelines.item(target["track_index"], target["item_index"])
            for target in targets
        ]
        if not target_items:
            raise OperationError("At least one target clip is required")
        if not source.CopyGrades(target_items):
            raise OperationError("Resolve could not copy the grade to the target clips")
        return {"copied_to": len(target_items)}

    def selected_timeline_items(self) -> list[Any]:
        raise CapabilityError(
            "Resolve 20's official scripting API does not expose timeline clip selection. "
            "Address timeline clips by track_index and item_index instead."
        )
