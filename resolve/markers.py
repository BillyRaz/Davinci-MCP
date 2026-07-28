"""Timeline marker operations."""

from typing import Any

from .connection import ResolveConnection
from .errors import NotFoundError, OperationError
from .models import MarkerInput


class MarkerService:
    def __init__(self, connection: ResolveConnection) -> None:
        self.connection = connection

    def list(self) -> list[dict[str, Any]]:
        markers = self.connection.timeline().GetMarkers() or {}
        return [{"frame": int(frame), **data} for frame, data in sorted(markers.items())]

    def add(self, marker: MarkerInput) -> dict[str, Any]:
        ok = self.connection.timeline().AddMarker(
            marker.frame,
            marker.color,
            marker.name,
            marker.note,
            marker.duration,
            marker.custom_data,
        )
        if not ok:
            raise OperationError("Resolve could not add the marker (the frame may be occupied)")
        return marker.model_dump()

    def delete(self, frame: int) -> dict[str, int]:
        if not self.connection.timeline().DeleteMarkerAtFrame(frame):
            raise NotFoundError(f"No marker exists at timeline frame {frame}")
        return {"deleted_frame": frame}

    def jump(self, frame: int) -> dict[str, Any]:
        timeline = self.connection.timeline()
        marker = (timeline.GetMarkers() or {}).get(float(frame))
        if marker is None:
            raise NotFoundError(f"No marker exists at timeline frame {frame}")
        fps = float(timeline.GetSetting("timelineFrameRate"))
        base = timeline.GetStartTimecode().split(":")
        start_frames = (((int(base[0]) * 60 + int(base[1])) * 60 + int(base[2])) * fps) + int(
            base[3]
        )
        total = int(start_frames + frame)
        ff = total % int(fps)
        seconds = total // int(fps)
        tc = f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}:{ff:02}"
        if not timeline.SetCurrentTimecode(tc):
            raise OperationError(f"Resolve could not move the playhead to {tc}")
        return {"frame": frame, "timecode": tc, "marker": marker}
