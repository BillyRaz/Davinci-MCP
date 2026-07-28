"""Project and timeline selection operations."""

from typing import Any

from .connection import ResolveConnection
from .errors import NotFoundError, OperationError


class ProjectService:
    def __init__(self, connection: ResolveConnection) -> None:
        self.connection = connection

    def current(self) -> dict[str, Any]:
        project = self.connection.project()
        return {
            "name": project.GetName(),
            "unique_id": project.GetUniqueId(),
            "timeline_count": project.GetTimelineCount(),
            "rendering": project.IsRenderingInProgress(),
        }

    def timelines(self) -> list[dict[str, Any]]:
        project = self.connection.project()
        current = project.GetCurrentTimeline()
        return [
            {
                "index": index,
                "name": timeline.GetName(),
                "unique_id": timeline.GetUniqueId(),
                "current": bool(current and timeline.GetUniqueId() == current.GetUniqueId()),
            }
            for index in range(1, project.GetTimelineCount() + 1)
            if (timeline := project.GetTimelineByIndex(index)) is not None
        ]

    def switch_timeline(self, name: str) -> dict[str, Any]:
        project = self.connection.project()
        for index in range(1, project.GetTimelineCount() + 1):
            timeline = project.GetTimelineByIndex(index)
            if timeline and timeline.GetName() == name:
                if not project.SetCurrentTimeline(timeline):
                    raise OperationError(f"Resolve could not switch to timeline {name!r}")
                return {"name": name, "unique_id": timeline.GetUniqueId()}
        raise NotFoundError(f"Timeline {name!r} was not found")
